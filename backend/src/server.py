from typing import Annotated
import os
import json
import logging
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, joinedload

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import Base, Group, Receipt, ReceiptEntry, Person
from .schemas import (
    GroupCreate,
    GroupUpdate,
    GroupNameUpdate,
    ReceiptCreate,
    ReceiptUpdate,
    PersonCreate,
    PersonResponse,
    PersonUpdate,
    ReceiptEntryCreate,
    ReceiptEntryUpdate,
)

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

def get_or_create_person(db: Session, name: str) -> Person:
    """Get existing person by name or create a new one"""
    person = db.query(Person).filter(Person.name == name).first()
    if not person:
        person = Person(name=name)
        db.add(person)
        db.flush()
    return person


def get_persons_from_names(db: Session, names: list[str]) -> list[Person]:
    """Convert list of names to list of Person objects"""
    return [get_or_create_person(db, name) for name in names]


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
# Person endpoints
# ============================================================================

@app.get("/people/", response_model=list[PersonResponse])
def list_people(db: SessionDep):
    """Get all people"""
    return db.query(Person).all()


@app.post("/people/", response_model=PersonResponse)
async def create_person(person: PersonCreate, db: SessionDep):
    """Create a new person"""
    existing = db.query(Person).filter(Person.name == person.name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Person with this name already exists"
        )

    db_person = Person(name=person.name)
    db.add(db_person)
    db.commit()
    db.refresh(db_person)

    # Broadcast to all groups
    for group_id in list(connection_manager.group_connections.keys()):
        await broadcast_group_update(group_id, "person_created")

    return db_person


@app.patch("/people/{person_id}", response_model=PersonResponse)
async def update_person(person_id: int, person_update: PersonUpdate, db: SessionDep):
    """Update a person's name"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing = (
        db.query(Person)
        .filter(Person.name == person_update.name, Person.id != person_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Person with this name already exists"
        )

    person.name = person_update.name
    db.commit()
    db.refresh(person)

    # Broadcast to all affected groups
    groups_with_person = (
        db.query(Group).filter(Group.people.any(Person.id == person_id)).all()
    )
    for group in groups_with_person:
        await broadcast_group_update(group.id, "person_renamed")

    return person


@app.delete("/people/{person_id}")
async def delete_person(person_id: int, db: SessionDep):
    """Delete a person"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if (
        person.groups
        or person.receipts
        or person.paid_receipts
        or person.assigned_entries
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete person who is referenced in groups or receipts",
        )

    db.delete(person)
    db.commit()

    # Broadcast to all groups
    for group_id in list(connection_manager.group_connections.keys()):
        await broadcast_group_update(group_id, "person_deleted")

    return {"message": "Person deleted successfully"}


# ============================================================================
# Group endpoints
# ============================================================================

@app.get("/groups/")
def list_groups(db: SessionDep):
    """Get all groups (without full details)"""
    groups = db.query(Group).all()
    return [group_to_response(group) for group in groups]


@app.post("/groups/")
async def create_group(group: GroupCreate, db: SessionDep):
    """Create a new group"""
    people = get_persons_from_names(db, group.people)

    db_group = Group(
        people=people,
        key_hash="placeholder_hash",
        name="",
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    # Set default name based on ID
    db_group.name = f"Group {db_group.id}"
    db.commit()
    db.refresh(db_group)

    return group_to_response(db_group)


@app.get("/groups/{group_id}")
def get_group(group_id: int, db: SessionDep):
    """Get a single group with all details - OPTIMIZED with eager loading"""
    group = (
        db.query(Group)
        .filter(Group.id == group_id)
        .options(
            joinedload(Group.people),
            joinedload(Group.receipts)
            .joinedload(Receipt.people),
            joinedload(Group.receipts)
            .joinedload(Receipt.paid_by_person),
            joinedload(Group.receipts)
            .joinedload(Receipt.entries)
            .joinedload(ReceiptEntry.assigned_to_people),
        )
        .first()
    )
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return group_to_response(group)


@app.patch("/groups/{group_id}")
async def update_group(group_id: int, group_update: GroupUpdate, db: SessionDep):
    """Update group members"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_update.people is not None:
        people = get_persons_from_names(db, group_update.people)
        group.people = people

    if group_update.name is not None:
        group.name = group_update.name

    db.commit()
    db.refresh(group)

    await broadcast_group_update(group_id, "group_updated")

    return group_to_response(group)


@app.patch("/groups/{group_id}/name")
async def update_group_name(
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
async def delete_group(group_id: int, db: SessionDep):
    """Delete a group and all its receipts"""
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
async def create_receipt(group_id: int, receipt: ReceiptCreate, db: SessionDep):
    """Create a new receipt"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    people = get_persons_from_names(db, receipt.people)
    paid_by_person = get_or_create_person(db, receipt.paid_by) if receipt.paid_by else None

    db_receipt = Receipt(
        group_id=group_id,
        processed=receipt.processed,
        name=receipt.name,
        raw_data=receipt.raw_data,
        paid_by_person=paid_by_person,
        people=people,
    )
    db.add(db_receipt)
    db.flush()

    # Create entries
    for entry_data in receipt.entries:
        assigned_people = get_persons_from_names(db, entry_data.assigned_to)
        db_entry = ReceiptEntry(
            receipt_id=db_receipt.id,
            name=entry_data.name,
            price=entry_data.price,
            taxable=entry_data.taxable,
            assigned_to_people=assigned_people,
        )
        db.add(db_entry)

    db.commit()
    db.refresh(db_receipt)

    await broadcast_group_update(group_id, "receipt_created")

    return receipt_to_response(db_receipt)


@app.patch("/receipts/{receipt_id}")
async def update_receipt(
    receipt_id: int, receipt_update: ReceiptUpdate, db: SessionDep
):
    """Update receipt details"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    group_id = receipt.group_id

    if receipt_update.people is not None:
        people = get_persons_from_names(db, receipt_update.people)
        receipt.people = people

    if receipt_update.processed is not None:
        receipt.processed = receipt_update.processed

    if receipt_update.paid_by == "":
        receipt.paid_by_id = None
    elif receipt_update.paid_by is not None:
        paid_by_person = get_or_create_person(db, receipt_update.paid_by)
        receipt.paid_by_person = paid_by_person

    db.commit()
    db.refresh(receipt)

    await broadcast_group_update(group_id, "receipt_updated")

    return receipt_to_response(receipt)


@app.delete("/receipts/{receipt_id}")
async def delete_receipt(receipt_id: int, db: SessionDep):
    """Delete a receipt and all its entries"""
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
async def create_receipt_entry(
    receipt_id: int, entry_data: ReceiptEntryCreate, db: SessionDep
):
    """Create a new entry for a receipt"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    db_entry = ReceiptEntry(
        receipt_id=receipt_id,
        name=entry_data.name,
        price=entry_data.price,
        taxable=entry_data.taxable,
        assigned_to_people=[],
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    await broadcast_group_update(receipt.group_id, "entry_created")

    return entry_to_response(db_entry)


@app.patch("/receipt-entries/{entry_id}")
async def update_receipt_entry(
    entry_id: int, update_data: ReceiptEntryUpdate, db: SessionDep
):
    """Update a receipt entry"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    if update_data.assigned_to is not None:
        assigned_people = get_persons_from_names(db, update_data.assigned_to)
        entry.assigned_to_people = assigned_people

    if update_data.name is not None:
        entry.name = update_data.name

    if update_data.price is not None:
        if update_data.price < 0:
            raise HTTPException(status_code=400, detail="Price must be non-negative")
        entry.price = update_data.price

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
async def delete_receipt_entry(entry_id: int, db: SessionDep):
    """Delete a receipt entry"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    group_id = entry.receipt.group_id

    db.delete(entry)
    db.commit()

    await broadcast_group_update(group_id, "entry_deleted")

    return {"message": "Entry deleted successfully", "id": entry_id}
