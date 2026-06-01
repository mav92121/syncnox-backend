"""add_route_assignment_table

Revision ID: 7a1c10c86aaa
Revises: cc2690e577f8
Create Date: 2026-05-23 08:41:33.592607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a1c10c86aaa'
down_revision: Union[str, None] = 'cc2690e577f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'route_assignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('route_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'acknowledged', 'in_progress', 'completed', name='routeassignmentstatus'), nullable=False),
        sa.Column('shared_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['team_member.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['route_id'], ['route.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('route_id', 'driver_id', name='uq_route_assignment_route_driver'),
    )
    op.create_index(op.f('ix_route_assignment_driver_id'), 'route_assignment', ['driver_id'], unique=False)
    op.create_index(op.f('ix_route_assignment_id'), 'route_assignment', ['id'], unique=False)
    op.create_index(op.f('ix_route_assignment_route_id'), 'route_assignment', ['route_id'], unique=False)
    op.create_index(op.f('ix_route_assignment_status'), 'route_assignment', ['status'], unique=False)
    op.create_index(op.f('ix_route_assignment_tenant_id'), 'route_assignment', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_route_assignment_tenant_id'), table_name='route_assignment')
    op.drop_index(op.f('ix_route_assignment_status'), table_name='route_assignment')
    op.drop_index(op.f('ix_route_assignment_route_id'), table_name='route_assignment')
    op.drop_index(op.f('ix_route_assignment_id'), table_name='route_assignment')
    op.drop_index(op.f('ix_route_assignment_driver_id'), table_name='route_assignment')
    op.drop_table('route_assignment')
    op.execute("DROP TYPE IF EXISTS routeassignmentstatus")
