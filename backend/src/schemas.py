from __future__ import annotations
from pydantic import BaseModel
from datetime import datetime


# person -------------------------------------
class PersonBase(BaseModel):
    name: str


class PersonCreate(BaseModel):
    name: str
    # group_id is not included - person is always created within a group context


class PersonResponse(PersonBase):
    id: int
    created_at: datetime
    group_id: int  # Now included to show which group the person belongs to

    class Config:
        from_attributes = True


class PersonUpdate(BaseModel):
    name: str
    # Cannot update group_id - person is permanently tied to their group


# group -------------------------------------
class GroupBase(BaseModel):
    name: str


class GroupCreate(BaseModel):
    name: str | None = None  # Optional - will default to "Group #{id}"
    people: list[str] = []  # Accept list of names, create Person objects in this group


class GroupResponse(GroupBase):
    id: int
    created_at: datetime
    slug: str
    people: list[PersonResponse] = []
    receipts: list[ReceiptResponse] = []

    class Config:
        from_attributes = True


class GroupUpdate(BaseModel):
    name: str | None = None  # Allow updating just the name
    people: list[str] | None = None  # Accept list of names to replace current people


class GroupNameUpdate(BaseModel):
    """Dedicated schema for updating just the group name"""
    name: str


# receipt ---------------------------------------
class ReceiptBase(BaseModel):
    name: str
    processed: bool = False
    raw_data: str | None = None  # Optional raw receipt data


class ReceiptCreate(BaseModel):
    name: str
    processed: bool = False
    raw_data: str | None = None
    paid_by: str | None = None  # Person name - will get or create in group
    people: list[str] = []  # Person names - will get or create in group
    entries: list[ReceiptEntryCreate] = []


class ReceiptResponse(ReceiptBase):
    id: int
    created_at: datetime
    group_id: int
    paid_by: PersonResponse | None = None
    people: list[PersonResponse] = []
    entries: list[ReceiptEntryResponse] = []

    class Config:
        from_attributes = True


class ReceiptUpdate(BaseModel):
    name: str | None = None
    processed: bool | None = None
    paid_by: str | None = None  # Person name
    people: list[str] | None = None  # Person names
    # Note: Cannot change group_id - receipt stays in original group


# receipt entry ---------------------------------------
class ReceiptEntryBase(BaseModel):
    name: str
    price: float
    taxable: bool = True


class ReceiptEntryCreate(BaseModel):
    name: str
    price: float
    taxable: bool = True
    assigned_to: list[str] = []  # Person names


class ReceiptEntryResponse(ReceiptEntryBase):
    id: int
    receipt_id: int
    assigned_to: list[PersonResponse] = []

    class Config:
        from_attributes = True


class ReceiptEntryUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    taxable: bool | None = None
    assigned_to: list[str] | None = None  # Person names


# Build forward references
ReceiptResponse.model_rebuild()
ReceiptEntryResponse.model_rebuild()
GroupResponse.model_rebuild()
