from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models import Person, Receipt, ReceiptEntry, Group


async def get_or_create_person(db: AsyncSession, group_id: int, name: str):
    stmt = select(Person).where(
        Person.name == name,
        Person.group_id == group_id
    )
    result = await db.execute(stmt)
    person = result.scalars().first()
    
    if not person:
        person = Person(name=name, group_id=group_id)
        db.add(person)
        await db.flush()
    
    return person


async def get_or_create_people(db: AsyncSession, group_id: int, names: list[str]) -> list[Person]:
    if not names:
        return []

    # Fetch all existing people with these names in this group
    stmt = select(Person).where(
        Person.group_id == group_id,
        Person.name.in_(names)
    )
    result = await db.execute(stmt)
    existing_people = {person.name: person for person in result.scalars().all()}

    people = []
    for name in names:
        person = existing_people.get(name)
        if person is not None:
            people.append(person)
        else:
            new_person = Person(name=name, group_id=group_id)
            db.add(new_person)
            people.append(new_person)

    if people:
        await db.flush()

    return people


async def create_receipt(
    db: AsyncSession,
    group_id: int,
    name: str,
    paid_by_name: str | None = None,
    people_names: list[str] = [],
    processed: bool = False,
    raw_data: str | None = None,
) -> Receipt:

    receipt = Receipt(
        name=name,
        group_id=group_id,
        processed=processed,
        raw_data=raw_data,
    )

    if paid_by_name:
        paid_by = await get_or_create_person(db, group_id, paid_by_name)
        receipt.paid_by_id = paid_by.id

    receipt.people = await get_or_create_people(db, group_id, people_names)

    db.add(receipt)
    await db.flush()
    return receipt


async def create_receipt_entry(
    db: AsyncSession,
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
    entry.assigned_to_people = await get_or_create_people(db, receipt.group_id, assigned_to_names)

    db.add(entry)
    await db.flush()
    return entry


async def update_entry_assigned_people(
    db: AsyncSession,
    entry: ReceiptEntry,
    assigned_to_names: list[str]
) -> ReceiptEntry:
    """
    Update people assigned to a receipt entry.
    Automatically uses the receipt's group.
    """
    # Get the group from the receipt
    group_id = entry.receipt.group_id
    entry.assigned_to_people = await get_or_create_people(db, group_id, assigned_to_names)
    return entry


async def update_receipt_people(
    db: AsyncSession,
    receipt: Receipt,
    people_names: list[str]
) -> Receipt:
    """
    Update people associated with a receipt.
    Uses the receipt's group_id automatically.
    """
    receipt.people = await get_or_create_people(db, receipt.group_id, people_names)
    return receipt


async def update_receipt_paid_by(
    db: AsyncSession,
    receipt: Receipt,
    paid_by_name: str | None
) -> Receipt:
    """
    Update who paid for a receipt.
    """
    if paid_by_name:
        paid_by = await get_or_create_person(db, receipt.group_id, paid_by_name)
        receipt.paid_by_id = paid_by.id
    else:
        receipt.paid_by_id = None
    return receipt
