from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Table

from datetime import datetime, timezone
import base64, uuid


class Base(DeclarativeBase):
    pass


def new_slug() -> str:
    # 16 bytes -> 22-char base64url
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")


# Association table for many-to-many relationship between Group and Person
group_person_association = Table(
    "group_person_association",
    Base.metadata,
    Column("group_id", ForeignKey("group_table.id"), primary_key=True),
    Column("person_id", ForeignKey("person_table.id"), primary_key=True),
)

# Association table for many-to-many relationship between Receipt and Person
receipt_person_association = Table(
    "receipt_person_association",
    Base.metadata,
    Column("receipt_id", ForeignKey("receipt_table.id"), primary_key=True),
    Column("person_id", ForeignKey("person_table.id"), primary_key=True),
)

# Association table for many-to-many relationship between ReceiptEntry and Person
receipt_entry_person_association = Table(
    "receipt_entry_person_association",
    Base.metadata,
    Column("receipt_entry_id", ForeignKey("receipt_entry_table.id"), primary_key=True),
    Column("person_id", ForeignKey("person_table.id"), primary_key=True),
)


class Person(Base):
    __tablename__ = "person_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    groups: Mapped[list["Group"]] = relationship(
        secondary=group_person_association, back_populates="people"
    )
    receipts: Mapped[list["Receipt"]] = relationship(
        secondary=receipt_person_association, back_populates="people"
    )
    paid_receipts: Mapped[list["Receipt"]] = relationship(
        "Receipt", foreign_keys="Receipt.paid_by_id", back_populates="paid_by_person"
    )
    assigned_entries: Mapped[list["ReceiptEntry"]] = relationship(
        secondary=receipt_entry_person_association, back_populates="assigned_to_people"
    )


class Group(Base):
    __tablename__ = "group_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )

    slug: Mapped[str] = mapped_column(
        String(22), unique=True, default=new_slug, index=True
    )
    key_hash: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    people: Mapped[list[Person]] = relationship(
        secondary=group_person_association, back_populates="groups"
    )
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="group")


class Receipt(Base):
    __tablename__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    processed: Mapped[bool] = mapped_column(default=False)

    # Store the raw receipt data/image
    raw_data: Mapped[str] = mapped_column(Text, nullable=True)

    paid_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("person_table.id"), nullable=True
    )
    paid_by_person: Mapped[Person] = relationship(
        "Person", foreign_keys=[paid_by_id], back_populates="paid_receipts"
    )

    people: Mapped[list[Person]] = relationship(
        secondary=receipt_person_association, back_populates="receipts"
    )

    # Parent relationship
    group_id: Mapped[int] = mapped_column(ForeignKey("group_table.id"))
    group: Mapped[Group] = relationship(back_populates="receipts")

    entries: Mapped[list["ReceiptEntry"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptEntry(Base):
    __tablename__ = "receipt_entry_table"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Item details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    taxable: Mapped[bool] = mapped_column(default=True)

    assigned_to_people: Mapped[list[Person]] = relationship(
        secondary=receipt_entry_person_association, back_populates="assigned_entries"
    )

    # Parent relationship
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt_table.id"))
    receipt: Mapped[Receipt] = relationship(back_populates="entries")
