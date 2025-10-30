"""add_updated_at_timestamps

Revision ID: a1b2c3d4e5f6
Revises: 2ab362f00f85
Create Date: 2025-10-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2ab362f00f85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """Add updated_at columns to all tables"""

    # Add updated_at to group_table
    op.add_column('group_table',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # Add updated_at to person_table
    op.add_column('person_table',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # Add updated_at to receipt_table
    op.add_column('receipt_table',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # Add created_at and updated_at to receipt_entry_table
    op.add_column('receipt_entry_table',
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )
    op.add_column('receipt_entry_table',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )


def downgrade():
    """Remove updated_at columns from all tables"""

    # Remove from group_table
    op.drop_column('group_table', 'updated_at')

    # Remove from person_table
    op.drop_column('person_table', 'updated_at')

    # Remove from receipt_table
    op.drop_column('receipt_table', 'updated_at')

    # Remove from receipt_entry_table
    op.drop_column('receipt_entry_table', 'updated_at')
    op.drop_column('receipt_entry_table', 'created_at')
