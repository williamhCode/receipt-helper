from typing import Annotated

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import Base, Group, Receipt, ReceiptEntry
from .schemas import (
    GroupCreate, 
    GroupResponse, 
    GroupUpdate, 
    ReceiptCreate, 
    ReceiptResponse, 
    ReceiptUpdate
)

# fastapi app -------------------------------------------------
app = FastAPI(title="Receipt Helper", version="0.0.1")

# Add CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# database setup -----------------------------------------------
db_url = "sqlite:///./receipt-helper.db"
engine = create_engine(db_url, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
# Base.metadata.create_all(bind=engine)

# dependency --------------------------------------------------
def get_session():
    with Session() as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]


# endpoints ---------------------------------------------------

# Root endpoint
@app.get("/")
def root():
    return {"message": "Receipt Helper API"}

# Group endpoints
@app.post("/groups/", response_model=GroupResponse)
def create_group(group: GroupCreate, db: SessionDep):
    db_group = Group(
        people=group.people,
        key_hash="placeholder_hash",  # You'll want to implement proper hashing
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@app.get("/groups/", response_model=list[GroupResponse])
def list_groups(db: SessionDep):
    return db.query(Group).all()

@app.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: SessionDep):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@app.patch("/groups/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, group_update: GroupUpdate, db: SessionDep):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.people = group_update.people
    db.commit()
    db.refresh(group)
    return group

# Receipt endpoints
@app.post("/groups/{group_id}/receipts/", response_model=ReceiptResponse)
def create_receipt(group_id: int, receipt: ReceiptCreate, db: SessionDep):
    # Verify group exists
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db_receipt = Receipt(
        group_id=group_id, 
        processed=receipt.processed, 
        name=receipt.name,  # Use the new name field
        raw_data=receipt.raw_data,  # Optional raw data
        paid_by=receipt.paid_by,
        people=receipt.people
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    # Add entries if provided
    for entry_data in receipt.entries:
        db_entry = ReceiptEntry(
            receipt_id=db_receipt.id,
            name=entry_data.name,
            price=entry_data.price,
            taxable=entry_data.taxable,
            assigned_to=entry_data.assigned_to or [],
        )
        db.add(db_entry)
    db.commit()

    db.refresh(db_receipt)
    return db_receipt

@app.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
def get_receipt(receipt_id: int, db: SessionDep):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt

@app.patch("/receipts/{receipt_id}", response_model=ReceiptResponse)
def update_receipt(receipt_id: int, receipt_update: ReceiptUpdate, db: SessionDep):
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    receipt.people = receipt_update.people
    db.commit()
    db.refresh(receipt)
    return receipt

@app.get("/groups/{group_id}/receipts/", response_model=list[ReceiptResponse])
def list_group_receipts(group_id: int, db: SessionDep):
    return db.query(Receipt).filter(Receipt.group_id == group_id).all()

# Sample data endpoint
@app.post("/create-sample-data")
def create_sample_data(db: SessionDep):
    # Create a sample group
    group = Group(
        people=["William", "Hao", "Howard"], 
        key_hash="sample_hash"
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Create sample receipts with proper names
    sample_receipts = [
        {
            "name": "Whole Foods Market",
            "raw_data": "Grocery shopping receipt with organic produce",
            "paid_by": "William"
        },
        {
            "name": "Starbucks Coffee",
            "raw_data": "Coffee and pastries for the team",
            "paid_by": "Hao"
        },
        {
            "name": "Pizza Palace",
            "raw_data": "Team lunch - large pepperoni pizza",
            "paid_by": "Howard"
        }
    ]

    for receipt_data in sample_receipts:
        receipt = Receipt(
            group_id=group.id, 
            processed=True, 
            name=receipt_data["name"],  # Use proper name
            raw_data=receipt_data["raw_data"],  # Optional additional data
            paid_by=receipt_data["paid_by"],
            people=["William", "Hao", "Howard"]  # Include all group members
        )
        db.add(receipt)
        db.commit()
        db.refresh(receipt)

        # Add some sample entries for the first receipt
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
                    assigned_to=[],  # No one assigned initially
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
                    assigned_to=[],
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
                    assigned_to=[],
                )
                db.add(entry)

    db.commit()
    return {
        "message": "Sample data created with proper receipt names",
        "group_id": group.id,
        "receipts_created": len(sample_receipts),
    }
