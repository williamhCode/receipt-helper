"""group_isolation

Revision ID: 2ab362f00f85
Revises: d72a04dcd52f
Create Date: 2025-10-08 19:34:03.373944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '2ab362f00f85'
down_revision: Union[str, Sequence[str], None] = 'd72a04dcd52f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    """
    Migrate from many-to-many (group_person_association) to one-to-many (person.group_id)
    """
    
    # Step 1: Add group_id column to person_table (nullable for now)
    op.add_column('person_table', 
        sa.Column('group_id', sa.Integer(), nullable=True)
    )
    
    # Step 2: Migrate data from group_person_association to person.group_id
    # For people in multiple groups, keep only the first group (lowest group_id)
    connection = op.get_bind()
    
    # Get distinct person_id -> group_id mappings (first group per person)
    result = connection.execute(text("""
        SELECT DISTINCT ON (person_id) person_id, group_id 
        FROM group_person_association 
        ORDER BY person_id, group_id
    """))
    
    # Update each person with their group_id
    for row in result:
        connection.execute(
            text("UPDATE person_table SET group_id = :group_id WHERE id = :person_id"),
            {"group_id": row.group_id, "person_id": row.person_id}
        )
    
    # Step 2.5: Handle orphaned people (not in any group)
    # Option 1: Delete them (safer - no orphaned data)
    connection.execute(text("""
        DELETE FROM person_table 
        WHERE group_id IS NULL
    """))
    
    # Option 2: If you want to keep them, assign to first available group instead:
    # first_group = connection.execute(text("SELECT id FROM group_table ORDER BY id LIMIT 1")).scalar()
    # if first_group:
    #     connection.execute(text(f"UPDATE person_table SET group_id = {first_group} WHERE group_id IS NULL"))
    
    # Step 3: Make group_id NOT NULL and add foreign key constraint
    op.alter_column('person_table', 'group_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    
    op.create_foreign_key(
        'fk_person_group',
        'person_table', 'group_table',
        ['group_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Step 4: Create index on group_id for query performance
    op.create_index('ix_person_group_id', 'person_table', ['group_id'])
    
    # Step 5: Drop the old many-to-many association table
    op.drop_table('group_person_association')
    
    # Step 6: Update foreign key constraints to add CASCADE deletes
    
    # Receipt -> Group
    op.drop_constraint('receipt_table_group_id_fkey', 'receipt_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_table_group_id_fkey',
        'receipt_table', 'group_table',
        ['group_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Receipt -> Person (paid_by)
    op.drop_constraint('receipt_table_paid_by_id_fkey', 'receipt_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_table_paid_by_id_fkey',
        'receipt_table', 'person_table',
        ['paid_by_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # ReceiptEntry -> Receipt
    op.drop_constraint('receipt_entry_table_receipt_id_fkey', 'receipt_entry_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_entry_table_receipt_id_fkey',
        'receipt_entry_table', 'receipt_table',
        ['receipt_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Update association table foreign keys to add CASCADE
    # receipt_person_association
    op.drop_constraint('receipt_person_association_receipt_id_fkey', 'receipt_person_association', type_='foreignkey')
    op.drop_constraint('receipt_person_association_person_id_fkey', 'receipt_person_association', type_='foreignkey')
    
    op.create_foreign_key(
        'receipt_person_association_receipt_id_fkey',
        'receipt_person_association', 'receipt_table',
        ['receipt_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'receipt_person_association_person_id_fkey',
        'receipt_person_association', 'person_table',
        ['person_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # receipt_entry_person_association
    op.drop_constraint('receipt_entry_person_association_receipt_entry_id_fkey', 'receipt_entry_person_association', type_='foreignkey')
    op.drop_constraint('receipt_entry_person_association_person_id_fkey', 'receipt_entry_person_association', type_='foreignkey')
    
    op.create_foreign_key(
        'receipt_entry_person_association_receipt_entry_id_fkey',
        'receipt_entry_person_association', 'receipt_entry_table',
        ['receipt_entry_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'receipt_entry_person_association_person_id_fkey',
        'receipt_entry_person_association', 'person_table',
        ['person_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    """
    Rollback: Restore many-to-many relationship
    """
    
    # Step 1: Recreate group_person_association table
    op.create_table(
        'group_person_association',
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group_table.id']),
        sa.ForeignKeyConstraint(['person_id'], ['person_table.id']),
        sa.PrimaryKeyConstraint('group_id', 'person_id')
    )
    
    # Step 2: Migrate data back from person.group_id to group_person_association
    connection = op.get_bind()
    result = connection.execute(text("SELECT id, group_id FROM person_table"))
    
    for row in result:
        connection.execute(
            text("INSERT INTO group_person_association (person_id, group_id) VALUES (:person_id, :group_id)"),
            {"person_id": row.id, "group_id": row.group_id}
        )
    
    # Step 3: Drop foreign key and index
    op.drop_constraint('fk_person_group', 'person_table', type_='foreignkey')
    op.drop_index('ix_person_group_id', 'person_table')
    
    # Step 4: Remove group_id column
    op.drop_column('person_table', 'group_id')
    
    # Step 5: Revert CASCADE changes (optional - could leave them as CASCADE)
    # Receipt -> Group
    op.drop_constraint('receipt_table_group_id_fkey', 'receipt_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_table_group_id_fkey',
        'receipt_table', 'group_table',
        ['group_id'], ['id']
    )
    
    # Receipt -> Person (paid_by)
    op.drop_constraint('receipt_table_paid_by_id_fkey', 'receipt_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_table_paid_by_id_fkey',
        'receipt_table', 'person_table',
        ['paid_by_id'], ['id']
    )
    
    # ReceiptEntry -> Receipt
    op.drop_constraint('receipt_entry_table_receipt_id_fkey', 'receipt_entry_table', type_='foreignkey')
    op.create_foreign_key(
        'receipt_entry_table_receipt_id_fkey',
        'receipt_entry_table', 'receipt_table',
        ['receipt_id'], ['id']
    )
    
    # Association tables
    op.drop_constraint('receipt_person_association_receipt_id_fkey', 'receipt_person_association', type_='foreignkey')
    op.drop_constraint('receipt_person_association_person_id_fkey', 'receipt_person_association', type_='foreignkey')
    
    op.create_foreign_key(
        'receipt_person_association_receipt_id_fkey',
        'receipt_person_association', 'receipt_table',
        ['receipt_id'], ['id']
    )
    op.create_foreign_key(
        'receipt_person_association_person_id_fkey',
        'receipt_person_association', 'person_table',
        ['person_id'], ['id']
    )
    
    op.drop_constraint('receipt_entry_person_association_receipt_entry_id_fkey', 'receipt_entry_person_association', type_='foreignkey')
    op.drop_constraint('receipt_entry_person_association_person_id_fkey', 'receipt_entry_person_association', type_='foreignkey')
    
    op.create_foreign_key(
        'receipt_entry_person_association_receipt_entry_id_fkey',
        'receipt_entry_person_association', 'receipt_entry_table',
        ['receipt_entry_id'], ['id']
    )
    op.create_foreign_key(
        'receipt_entry_person_association_person_id_fkey',
        'receipt_entry_person_association', 'person_table',
        ['person_id'], ['id']
    )
