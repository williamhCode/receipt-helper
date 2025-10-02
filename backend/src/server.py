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
    GroupResponse,
    GroupUpdate,
    GroupNameUpdate,  # NEW: Import the new schema
    ReceiptCreate,
    ReceiptResponse,
    ReceiptUpdate,
    PersonCreate,
    PersonResponse,
    PersonUpdate,
    ReceiptEntryCreate,
    ReceiptEntryUpdate,
)

# Import the connection manager
from .websocket_manager import connection_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# fastapi app -------------------------------------------------
app = FastAPI(title="Receipt Helper", version="0.0.1")

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# database setup -----------------------------------------------
db_url = os.getenv(
    "DATABASE_URL", "postgresql://williamhou@localhost:5432/receipt_helper"
)
engine = create_engine(db_url, pool_pre_ping=True)
# Base.metadata.create_all(bind=engine)

# dependency --------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# Helper functions ---------------------------------------------
def get_or_create_person(db: Session, name: str) -> Person:
    """Get existing person by name or create a new one"""
    person = db.query(Person).filter(Person.name == name).first()
    if not person:
        person = Person(name=name)
        db.add(person)
        db.flush()  # Flush to get the ID without committing
    return person


def get_persons_from_names(db: Session, names: list[str]) -> list[Person]:
    """Convert list of names to list of Person objects"""
    return [get_or_create_person(db, name) for name in names]


def persons_to_names(persons: list[Person]) -> list[str]:
    """Convert list of Person objects to list of names for frontend compatibility"""
    return [person.name for person in persons]


# SIMPLIFIED: Just broadcast "refresh_group" to all clients in a group
async def broadcast_group_update(group_id: int, action: str = "update"):
    """Simple function to tell all clients in a group to refresh"""
    await connection_manager.broadcast_to_group(
        group_id,
        {
            "type": "refresh_group",
            "group_id": group_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),  # Convert to string!
        },
    )


# Response model conversion functions (FIXED datetime serialization)
def group_to_response(group: Group) -> dict:
    """Convert Group model to response format with string names"""
    return {
        "id": group.id,
        "created_at": group.created_at.isoformat(),  # Convert to string
        "slug": group.slug,
        "name": group.name,  # NEW: Include the name field
        "people": persons_to_names(group.people),
        "receipts": [receipt_to_response(receipt) for receipt in group.receipts],
    }


def receipt_to_response(receipt: Receipt) -> dict:
    """Convert Receipt model to response format with string names"""
    return {
        "id": receipt.id,
        "created_at": receipt.created_at.isoformat(),  # Convert to string
        "processed": receipt.processed,
        "name": receipt.name,
        "raw_data": receipt.raw_data,
        "paid_by": receipt.paid_by_person.name if receipt.paid_by_person else None,
        "group_id": receipt.group_id,
        "people": persons_to_names(receipt.people),
        "entries": [entry_to_response(entry) for entry in receipt.entries],
    }


def entry_to_response(entry: ReceiptEntry) -> dict:
    """Convert ReceiptEntry model to response format with string names"""
    return {
        "id": entry.id,
        "name": entry.name,
        "price": entry.price,
        "taxable": entry.taxable,
        "assigned_to": persons_to_names(entry.assigned_to_people),
        "receipt_id": entry.receipt_id,
    }


# WebSocket endpoints ------------------------------------------
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


# Regular endpoints ---------------------------------------------------


# Root endpoint
@app.get("/")
def root():
    return {"message": "Receipt Helper API"}


# Person endpoints
@app.get("/people/", response_model=list[PersonResponse])
def list_people(db: SessionDep):
    return db.query(Person).all()


@app.post("/people/", response_model=PersonResponse)
async def create_person(person: PersonCreate, db: SessionDep):
    existing = db.query(Person).filter(Person.name == person.name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Person with this name already exists"
        )

    db_person = Person(name=person.name)
    db.add(db_person)
    db.commit()
    db.refresh(db_person)

    # Broadcast to all groups that might be affected
    for group_id in list(connection_manager.group_connections.keys()):
        await broadcast_group_update(group_id, "person_created")

    return db_person


@app.patch("/people/{person_id}", response_model=PersonResponse)
async def update_person(person_id: int, person_update: PersonUpdate, db: SessionDep):
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

    # Find all groups that include this person and broadcast
    groups_with_person = (
        db.query(Group).filter(Group.people.any(Person.id == person_id)).all()
    )
    for group in groups_with_person:
        await broadcast_group_update(group.id, "person_renamed")

    return person


@app.delete("/people/{person_id}")
async def delete_person(person_id: int, db: SessionDep):
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


# Group endpoints
@app.post("/groups/")
async def create_group(group: GroupCreate, db: SessionDep):
    people = get_persons_from_names(db, group.people)

    db_group = Group(
        people=people,
        key_hash="placeholder_hash",
        name="",  # Temporary empty name - will be set after commit to get ID
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    # NEW: Set the default name to "Group #{id}" after getting the ID
    db_group.name = f"Group {db_group.id}"
    db.commit()
    db.refresh(db_group)

    return group_to_response(db_group)


@app.delete("/groups/{group_id}")
async def delete_group(group_id: int, db: SessionDep):
    """Delete a group and all its receipts"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Delete the group (receipts and entries will be cascade deleted if set up in models)
    db.delete(group)
    db.commit()
    
    # Broadcast deletion to any connected clients before they're disconnected
    await broadcast_group_update(group_id, "group_deleted")
    
    return {"message": "Group deleted successfully", "id": group_id}


@app.get("/groups/")
def list_groups(db: SessionDep):
    groups = db.query(Group).all()
    return [group_to_response(group) for group in groups]


@app.get("/groups/{group_id}")
def get_group(group_id: int, db: SessionDep):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group_to_response(group)


@app.patch("/groups/{group_id}")
async def update_group(group_id: int, group_update: GroupUpdate, db: SessionDep):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # NEW: Handle name updates
    if group_update.name is not None:
        group.name = group_update.name

    if group_update.people is not None:
        people = get_persons_from_names(db, group_update.people)
        group.people = people

    db.commit()
    db.refresh(group)

    # Broadcast update
    await broadcast_group_update(group_id, "group_updated")

    return group_to_response(group)


# NEW: Dedicated endpoint for updating just the group name
@app.patch("/groups/{group_id}/name")
async def update_group_name(
    group_id: int, name_update: GroupNameUpdate, db: SessionDep
):
    """Update only the group name - useful for inline editing"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    group.name = name_update.name
    db.commit()
    db.refresh(group)

    # Broadcast name update specifically
    await broadcast_group_update(group_id, "group_name_updated")

    return group_to_response(group)


# Receipt endpoints
@app.post("/groups/{group_id}/receipts/")
async def create_receipt(group_id: int, receipt: ReceiptCreate, db: SessionDep):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    people = get_persons_from_names(db, receipt.people)

    paid_by_person = None
    if receipt.paid_by:
        paid_by_person = get_or_create_person(db, receipt.paid_by)

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

    # Broadcast update
    await broadcast_group_update(group_id, "receipt_created")

    return receipt_to_response(db_receipt)

# NEW: Delete a receipt
@app.delete("/receipts/{receipt_id}")
async def delete_receipt(receipt_id: int, db: SessionDep):
    """Delete a receipt and all its entries"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    group_id = receipt.group_id
    
    # Delete the receipt (entries will be cascade deleted if set up in models)
    db.delete(receipt)
    db.commit()
    
    # Broadcast update
    await broadcast_group_update(group_id, "receipt_deleted")
    
    return {"message": "Receipt deleted successfully", "id": receipt_id}

@app.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: int, db: SessionDep):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt_to_response(receipt)


# UPDATE: Modify the existing update_receipt endpoint to handle paid_by
@app.patch("/receipts/{receipt_id}")
async def update_receipt(
    receipt_id: int, receipt_update: ReceiptUpdate, db: SessionDep
):
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

    # Broadcast update
    await broadcast_group_update(group_id, "receipt_updated")

    return receipt_to_response(receipt)


# UPDATE: Modify the existing update_receipt_entry endpoint to handle all fields
@app.patch("/receipt-entries/{entry_id}")
async def update_receipt_entry(
    entry_id: int, update_data: ReceiptEntryUpdate, db: SessionDep
):
    """Update a receipt entry and broadcast changes to all group members"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    group_id = entry.receipt.group_id

    # Update assigned_to if provided
    if update_data.assigned_to is not None:
        assigned_people = get_persons_from_names(db, update_data.assigned_to)
        entry.assigned_to_people = assigned_people

    # NEW: Update name if provided
    if update_data.name is not None:
        entry.name = update_data.name

    # NEW: Update price if provided
    if update_data.price is not None:
        if update_data.price < 0:
            raise HTTPException(status_code=400, detail="Price must be non-negative")
        entry.price = update_data.price

    # NEW: Update taxable if provided
    if update_data.taxable is not None:
        entry.taxable = update_data.taxable

    db.commit()
    db.refresh(entry)

    entry_response = entry_to_response(entry)

    # Broadcast the update
    await connection_manager.broadcast_to_group(
        group_id,
        {
            "type": "entry_updated",
            "entry_id": entry_id,
            "entry": entry_response,
            "group_id": group_id,
            "timestamp": datetime.now().isoformat(),
        },
    )

    return entry_response


# NEW: Create a new receipt entry
@app.post("/receipts/{receipt_id}/entries/")
async def create_receipt_entry(
    receipt_id: int, entry_data: ReceiptEntryCreate, db: SessionDep
):
    """Create a new entry for an existing receipt"""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    group_id = receipt.group_id

    # Create new entry with no assignments by default
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

    # Broadcast update
    await broadcast_group_update(group_id, "entry_created")

    return entry_to_response(db_entry)


@app.delete("/receipt-entries/{entry_id}")
async def delete_receipt_entry(entry_id: int, db: SessionDep):
    """Delete a receipt entry"""
    entry = db.query(ReceiptEntry).filter(ReceiptEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    group_id = entry.receipt.group_id

    db.delete(entry)
    db.commit()

    # Broadcast update
    await broadcast_group_update(group_id, "entry_deleted")

    return {"message": "Entry deleted successfully", "id": entry_id}


@app.get("/groups/{group_id}/receipts/")
def list_group_receipts(group_id: int, db: SessionDep):
    receipts = db.query(Receipt).filter(Receipt.group_id == group_id).all()
    return [receipt_to_response(receipt) for receipt in receipts]


# WebSocket status endpoint
@app.get("/groups/{group_id}/connections")
def get_group_connections(group_id: int):
    """Get the number of active WebSocket connections for a group"""
    count = connection_manager.get_group_connection_count(group_id)
    return {"group_id": group_id, "active_connections": count}


# Sample data endpoint
@app.post("/create-sample-data")
async def create_sample_data(db: SessionDep):
    william = get_or_create_person(db, "William")
    hao = get_or_create_person(db, "Hao")
    howard = get_or_create_person(db, "Howard")

    group = Group(
        people=[william, hao, howard],
        key_hash="sample_hash",
        name="",  # Temporary empty name
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Set the default name pattern
    group.name = f"Group #{group.id}"
    db.commit()
    db.refresh(group)

    sample_receipts = [
        {
            "name": "Whole Foods Market",
            "raw_data": "Grocery shopping receipt with organic produce",
            "paid_by": william,
        },
        {
            "name": "Starbucks Coffee",
            "raw_data": "Coffee and pastries for the team",
            "paid_by": hao,
        },
        {
            "name": "Pizza Palace",
            "raw_data": "Team lunch - large pepperoni pizza",
            "paid_by": howard,
        },
    ]

    receipts_created = []
    for receipt_data in sample_receipts:
        receipt = Receipt(
            group_id=group.id,
            processed=False,
            name=receipt_data["name"],
            raw_data=receipt_data["raw_data"],
            paid_by_person=receipt_data["paid_by"],
            people=[william, hao, howard],
        )
        db.add(receipt)
        db.flush()
        receipts_created.append(receipt)

        if receipt_data["name"] == "Whole Foods Market":
            sample_items = [
                ("Organic Apples", 5.99, True),
                ("Bananas", 3.50, True),
                ("Sourdough Bread", 4.99, False),
                ("Almond Milk", 4.25, False),
            ]

            for name, price, taxable in sample_items:
                entry = ReceiptEntry(
                    receipt_id=receipt.id,
                    name=name,
                    price=price,
                    taxable=taxable,
                    assigned_to_people=[],
                )
                db.add(entry)

        elif receipt_data["name"] == "Starbucks Coffee":
            starbucks_items = [
                ("Large Latte", 5.45, True),
                ("Cappuccino", 4.95, True),
                ("Blueberry Muffin", 3.25, True),
            ]

            for name, price, taxable in starbucks_items:
                entry = ReceiptEntry(
                    receipt_id=receipt.id,
                    name=name,
                    price=price,
                    taxable=taxable,
                    assigned_to_people=[],
                )
                db.add(entry)

        elif receipt_data["name"] == "Pizza Palace":
            pizza_items = [
                ("Large Pepperoni Pizza", 18.99, True),
                ("Garlic Bread", 6.99, True),
                ("2L Coca Cola", 3.99, True),
            ]

            for name, price, taxable in pizza_items:
                entry = ReceiptEntry(
                    receipt_id=receipt.id,
                    name=name,
                    price=price,
                    taxable=taxable,
                    assigned_to_people=[],
                )
                db.add(entry)

    db.commit()

    # Broadcast sample data creation
    await broadcast_group_update(group.id, "sample_data_created")

    return {
        "message": "Sample data created with Person objects",
        "group_id": group.id,
        "receipts_created": len(receipts_created),
    }
