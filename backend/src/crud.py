from sqlalchemy.orm import Session
from sqlalchemy import select
from src.models import Person, Receipt, ReceiptEntry, Group


def get_or_create_person(db: Session, name: str, group_id: int) -> Person:
    """
    Get existing person by name in group, or create new one.
    Simple and straightforward - let the database handle constraints.
    """
    stmt = select(Person).where(
        Person.name == name,
        Person.group_id == group_id
    )
    person = db.scalars(stmt).first()
    
    if not person:
        person = Person(name=name, group_id=group_id)
        db.add(person)
        db.flush()  # Get ID without committing
    
    return person


def get_people_by_names(db: Session, names: list[str], group_id: int) -> list[Person]:
    """
    Get or create multiple people by names in a group.
    """
    return [get_or_create_person(db, name, group_id) for name in names]


def create_receipt(
    db: Session,
    group_id: int,
    name: str,
    paid_by_name: str | None = None,
    people_names: list[str] = [],
    processed: bool = False,
    raw_data: str | None = None,
) -> Receipt:
    """
    Create a receipt in a group with people.
    """
    receipt = Receipt(
        name=name,
        group_id=group_id,
        processed=processed,
        raw_data=raw_data,
    )
    
    # Handle paid_by
    if paid_by_name:
        paid_by = get_or_create_person(db, paid_by_name, group_id)
        receipt.paid_by_id = paid_by.id
    
    # Handle people list
    receipt.people = get_people_by_names(db, people_names, group_id)
    
    db.add(receipt)
    db.flush()
    return receipt


def update_receipt_people(
    db: Session,
    receipt: Receipt,
    people_names: list[str]
) -> Receipt:
    """
    Update people associated with a receipt.
    Uses the receipt's group_id automatically.
    """
    receipt.people = get_people_by_names(db, people_names, receipt.group_id)
    return receipt


def update_receipt_paid_by(
    db: Session,
    receipt: Receipt,
    paid_by_name: str | None
) -> Receipt:
    """
    Update who paid for a receipt.
    """
    if paid_by_name:
        paid_by = get_or_create_person(db, paid_by_name, receipt.group_id)
        receipt.paid_by_id = paid_by.id
    else:
        receipt.paid_by_id = None
    return receipt


def create_receipt_entry(
    db: Session,
    receipt: Receipt,
    name: str,
    price: float,
    taxable: bool = True,
    assigned_to_names: list[str] = []
) -> ReceiptEntry:
    """
    Create a receipt entry with assigned people.
    Automatically uses the receipt's group for people lookup.
    """
    entry = ReceiptEntry(
        receipt_id=receipt.id,
        name=name,
        price=price,
        taxable=taxable,
    )
    
    # Assign people (they'll be in the same group as the receipt)
    entry.assigned_to_people = get_people_by_names(db, assigned_to_names, receipt.group_id)
    
    db.add(entry)
    db.flush()
    return entry


def update_entry_assigned_people(
    db: Session,
    entry: ReceiptEntry,
    assigned_to_names: list[str]
) -> ReceiptEntry:
    """
    Update people assigned to a receipt entry.
    Automatically uses the receipt's group.
    """
    # Get the group from the receipt
    group_id = entry.receipt.group_id
    entry.assigned_to_people = get_people_by_names(db, assigned_to_names, group_id)
    return entry


def get_group_people(db: Session, group_id: int) -> list[Person]:
    """
    Get all people in a group.
    """
    stmt = select(Person).where(Person.group_id == group_id).order_by(Person.name)
    return list(db.scalars(stmt).all())


def get_group_receipts(db: Session, group_id: int) -> list[Receipt]:
    """
    Get all receipts in a group.
    """
    stmt = select(Receipt).where(Receipt.group_id == group_id).order_by(Receipt.created_at.desc())
    return list(db.scalars(stmt).all())
