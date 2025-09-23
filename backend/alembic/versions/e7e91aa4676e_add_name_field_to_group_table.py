"""add name field to group table

Revision ID: e7e91aa4676e
Revises: 651ccf0f65b4
Create Date: 2025-09-23 11:30:50.144804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7e91aa4676e'
down_revision: Union[str, Sequence[str], None] = '651ccf0f65b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the name column to group_table
    op.add_column('group_table', sa.Column('name', sa.String(length=255), nullable=False, server_default=''))
    
    # Update existing groups to have default names
    # This uses raw SQL to set the name based on the id
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE group_table SET name = 'Group #' || id WHERE name = ''")
    )


def downgrade() -> None:
    # Remove the name column
    op.drop_column('group_table', 'name')
