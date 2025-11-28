"""add_performance_indexes

Revision ID: a1b2c3d4e5f6
Revises: faab831d84ab
Create Date: 2025-11-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'faab831d84ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes for commonly queried columns.
    
    These indexes significantly improve query performance for tenant-scoped
    queries and lookups.
    """
    # Team member indexes
    op.create_index('ix_team_member_tenant_id', 'team_member', ['tenant_id'])
    op.create_index('ix_team_member_email_tenant', 'team_member', ['email', 'tenant_id'])
    
    # Job indexes
    op.create_index('ix_job_tenant_id', 'job', ['tenant_id'])
    op.create_index('ix_job_tenant_scheduled', 'job', ['tenant_id', 'scheduled_date'])
    op.create_index('ix_job_status_tenant', 'job', ['status', 'tenant_id'])
    
    # Vehicle indexes
    op.create_index('ix_vehicle_tenant_id', 'vehicle', ['tenant_id'])
    
    # Depot indexes
    op.create_index('ix_depot_tenant_id', 'depot', ['tenant_id'])
    
    # Route indexes
    op.create_index('ix_route_tenant_id', 'route', ['tenant_id'])
    op.create_index('ix_route_stop_route_id', 'route_stop', ['route_id'])


def downgrade() -> None:
    """Remove performance indexes."""
    # Team member indexes
    op.drop_index('ix_team_member_tenant_id')
    op.drop_index('ix_team_member_email_tenant')
    
    # Job indexes
    op.drop_index('ix_job_tenant_id')
    op.drop_index('ix_job_tenant_scheduled')
    op.drop_index('ix_job_status_tenant')
    
    # Vehicle indexes
    op.drop_index('ix_vehicle_tenant_id')
    
    # Depot indexes
    op.drop_index('ix_depot_tenant_id')
    
    # Route indexes
    op.drop_index('ix_route_tenant_id')
    op.drop_index('ix_route_stop_route_id')
