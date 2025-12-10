"""Add cascade delete to route_stop job_id foreign key

Revision ID: a8629e4ad8cf
Revises: 4b6585c28191
Create Date: 2025-12-10 19:23:55.315743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8629e4ad8cf'
down_revision: Union[str, None] = '4b6585c28191'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing foreign key constraint
    op.drop_constraint('route_stop_job_id_fkey', 'route_stop', type_='foreignkey')
    
    # Recreate the foreign key constraint with CASCADE delete
    op.create_foreign_key(
        'route_stop_job_id_fkey',
        'route_stop',
        'job',
        ['job_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop the CASCADE foreign key constraint
    op.drop_constraint('route_stop_job_id_fkey', 'route_stop', type_='foreignkey')
    
    # Recreate the original foreign key constraint without CASCADE
    op.create_foreign_key(
        'route_stop_job_id_fkey',
        'route_stop',
        'job',
        ['job_id'],
        ['id']
    )
