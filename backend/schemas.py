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


# reciept ---------------------------------------
class ReceiptBase(BaseModel):
    processed: bool = False
    raw_data: str | None = None


class ReceiptCreate(ReceiptBase):
    entries: list[ReceiptEntryCreate] | None = []


class ReceiptResponse(ReceiptBase):
    id: int
    created_at: datetime
    group_id: int
    entries: list[ReceiptEntryResponse] = []

    class Config:
        from_attributes = True


# reciept entry ---------------------------------------
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
# ReceiptResponse.update_forward_refs()
ReceiptResponse.model_rebuild();
ReceiptEntryResponse.model_rebuild();
