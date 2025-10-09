from typing import Annotated
import os
import json
import logging
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import Base, Group, Receipt, ReceiptEntry, Person
from .schemas import (
    GroupCreate,
    GroupUpdate,
    GroupNameUpdate,
    ReceiptCreate,
    ReceiptUpdate,
    PersonResponse,
    PersonUpdate,
    ReceiptEntryCreate,
    ReceiptEntryUpdate,
)

from .websocket_manager import connection_manager
from .crud import (
    get_or_create_person,
    get_people_by_names,
    create_receipt,
    update_receipt_people,
    update_receipt_paid_by,
    create_receipt_entry,
    update_entry_assigned_people,
    get_group_people,
    get_group_receipts,
)

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
db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2:///receipt_helper")

# Fix Railway's postgres:// to postgresql+psycopg2://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

engine = create_engine(db_url, pool_pre_ping=True)


# Dependency
def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ============================================================================
# Helper functions
# ============================================================================

def persons_to_names(persons: list[Person]) -> list[str]:
    """Convert list of Person objects to list of names"""
    return [person.name for person in persons]


async def broadcast_group_update(group_id: int, action: str = "update"):
    """Broadcast refresh message to all clients in a group"""
    await connection_manager.broadcast_to_group(
        group_id,
        {
            "type": "refresh_group",
            "group_id": group_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),
        },
    )


# ============================================================================
# Response conversion functions
# ============================================================================

def group_to_response(group: Group) -> dict:
    """Convert Group model to response format"""
    return {
        "id": group.id,
        "created_at": group.created_at.isoformat(),
        "slug": group.slug,
        "name": group.name,
        "people": persons_to_names(group.people),
        "receipts": [receipt_to_response(receipt) for receipt in group.receipts],
    }


def receipt_to_response(receipt: Receipt) -> dict:
    """Convert Receipt model to response format"""
    return {
        "id": receipt.id,
        "created_at": receipt.created_at.isoformat(),
        "processed": receipt.processed,
        "name": receipt.name,
        "raw_data": receipt.raw_data,
        "paid_by": receipt.paid_by_person.name if receipt.paid_by_person else None,
        "group_id": receipt.group_id,
        "people": persons_to_names(receipt.people),
        "entries": [entry_to_response(entry) for entry in receipt.entries],
    }


def entry_to_response(entry: ReceiptEntry) -> dict:
    """Convert ReceiptEntry model to response format"""
    return {
        "id": entry.id,
        "name": entry.name,
        "price": entry.price,
        "taxable": entry.taxable,
        "assigned_to": persons_to_names(entry.assigned_to_people),
        "receipt_id": entry.receipt_id,
    }


# ============================================================================
# WebSocket endpoints
# ============================================================================

@app.websocket("/ws/groups/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: int):
    """WebSocket endpoint for real-time updates within a group"""
    # Verify group exists
    with Session(engine) as db:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            await websocket.close(code=1008, reason="Group not found")
            return

    # Connect the websocket
    await connection_manager.connect(websocket, group_id)

    try:
        # Send initial connection confirmation
        await connection_manager.send_to_websocket(
            websocket,
            {
                "type": "connected",
                "group_id": group_id,
                "message": f"Connected to group {group_id}",
            },
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping messages for connection health
                if message.get("type") == "ping":
                    await connection_manager.send_to_websocket(
                        websocket,
                        {"type": "pong", "timestamp": message.get("timestamp")},
                    )

            except json.JSONDecodeError:
                await connection_manager.send_to_websocket(
                    websocket, {"type": "error", "message": "Invalid JSON format"}
                )

    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await connection_manager.disconnect(websocket)


# ============================================================================
# API endpoints
# ============================================================================

@app.get("/")
def root():
    """Health check endpoint"""
    return {"message": "Receipt Helper API", "version": "0.1.0"}


# ============================================================================
# Person endpoints (within group context)
# ============================================================================

@app.get("/groups/{group_id}/people/", response_model=list[PersonResponse])
def list_group_people(group_id: int, db: SessionDep):
    """Get all people in a group"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return get_group_people(db, group_id)


@app.patch("/people/{person_id}", response_model=PersonResponse)
async def update_person(person_id: int, person_update: PersonUpdate, db: SessionDep):
    """Update a person's name (within their group)"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Check if new name already exists in the same group
    existing = db.query(Person).filter(
        Person.name == person_update.name,
        Person.group_id == person.group_id,
        Person.id != person_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Person with name '{person_update.name}' already exists in this group"
        )
    
    person.name = person_update.name
    db.commit()
    db.refresh(person)
    
    # Broadcast update to the person's group
    await broadcast_group_update(person.group_id, "person_renamed")
    
    return person


# ============================================================================
# Group endpoints
# ============================================================================

@app.get("/groups/")
def list_groups(db: SessionDep):
    """Get all groups (without full details)"""
    groups = db.query(Group).all()
    return [group_to_response(group) for group in groups]


@app.post("/groups/")
async def create_group_endpoint(group: GroupCreate, db: SessionDep):
    """Create a new group"""
    db_group = Group(
        key_hash="placeholder_hash",
        name=group.name or "",
    )
    db.add(db_group)
    db.flush()  # Get the ID

    # Set default name based on ID if not provided
    if not db_group.name:
        db_group.name = f"Group {db_group.id}"
    
    # Create people in this group
    for person_name in group.people:
        person = Person(name=person_name, group_id=db_group.id)
        db.add(person)

    db.commit()
    db.refresh(db_group)

    return group_to_response(db_group)


@app.get("/groups/{group_id}")
def get_group(group_id: int, db: SessionDep):
    """Get a single group with all details"""
    group = db.query(Group).filter(Group.id == group_id).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return group_to_response(group)


@app.patch("/groups/{group_id}")
async def update_group_endpoint(group_id: int, group_update: GroupUpdate, db: SessionDep):
    """Update group name and/or people"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_update.name is not None:
        group.name = group_update.name

    if group_update.people is not None:
        # Replace all people in the group
        # This will delete old people (cascade) and create new ones
        people = get_people_by_names(db, group_update.people, group_id)
        group.people = people

    db.commit()
    db.refresh(group)

    await broadcast_group_update(group_id, "group_updated")

    return group_to_response(group)


@app.patch("/groups/{group_id}/name")
async def update_group_name_endpoint(
    group_id: int, name_update: GroupNameUpdate, db: SessionDep
):
    """Update only the group name"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group.name = name_update.name
    db.commit()
    db.refresh(group)

    await broadcast_group_update(group_id, "group_name_updated")

    return group_to_response(group)


@app.delete("/groups/{group_id}")
async def delete_group_endpoint(group_id: int, db: SessionDep):
    """Delete a group and all its receipts and people (CASCADE)"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    db.delete(group)
    db.commit()
    
    await broadcast_group_update(group_id, "group_deleted")
    
    return {"message": "Group deleted successfully", "id": group_id}


# ============================================================================
# Receipt endpoints
# ============================================================================

@app.post("/groups/{group_id}/receipts/")
async def create_receipt_endpoint(group_id: int, receipt_data: ReceiptCreate, db: SessionDep):
    """Create a new receipt in a group"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Use the CRUD helper to create receipt
    db_receipt = create_receipt(
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
        create_receipt_entry(
            db=db,
            receipt=db_receipt,
            name=entry_data.name,
            price=entry_data.price,
            taxable=entry_data.taxable,
            assigned_to_names=entry_data.assigned_to,
        )

    db.commit()
    db.refresh(db_receipt)

    await broadcast_group_update(group_id, "receipt_created")

    return receipt_to_response(db_receipt)


@app.patch("/receipts/{receipt_id}")
async def update_receipt_endpoint(
    receipt_id: int, receipt_update: ReceiptUpdate, db: SessionDep
):
    """Update receipt details"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    group_id = receipt.group_id

    # Update people
    if receipt_update.people is not None:
        update_receipt_people(db, receipt, receipt_update.people)
        
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
        update_receipt_paid_by(db, receipt, receipt_update.paid_by)

    db.commit()
    db.refresh(receipt)

    await broadcast_group_update(group_id, "receipt_updated")

    return receipt_to_response(receipt)


@app.delete("/receipts/{receipt_id}")
async def delete_receipt_endpoint(receipt_id: int, db: SessionDep):
    """Delete a receipt and all its entries (CASCADE)"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    group_id = receipt.group_id
    
    db.delete(receipt)
    db.commit()
    
    await broadcast_group_update(group_id, "receipt_deleted")
    
    return {"message": "Receipt deleted successfully", "id": receipt_id}


# ============================================================================
# Receipt Entry endpoints
# ============================================================================

@app.post("/receipts/{receipt_id}/entries/")
async def create_receipt_entry_endpoint(
    receipt_id: int, entry_data: ReceiptEntryCreate, db: SessionDep
):
    """Create a new entry for a receipt"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Use CRUD helper
    db_entry = create_receipt_entry(
        db=db,
        receipt=receipt,
        name=entry_data.name,
        price=entry_data.price,
        taxable=entry_data.taxable,
        assigned_to_names=entry_data.assigned_to,
    )

    db.commit()
    db.refresh(db_entry)

    await broadcast_group_update(receipt.group_id, "entry_created")

    return entry_to_response(db_entry)


@app.patch("/receipt-entries/{entry_id}")
async def update_receipt_entry_endpoint(
    entry_id: int, update_data: ReceiptEntryUpdate, db: SessionDep
):
    """Update a receipt entry"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    # Update assigned people
    if update_data.assigned_to is not None:
        update_entry_assigned_people(db, entry, update_data.assigned_to)

    # Update name
    if update_data.name is not None:
        entry.name = update_data.name

    # Update price
    if update_data.price is not None:
        if update_data.price < 0:
            raise HTTPException(status_code=400, detail="Price must be non-negative")
        entry.price = update_data.price

    # Update taxable
    if update_data.taxable is not None:
        entry.taxable = update_data.taxable

    db.commit()
    db.refresh(entry)

    # Broadcast granular update
    await connection_manager.broadcast_to_group(
        entry.receipt.group_id,
        {
            "type": "entry_updated",
            "entry_id": entry_id,
            "entry": entry_to_response(entry),
            "group_id": entry.receipt.group_id,
            "timestamp": datetime.now().isoformat(),
        },
    )

    return entry_to_response(entry)


@app.delete("/receipt-entries/{entry_id}")
async def delete_receipt_entry_endpoint(entry_id: int, db: SessionDep):
    """Delete a receipt entry"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    group_id = entry.receipt.group_id

    db.delete(entry)
    db.commit()

    await broadcast_group_update(group_id, "entry_deleted")

    return {"message": "Entry deleted successfully", "id": entry_id}
