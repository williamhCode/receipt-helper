from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime


# group -------------------------------------
class GroupBase(BaseModel):
    people: list[str]


class GroupCreate(GroupBase):
    pass


class GroupResponse(GroupBase):
    id: int
    created_at: datetime
    slug: str
    receipts: list[ReceiptResponse] = []

    class Config:
        from_attributes = True


# receipt ---------------------------------------
class ReceiptBase(BaseModel):
    processed: bool = False
    name: str
    raw_data: str | None = None  # Optional raw receipt data
    paid_by: str | None = None  # Who paid for this receipt
    people: list[str] = []  # Receipt-specific people list


class ReceiptCreate(ReceiptBase):
    entries: list[ReceiptEntryCreate] = []


class ReceiptResponse(ReceiptBase):
    id: int
    created_at: datetime
    group_id: int
    entries: list[ReceiptEntryResponse] = []

    class Config:
        from_attributes = True


class ReceiptUpdate(BaseModel):
    people: list[str]


class GroupUpdate(BaseModel):
    people: list[str]


# receipt entry ---------------------------------------
class ReceiptEntryBase(BaseModel):
    name: str
    price: float
    taxable: bool = True
    assigned_to: list[str] = []


class ReceiptEntryCreate(ReceiptEntryBase):
    pass


class ReceiptEntryResponse(ReceiptEntryBase):
    id: int
    receipt_id: int

    class Config:
        from_attributes = True


# build models
ReceiptResponse.model_rebuild()
ReceiptEntryResponse.model_rebuild()
