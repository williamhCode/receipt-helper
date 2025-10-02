"""add server default to created_at

Revision ID: d72a04dcd52f
Revises: e1f109b22dfe
Create Date: 2025-10-02 17:07:24.853133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd72a04dcd52f'
down_revision: Union[str, Sequence[str], None] = 'e1f109b22dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column('person_table', 'created_at',
                    server_default=sa.text('now()'),
                    nullable=False)
    
    op.alter_column('group_table', 'created_at',
                    server_default=sa.text('now()'),
                    nullable=False)
    
    op.alter_column('receipt_table', 'created_at',
                    server_default=sa.text('now()'),
                    nullable=False)

def downgrade():
    op.alter_column('person_table', 'created_at',
                    server_default=None)
    
    op.alter_column('group_table', 'created_at',
                    server_default=None)
    
    op.alter_column('receipt_table', 'created_at',
                    server_default=None)
