"""update_route_status_enum

Revision ID: de9170b8beda
Revises: 9e69c61d4d01
Create Date: 2025-12-22 22:27:25.398962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de9170b8beda'
down_revision: Union[str, None] = '9e69c61d4d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update existing data: 'planned' -> 'scheduled' to ensure clean conversion
    op.execute("UPDATE route SET status = 'scheduled' WHERE status = 'planned'")
    
    # 2. Update any other statuses that might not be in the enum to null or a default
    # For now assuming other statuses are valid or null.
    
    # 3. Create Enum type
    route_status = sa.Enum('scheduled', 'in_transit', 'completed', 'failed', 'processing', name='routestatus')
    route_status.create(op.get_bind())
    
    # 4. Alter column
    op.alter_column(
        'route', 
        'status', 
        existing_type=sa.String(),
        type_=route_status,
        postgresql_using='status::routestatus',
        nullable=True,
        server_default='scheduled'
    )


def downgrade() -> None:
    # 1. Alter column back to String
    op.alter_column(
        'route', 
        'status', 
        existing_type=sa.Enum('scheduled', 'in_transit', 'completed', 'failed', 'processing', name='routestatus'),
        type_=sa.String(),
        nullable=True
    )
    
    # 2. Drop Enum type
    route_status = sa.Enum('scheduled', 'in_transit', 'completed', 'failed', 'processing', name='routestatus')
    route_status.drop(op.get_bind())
