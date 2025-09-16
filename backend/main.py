from typing import Annotated

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import Base, Group, Receipt, ReceiptEntry
from .schemas import GroupCreate, GroupResponse, ReceiptCreate, ReceiptResponse

# fastapi app -------------------------------------------------
app = FastAPI(title="Reciept Helper", version="0.0.1")

# Add CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# database setup -----------------------------------------------
db_url = "sqlite:///./reciept-helper.db"
engine = create_engine(db_url, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# dependency --------------------------------------------------
def get_session():
    with Session() as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]


# endpoints ---------------------------------------------------
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


# Receipts endpoints
@app.post("/groups/{group_id}/receipts/", response_model=ReceiptResponse)
def create_receipt(group_id: int, receipt: ReceiptCreate, db: SessionDep):
    # Verify group exists
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db_receipt = Receipt(
        group_id=group_id, processed=receipt.processed, raw_data=receipt.raw_data
    )
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    # Add entries if provided
    if receipt.entries:
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


@app.get("/groups/{group_id}/receipts/", response_model=list[ReceiptResponse])
def list_group_receipts(group_id: int, db: SessionDep):
    return db.query(Receipt).filter(Receipt.group_id == group_id).all()


# Test endpoint
@app.get("/")
def root():
    return {"message": "Receipt Helper API"}


# Create some sample data
@app.post("/create-sample-data")
def create_sample_data(db: SessionDep):
    # Create a sample group
    group = Group(people=["William", "Hao", "Howard"], key_hash="sample_hash")
    db.add(group)
    db.commit()
    db.refresh(group)

    # Create a sample receipt
    receipt = Receipt(
        group_id=group.id, processed=True, raw_data="Sample grocery receipt"
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Add some sample entries
    sample_items = [
        ("Apples", 3.99, True),
        ("Bananas", 2.50, True),
        ("Bread", 2.99, False),
        ("Milk", 4.25, False),
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

    db.commit()
    return {
        "message": "Sample data created",
        "group_id": group.id,
        "receipt_id": receipt.id,
    }
