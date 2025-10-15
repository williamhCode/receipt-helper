from __future__ import annotations
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from . import models


# person -------------------------------------
class PersonCreate(BaseModel):
    name: str


class Person(BaseModel):
    id: int
    created_at: datetime
    name: str
    group_id: int

    model_config = ConfigDict(from_attributes=True)


class PersonUpdate(BaseModel):
    name: str


# group -------------------------------------
class GroupBase(BaseModel):
    name: str


class GroupCreate(BaseModel):
    name: str | None = None
    people: list[str] = []


class Group(GroupBase):
    id: int
    created_at: datetime
    slug: str
    people: list[str] = []
    receipts: list[Receipt] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator("people", mode="before")
    @classmethod
    def convert_people_to_names(cls, v):
        if v and isinstance(v[0], models.Person):
            return [person.name for person in v]
        return v


class GroupUpdate(BaseModel):
    name: str | None = None
    people: list[str] | None = None


# receipt ---------------------------------------
class ReceiptBase(BaseModel):
    name: str
    processed: bool = False
    raw_data: str | None = None


class ReceiptCreate(BaseModel):
    name: str
    processed: bool = False
    raw_data: str | None = None
    paid_by: str | None = None
    people: list[str] = []
    entries: list[ReceiptEntryCreate] = []

    @field_validator("people", mode="before")
    @classmethod
    def convert_people_to_names(cls, v):
        if v and isinstance(v[0], models.Person):
            return [person.name for person in v]
        return v

    @field_validator("paid_by", mode="before")
    @classmethod
    def convert_paid_by_to_name(cls, v):
        # Here 'v' is a single SQLAlchemy Person object, not a list
        if isinstance(v, models.Person):
            return v.name
        return v


class Receipt(ReceiptBase):
    id: int
    created_at: datetime
    group_id: int
    paid_by: str | None = None
    people: list[str] = []
    entries: list[ReceiptEntry] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator("people", mode="before")
    @classmethod
    def convert_people_to_names(cls, v):
        if v and isinstance(v[0], models.Person):
            return [person.name for person in v]
        return v


class ReceiptUpdate(BaseModel):
    name: str | None = None
    processed: bool | None = None
    paid_by: str | None = None
    people: list[str] | None = None


# receipt entry ---------------------------------------
class ReceiptEntryBase(BaseModel):
    name: str
    price: float
    taxable: bool = True


class ReceiptEntryCreate(BaseModel):
    name: str
    price: float
    taxable: bool = True
    assigned_to: list[str] = []


class ReceiptEntry(ReceiptEntryBase):
    id: int
    receipt_id: int
    assigned_to: list[str] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator("assigned_to", mode="before")
    def convert_people_to_names(cls, v):
        if v and isinstance(v[0], models.Person):
            return [person.name for person in v]
        return v


class ReceiptEntryUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    taxable: bool | None = None
    assigned_to: list[str] | None = None  # Person names


# Build forward references
Receipt.model_rebuild()
ReceiptEntry.model_rebuild()
Group.model_rebuild()
