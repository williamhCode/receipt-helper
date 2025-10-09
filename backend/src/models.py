from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Table
from sqlalchemy import func

from datetime import datetime
import base64, uuid


class Base(DeclarativeBase):
    pass


def new_slug() -> str:
    # 16 bytes -> 22-char base64url
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")


receipt_person_association = Table(
    "receipt_person_association",
    Base.metadata,
    Column("receipt_id", ForeignKey("receipt_table.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", ForeignKey("person_table.id", ondelete="CASCADE"), primary_key=True),
)

receipt_entry_person_association = Table(
    "receipt_entry_person_association",
    Base.metadata,
    Column("receipt_entry_id", ForeignKey("receipt_entry_table.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", ForeignKey("person_table.id", ondelete="CASCADE"), primary_key=True),
)


class Group(Base):
    __tablename__ = "group_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    slug: Mapped[str] = mapped_column(
        String(22), unique=True, default=new_slug, index=True
    )
    key_hash: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # One-to-many: A group has many people
    people: Mapped[list["Person"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Person.id"
    )
    
    # One-to-many: A group has many receipts
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Receipt.id"
    )


class Person(Base):
    __tablename__ = "person_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Foreign key: A person belongs to ONE group
    group_id: Mapped[int] = mapped_column(ForeignKey("group_table.id", ondelete="CASCADE"))
    
    # Relationships
    group: Mapped["Group"] = relationship(back_populates="people")
    
    # Many-to-many: A person can be on many receipts (within their group)
    receipts: Mapped[list["Receipt"]] = relationship(
        secondary=receipt_person_association, 
        back_populates="people",
        order_by="Receipt.id"
    )
    
    # One-to-many: A person can be the payer for many receipts
    paid_receipts: Mapped[list["Receipt"]] = relationship(
        "Receipt", 
        foreign_keys="Receipt.paid_by_id", 
        back_populates="paid_by_person",
        order_by="Receipt.id"
    )
    
    # Many-to-many: A person can be assigned to many receipt entries
    assigned_entries: Mapped[list["ReceiptEntry"]] = relationship(
        secondary=receipt_entry_person_association, 
        back_populates="assigned_to_people",
        order_by="ReceiptEntry.id"
    )


class Receipt(Base):
    __tablename__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    processed: Mapped[bool] = mapped_column(default=False)

    # Store the raw receipt data/image
    raw_data: Mapped[str] = mapped_column(Text, nullable=True)

    # Foreign key: Receipt belongs to ONE group
    group_id: Mapped[int] = mapped_column(ForeignKey("group_table.id", ondelete="CASCADE"))
    
    # Foreign key: Who paid for this receipt (must be in same group)
    paid_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person_table.id", ondelete="SET NULL"), 
        nullable=True
    )

    # Relationships
    group: Mapped[Group] = relationship(back_populates="receipts")
    
    paid_by_person: Mapped[Person | None] = relationship(
        "Person", 
        foreign_keys=[paid_by_id], 
        back_populates="paid_receipts"
    )

    # Many-to-many: Receipt can involve multiple people (all must be in same group)
    people: Mapped[list[Person]] = relationship(
        secondary=receipt_person_association, 
        back_populates="receipts",
        order_by="Person.id"
    )

    # One-to-many: Receipt has many entries
    entries: Mapped[list["ReceiptEntry"]] = relationship(
        back_populates="receipt", 
        cascade="all, delete-orphan",
        order_by="ReceiptEntry.id"
    )


class ReceiptEntry(Base):
    __tablename__ = "receipt_entry_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Item details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    taxable: Mapped[bool] = mapped_column(default=True)

    # Foreign key: Entry belongs to ONE receipt
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt_table.id", ondelete="CASCADE"))

    # Relationships
    receipt: Mapped[Receipt] = relationship(back_populates="entries")
    
    # Many-to-many: Entry can be assigned to multiple people (all must be in same group as receipt)
    assigned_to_people: Mapped[list[Person]] = relationship(
        secondary=receipt_entry_person_association, 
        back_populates="assigned_entries",
        order_by="Person.id"
    )
