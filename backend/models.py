from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text

from datetime import datetime, timezone
import base64, uuid


class Base(DeclarativeBase):
    pass


def new_slug() -> str:
    # 16 bytes -> 22-char base64url
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")


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

    people: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="group")


class Receipt(Base):
    __tablename__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )

    processed: Mapped[bool] = mapped_column(default=False)

    # Store the raw receipt data/image
    raw_data: Mapped[str] = mapped_column(Text, nullable=True)

    # parent
    group_id: Mapped[int] = mapped_column(ForeignKey("group_table.id"))
    group: Mapped[Group] = relationship(back_populates="receipts")

    # Receipt entries
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
    
    # Who is responsible for this item (JSON array of person names)
    assigned_to: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    # Parent relationship
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipt_table.id"))
    receipt: Mapped[Receipt] = relationship(back_populates="entries")
