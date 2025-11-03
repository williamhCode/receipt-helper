from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Table
from sqlalchemy import func, event

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

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
    # don't put selectin for performance reasons
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="Receipt.id",
    )


class Person(Base):
    __tablename__ = "person_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

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
        back_populates="paid_by",
        order_by="Receipt.id"
    )
    
    # Many-to-many: A person can be assigned to many receipt entries
    assigned_entries: Mapped[list["ReceiptEntry"]] = relationship(
        secondary=receipt_entry_person_association, 
        back_populates="assigned_to",
        order_by="ReceiptEntry.id"
    )


class Receipt(Base):
    __tablename__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

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
    
    paid_by: Mapped[Person | None] = relationship(
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
    # don't put selectin for performance reasons
    entries: Mapped[list["ReceiptEntry"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptEntry.id",
    )


class ReceiptEntry(Base):
    __tablename__ = "receipt_entry_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Item details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    taxable: Mapped[bool] = mapped_column(default=True)

    # Foreign key: Entry belongs to ONE receipt
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt_table.id", ondelete="CASCADE"))

    # Relationships
    receipt: Mapped[Receipt] = relationship(back_populates="entries")
    
    # Many-to-many: Entry can be assigned to multiple people (all must be in same group as receipt)
    assigned_to: Mapped[list[Person]] = relationship(
        secondary=receipt_entry_person_association,
        back_populates="assigned_entries",
        order_by="Person.id"
    )


# ============================================================================
# Event listeners to propagate updates to parent Group
# ============================================================================

def touch_group(mapper, connection, target):
    """Update the parent group's updated_at timestamp"""
    if hasattr(target, 'group_id'):
        # For Person
        connection.execute(
            Group.__table__.update()
            .where(Group.id == target.group_id)
            .values(updated_at=func.now())
        )
    elif hasattr(target, 'receipt'):
        # For ReceiptEntry - need to get the receipt's group_id
        # This is handled via Receipt update cascading
        pass


def touch_group_via_receipt(mapper, connection, target):
    """Update the parent group's updated_at timestamp via Receipt"""
    if hasattr(target, 'group_id') and target.group_id:
        connection.execute(
            Group.__table__.update()
            .where(Group.id == target.group_id)
            .values(updated_at=func.now())
        )


# Register event listeners for cascading updates
event.listen(Person, 'after_insert', touch_group)
event.listen(Person, 'after_update', touch_group)
event.listen(Person, 'after_delete', touch_group)

event.listen(Receipt, 'after_insert', touch_group_via_receipt)
event.listen(Receipt, 'after_update', touch_group_via_receipt)
event.listen(Receipt, 'after_delete', touch_group_via_receipt)

# ReceiptEntry updates will trigger both Receipt and Group updated_at
def touch_receipt_and_group_from_entry(mapper, connection, target):
    if hasattr(target, 'receipt_id') and target.receipt_id:
        # First update the receipt
        connection.execute(
            Receipt.__table__.update()
            .where(Receipt.id == target.receipt_id)
            .values(updated_at=func.now())
        )
        # Then update the group (need to get group_id from receipt)
        # Use a subquery to get the group_id from the receipt
        from sqlalchemy import select as sql_select
        connection.execute(
            Group.__table__.update()
            .where(Group.id == sql_select(Receipt.group_id).where(Receipt.id == target.receipt_id).scalar_subquery())
            .values(updated_at=func.now())
        )

event.listen(ReceiptEntry, 'after_insert', touch_receipt_and_group_from_entry)
event.listen(ReceiptEntry, 'after_update', touch_receipt_and_group_from_entry)
event.listen(ReceiptEntry, 'after_delete', touch_receipt_and_group_from_entry)
