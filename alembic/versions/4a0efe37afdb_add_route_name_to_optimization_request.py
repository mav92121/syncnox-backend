"""add_route_name_to_optimization_request

Revision ID: 4a0efe37afdb
Revises: 892a6a122040
Create Date: 2025-12-01 19:11:54.068291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a0efe37afdb'
down_revision: Union[str, None] = '892a6a122040'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add route_name column to optimization_request table
    op.add_column('optimization_request', sa.Column('route_name', sa.String(), nullable=False, server_default='Unnamed Route'))
    # Remove server_default after adding the column (it was only needed for existing rows)
    op.alter_column('optimization_request', 'route_name', server_default=None)
    # Add index for route_name
    op.create_index(op.f('ix_optimization_request_route_name'), 'optimization_request', ['route_name'], unique=False)


def downgrade() -> None:
    # Remove index and column
    op.drop_index(op.f('ix_optimization_request_route_name'), table_name='optimization_request')
    op.drop_column('optimization_request', 'route_name')
