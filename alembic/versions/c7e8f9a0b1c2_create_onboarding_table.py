"""create_onboarding_table

Revision ID: c7e8f9a0b1c2
Revises: 86509b23d0f0
Create Date: 2026-01-02 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e8f9a0b1c2'
down_revision: Union[str, None] = '86509b23d0f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create onboarding table for tracking tenant onboarding progress."""
    op.create_table(
        'onboarding',
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenant.id'), primary_key=True),
        sa.Column('is_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('current_step', sa.Integer(), nullable=False, default=0),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Drop onboarding table."""
    op.drop_table('onboarding')
