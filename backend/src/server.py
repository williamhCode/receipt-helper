from typing import Annotated
import os
import logging

from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src import models, schemas, crud
from src.models import Base

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
db_url = os.getenv("DATABASE_URL", "postgresql:///receipt_helper")

engine = create_engine(db_url, pool_pre_ping=True)


# Dependency
def get_session():
    with Session(engine, expire_on_commit=False) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


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
def create_group(group: schemas.GroupCreate, db: SessionDep):
    db_group = models.Group(
        key_hash="placeholder_hash",
        name=group.name or "",
    )
    db.add(db_group)
    db.flush()

    if not db_group.name:
        db_group.name = f"Group {db_group.id}"

    for person_name in group.people:
        person = models.Person(name=person_name, group_id=db_group.id)
        db.add(person)

    db.commit()
    db.refresh(db_group)

    return db_group


@app.get("/groups/", response_model=list[schemas.Group])
def get_groups(db: SessionDep):
    stmt = select(models.Group)
    groups = db.scalars(stmt).all()
    return groups


@app.get("/groups/{group_id}", response_model=schemas.Group)
def get_group(group_id: int, db: SessionDep):
    stmt = select(models.Group).where(models.Group.id == group_id)
    group = db.scalars(stmt).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return group


@app.get("/groups/{group_id}/version")
def get_group_version(group_id: int, db: SessionDep):
    """Lightweight endpoint to check if group has been updated.

    Returns the last update timestamp for efficient polling.
    Clients can poll this endpoint to detect changes without fetching full group data.
    """
    stmt = select(models.Group.updated_at).where(models.Group.id == group_id)
    result = db.execute(stmt)
    updated_at = result.scalar_one_or_none()

    if updated_at is None:
        raise HTTPException(status_code=404, detail="Group not found")

    return {
        "group_id": group_id,
        "updated_at": updated_at.isoformat()
    }


@app.patch("/groups/{group_id}", response_model=schemas.Group)
def update_group(group_id: int, group_update: schemas.GroupUpdate, db: SessionDep):
    stmt = select(models.Group).where(models.Group.id == group_id)
    group = db.scalars(stmt).first()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_update.name is not None:
        group.name = group_update.name

    if group_update.people is not None:
        group.people = crud.get_or_create_people(db, group_id, group_update.people)

    db.commit()
    db.refresh(group)

    return group


@app.delete("/groups/{group_id}")
def delete_group(group_id: int, db: SessionDep):
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.delete(group)
    db.commit()

    return {"message": "Group deleted successfully", "id": group.id}


# ============================================================================
# Person endpoints (within group context)
# ============================================================================

@app.get("/groups/{group_id}/people/", response_model=list[schemas.Person])
def get_group_people(group_id: int, db: SessionDep):
    result = db.execute(
        select(models.Person).where(models.Person.group_id == group_id)
    )
    people = result.scalars().all()
    return people


@app.patch("/people/{person_id}", response_model=schemas.Person)
def update_person(person_id: int, person_update: schemas.PersonUpdate, db: SessionDep):
    """Update a person's name (within their group)"""
    person = db.get(models.Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if name already exists in the same group
    result = db.execute(
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
    db.commit()
    db.refresh(person)

    return person


# ============================================================================
# Receipt endpoints
# ============================================================================

@app.post("/groups/{group_id}/receipts/", response_model=schemas.Receipt)
def create_receipt(group_id: int, receipt_data: schemas.ReceiptCreate, db: SessionDep):
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Use CRUD helper to create receipt
    db_receipt = crud.create_receipt(
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
        crud.create_receipt_entry(
            db=db,
            receipt=db_receipt,
            name=entry_data.name,
            price=entry_data.price,
            taxable=entry_data.taxable,
            assigned_to_names=entry_data.assigned_to,
        )

    db.commit()
    db.refresh(db_receipt)

    return db_receipt


@app.get("/receipts/{receipt_id}", response_model=schemas.Receipt)
def get_receipt(receipt_id: int, db: SessionDep):
    stmt = select(models.Receipt).where(models.Receipt.id == receipt_id)
    receipt = db.scalars(stmt).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return receipt


@app.patch("/receipts/{receipt_id}", response_model=schemas.Receipt)
def update_receipt(
    receipt_id: int, receipt_update: schemas.ReceiptUpdate, db: SessionDep
):
    """Update receipt details"""
    stmt = select(models.Receipt).where(models.Receipt.id == receipt_id)
    receipt = db.scalars(stmt).first()

    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Update people
    if receipt_update.people is not None:
        receipt.people = crud.get_or_create_people(
            db, receipt.group_id, receipt_update.people
        )

        # If paid_by is no longer in the people list, clear it
        if receipt.paid_by and receipt.paid_by.name not in receipt_update.people:
            receipt.paid_by_id = None

        # Remove any people from entry assigned_to lists who are no longer in receipt people
        for entry in receipt.entries:
            entry.assigned_to = [
                person for person in entry.assigned_to
                if person.name in receipt_update.people
            ]

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
        if receipt_update.paid_by:
            paid_by = crud.get_or_create_person(
                db, receipt.group_id, receipt_update.paid_by
            )
            receipt.paid_by_id = paid_by.id
        else:
            receipt.paid_by_id = None

    db.commit()
    db.refresh(receipt)

    return receipt


@app.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: int, db: SessionDep):
    """Delete a receipt and all its entries (CASCADE)"""
    receipt = db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    db.delete(receipt)
    db.commit()

    return {"message": "Receipt deleted successfully", "id": receipt_id}


# ============================================================================
# Receipt Entry endpoints
# ============================================================================

@app.post("/receipts/{receipt_id}/entries/", response_model=schemas.ReceiptEntry)
def create_receipt_entry(
    receipt_id: int, entry_data: schemas.ReceiptEntryCreate, db: SessionDep
):
    """Create a new entry for a receipt"""
    receipt = db.get(models.Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Use CRUD helper
    db_entry = crud.create_receipt_entry(
        db=db,
        receipt=receipt,
        name=entry_data.name,
        price=entry_data.price,
        taxable=entry_data.taxable,
        assigned_to_names=entry_data.assigned_to,
    )

    db.commit()
    db.refresh(db_entry)

    return db_entry


@app.patch("/receipt-entries/{entry_id}", response_model=schemas.ReceiptEntry)
def update_receipt_entry(
    entry_id: int, update_data: schemas.ReceiptEntryUpdate, db: SessionDep
):
    stmt = select(models.ReceiptEntry).where(models.ReceiptEntry.id == entry_id)
    entry = db.scalars(stmt).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    if update_data.assigned_to is not None:
        entry.assigned_to = crud.get_or_create_people(
            db, entry.receipt.group_id, update_data.assigned_to
        )

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

    return entry


@app.delete("/receipt-entries/{entry_id}")
def delete_receipt_entry(entry_id: int, db: SessionDep):
    """Delete a receipt entry"""
    entry = db.get(models.ReceiptEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Receipt entry not found")

    db.delete(entry)
    db.commit()

    return {"message": "Entry deleted successfully", "id": entry_id}
