from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime


# person -------------------------------------
class PersonBase(BaseModel):
    name: str


class PersonCreate(PersonBase):
    pass


class PersonResponse(PersonBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PersonUpdate(BaseModel):
    name: str


# group -------------------------------------
class GroupBase(BaseModel):
    name: str
    people: list[PersonResponse]


class GroupCreate(BaseModel):
    people: list[str]  # Accept list of names, convert to Person objects
    # name is optional in creation - will default to "Group #{id}"


class GroupResponse(GroupBase):
    id: int
    created_at: datetime
    slug: str
    receipts: list[ReceiptResponse] = []

    class Config:
        from_attributes = True


class GroupUpdate(BaseModel):
    people: list[str] | None = None  # Accept list of names
    name: str | None = None  # Allow updating just the name


# NEW: Dedicated schema for updating just the group name
class GroupNameUpdate(BaseModel):
    name: str


# receipt ---------------------------------------
class ReceiptBase(BaseModel):
    processed: bool = False
    name: str
    raw_data: str | None = None  # Optional raw receipt data
    paid_by: PersonResponse | None = None  # Who paid for this receipt
    people: list[PersonResponse] = []  # Receipt-specific people list


class ReceiptCreate(BaseModel):
    processed: bool = False
    name: str
    raw_data: str | None = None
    paid_by: str | None = None  # Accept person name, convert to Person object
    people: list[str] = []  # Accept list of names, convert to Person objects
    entries: list[ReceiptEntryCreate] = []


class ReceiptResponse(ReceiptBase):
    id: int
    created_at: datetime
    group_id: int
    entries: list[ReceiptEntryResponse] = []

    class Config:
        from_attributes = True


class ReceiptUpdate(BaseModel):
    people: list[str] | None = None  # Accept list of names
    processed: bool | None = None
    paid_by: str | None = None


# receipt entry ---------------------------------------
class ReceiptEntryBase(BaseModel):
    name: str
    price: float
    taxable: bool = True
    assigned_to: list[PersonResponse] = []


class ReceiptEntryCreate(BaseModel):
    name: str
    price: float
    taxable: bool = True
    assigned_to: list[str] = []


class ReceiptEntryResponse(ReceiptEntryBase):
    id: int
    receipt_id: int

    class Config:
        from_attributes = True


class ReceiptEntryUpdate(BaseModel):
    assigned_to: list[str] | None = None
    name: str | None = None
    price: float | None = None
    taxable: bool | None = None


# build models
ReceiptResponse.model_rebuild()
ReceiptEntryResponse.model_rebuild()
GroupResponse.model_rebuild()
