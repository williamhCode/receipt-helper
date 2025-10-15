from typing import Annotated
import os
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from src import models, schemas, crud

from .websocket_manager import connection_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Receipt Helper", version="0.1.0")

# CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg:///receipt_helper")

# if db_url.startswith("postgres://"):
#     db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url, pool_pre_ping=True)


# Dependency
async def get_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ============================================================================
# WebSocket endpoints
# ============================================================================

# @app.websocket("/ws/groups/{group_id}")
# async def websocket_endpoint(websocket: WebSocket, group_id: int):
#     """WebSocket endpoint for real-time updates within a group"""
#     # Verify group exists
#     with Session(engine) as db:
#         group = db.query(Group).filter(Group.id == group_id).first()
#         if not group:
#             await websocket.close(code=1008, reason="Group not found")
#             return

#     # Connect the websocket
#     await connection_manager.connect(websocket, group_id)

#     try:
#         # Send initial connection confirmation
#         await connection_manager.send_to_websocket(
#             websocket,
#             {
#                 "type": "connected",
#                 "group_id": group_id,
#                 "message": f"Connected to group {group_id}",
#             },
#         )

#         # Keep connection alive and handle incoming messages
#         while True:
#             try:
#                 data = await websocket.receive_text()
#                 message = json.loads(data)

#                 # Handle ping messages for connection health
#                 if message.get("type") == "ping":
#                     await connection_manager.send_to_websocket(
#                         websocket,
#                         {"type": "pong", "timestamp": message.get("timestamp")},
#                     )

#             except json.JSONDecodeError:
#                 await connection_manager.send_to_websocket(
#                     websocket, {"type": "error", "message": "Invalid JSON format"}
#                 )

#     except WebSocketDisconnect:
#         await connection_manager.disconnect(websocket)
#     except Exception as e:
#         logger.error(f"WebSocket error: {e}")
#         await connection_manager.disconnect(websocket)


# ============================================================================
# API endpoints
# ============================================================================

@app.get("/")
def root():
    """Health check endpoint"""
    return {"message": "Receipt Helper API", "version": "0.1.0"}


# ============================================================================
# Group endpoints
# ============================================================================

@app.post("/groups/", response_model=schemas.Group)
async def create_group(group: schemas.GroupCreate, db: SessionDep):
    db_group = models.Group(
        key_hash="placeholder_hash",
        name=group.name or "",
    )
    db.add(db_group)
    await db.flush()

    if not db_group.name:
        db_group.name = f"Group {db_group.id}"

    for person_name in group.people:
        person = models.Person(name=person_name, group_id=db_group.id)
        db.add(person)

    await db.commit()
    await db.refresh(db_group)

    return db_group


@app.get("/groups/", response_model=list[schemas.Group])
async def get_groups(db: SessionDep):
    groups = (await db.scalars(select(models.Group))).all()
    return groups


@app.get("/groups/{group_id}", response_model=schemas.Group)
async def get_group(group_id: int, db: SessionDep):
    group = await db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return group


@app.patch("/groups/{group_id}", response_model=schemas.Group)
async def update_group(group_id: int, group_update: schemas.GroupUpdate, db: SessionDep):
    group = await db.get(models.Group, group_id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_update.name is not None:
        group.name = group_update.name

    if group_update.people is not None:
        group.people = await crud.get_or_create_people(db, group_id, group_update.people)

    await db.commit()
    await db.refresh(group)

    return group


@app.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: SessionDep):
    group = await db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()


# ============================================================================
# Person endpoints (within group context)
# ============================================================================

@app.get("/groups/{group_id}/people/", response_model=list[schemas.Person])
async def get_group_people(group_id: int, db: SessionDep):
    result = await db.execute(
        select(models.Person).where(models.Person.group_id == group_id)
    )
    people = result.scalars().all()
    return people


@app.patch("/people/{person_id}", response_model=schemas.Person)
async def update_person(person_id: int, person_update: schemas.PersonUpdate, db: SessionDep):
    """Update a person's name (within their group)"""
    person = await db.get(models.Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if name already exists in the same group
    result = await db.execute(
        select(models.Person).where(
            models.Person.name == person_update.name,
            models.Person.group_id == person.group_id,
            models.Person.id != person_id
        )
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Person with name '{person_update.name}' already exists in this group"
        )

    person.name = person_update.name
    await db.commit()
    await db.refresh(person)

    return person


# ============================================================================
# Receipt endpoints
# ============================================================================

@app.post("/groups/{group_id}/receipts/", response_model=schemas.Receipt)
async def create_receipt(group_id: int, receipt_data: schemas.ReceiptCreate, db: SessionDep):
    group = await db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Use CRUD helper to create receipt
    db_receipt = await crud.create_receipt(
        db=db,
        group_id=group_id,
        name=receipt_data.name,
        paid_by_name=receipt_data.paid_by,
        people_names=receipt_data.people,
        processed=receipt_data.processed,
        raw_data=receipt_data.raw_data,
    )

    # Create entries
    for entry_data in receipt_data.entries:
        await crud.create_receipt_entry(
            db=db,
            receipt=db_receipt,
            name=entry_data.name,
            price=entry_data.price,
            taxable=entry_data.taxable,
            assigned_to_names=entry_data.assigned_to,
        )

    await db.commit()
    await db.refresh(db_receipt)

    return db_receipt


@app.get("/receipts/{receipt_id}", response_model=schemas.Receipt)
async def get_receipt(receipt_id: int, db: SessionDep):
    receipt = await db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return receipt


@app.patch("/receipts/{receipt_id}", response_model=schemas.Receipt)
async def update_receipt(
    receipt_id: int, receipt_update: schemas.ReceiptUpdate, db: SessionDep
):
    """Update receipt details"""
    receipt = await db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Update people
    if receipt_update.people is not None:
        await crud.update_receipt_people(db, receipt, receipt_update.people)

        # If paid_by is no longer in the people list, clear it
        if receipt.paid_by_person and receipt.paid_by_person.name not in receipt_update.people:
            receipt.paid_by_id = None

    # Update processed status
    if receipt_update.processed is not None:
        receipt.processed = receipt_update.processed

    # Update name
    if receipt_update.name is not None:
        receipt.name = receipt_update.name

    # Update paid_by
    if receipt_update.paid_by == "":
        receipt.paid_by_id = None
    elif receipt_update.paid_by is not None:
        await crud.update_receipt_paid_by(db, receipt, receipt_update.paid_by)

    await db.commit()
    await db.refresh(receipt)

    return receipt


@app.delete("/receipts/{receipt_id}")
async def delete_receipt(receipt_id: int, db: SessionDep):
    """Delete a receipt and all its entries (CASCADE)"""
    receipt = await db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    await db.delete(receipt)
    await db.commit()

    return {"message": "Receipt deleted successfully", "id": receipt_id}


# ============================================================================
# Receipt Entry endpoints
# ============================================================================

@app.post("/receipts/{receipt_id}/entries/", response_model=schemas.ReceiptEntry)
async def create_receipt_entry(
    receipt_id: int, entry_data: schemas.ReceiptEntryCreate, db: SessionDep
):
    """Create a new entry for a receipt"""
    receipt = await db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Use CRUD helper
    db_entry = await crud.create_receipt_entry(
        db=db,
        receipt=receipt,
        name=entry_data.name,
        price=entry_data.price,
        taxable=entry_data.taxable,
        assigned_to_names=entry_data.assigned_to,
    )

    await db.commit()
    await db.refresh(db_entry)

    return db_entry


@app.patch("/receipt-entries/{entry_id}", response_model=schemas.ReceiptEntry)
async def update_receipt_entry(
    entry_id: int, update_data: schemas.ReceiptEntryUpdate, db: SessionDep
):
    """Update a receipt entry"""
    entry = await db.get(models.ReceiptEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    if update_data.assigned_to is not None:
        await crud.update_entry_assigned_people(db, entry, update_data.assigned_to)

    if update_data.name is not None:
        entry.name = update_data.name

    if update_data.price is not None:
        if update_data.price < 0:
            raise HTTPException(status_code=400, detail="Price must be non-negative")
        entry.price = update_data.price

    if update_data.taxable is not None:
        entry.taxable = update_data.taxable

    await db.commit()
    await db.refresh(entry)

    return entry


@app.delete("/receipt-entries/{entry_id}")
async def delete_receipt_entry(entry_id: int, db: SessionDep):
    """Delete a receipt entry"""
    entry = await db.get(models.ReceiptEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    await db.delete(entry)
    await db.commit()

    return {"message": "Entry deleted successfully", "id": entry_id}
