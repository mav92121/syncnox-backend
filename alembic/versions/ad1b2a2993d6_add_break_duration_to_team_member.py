"""add_break_duration_to_team_member

Revision ID: ad1b2a2993d6
Revises: 97c05195d429
Create Date: 2026-01-13 10:50:18.685584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ad1b2a2993d6'
down_revision: Union[str, None] = '97c05195d429'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add break_duration column to team_member table."""
    op.add_column('team_member', sa.Column('break_duration', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove break_duration column from team_member table."""
    op.drop_column('team_member', 'break_duration')

