from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey


class Base(DeclarativeBase):
    pass


def new_slug() -> str:
    # 16 bytes -> 22-char base64url
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")


class Group(Base):
    __tablename__ = "group_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[DateTime] = mapped_column()

    slug: Mapped[str] = mapped_column(
        String(22), unique=True, default=new_slug, index=True
    )
    key_hash: Mapped[str] = mapped_column(nullable=False)

    people: Mapped[list[str]] = mapped_column(nullable=False, unique=True)
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="group")


class Receipt(Base):
    __tablename__ = "receipt_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[DateTime] = mapped_column()

    processed: Mapped[bool] = mapped_column()

    people: Mapped[list["Receipt"]] = relationship(back_populates="group")

    # parent
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id"))
    group: Mapped[Group] = relationship(back_populates="receipts")
