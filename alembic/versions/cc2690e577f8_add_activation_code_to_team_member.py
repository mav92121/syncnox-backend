"""add_activation_code_to_team_member

Revision ID: cc2690e577f8
Revises: d03473a50a30
Create Date: 2026-05-22 08:27:42.583581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc2690e577f8'
down_revision: Union[str, None] = 'd03473a50a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add activation_code column to team_member table
    op.add_column('team_member', sa.Column('activation_code', sa.String(), nullable=True))
    op.create_index(op.f('ix_team_member_activation_code'), 'team_member', ['activation_code'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_team_member_activation_code'), table_name='team_member')
    op.drop_column('team_member', 'activation_code')
