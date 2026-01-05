"""add_cascade_delete_to_foreign_keys

Revision ID: 97c05195d429
Revises: c7e8f9a0b1c2
Create Date: 2026-01-05 14:34:30.521531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97c05195d429'
down_revision: Union[str, None] = 'c7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CASCADE and SET NULL to foreign key constraints."""
    
    # depot: tenant_id -> CASCADE
    op.drop_constraint('depot_tenant_id_fkey', 'depot', type_='foreignkey')
    op.create_foreign_key('depot_tenant_id_fkey', 'depot', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # job: tenant_id -> CASCADE, assigned_to -> SET NULL, route_id -> SET NULL
    op.drop_constraint('job_assigned_to_fkey', 'job', type_='foreignkey')
    op.drop_constraint('job_tenant_id_fkey', 'job', type_='foreignkey')
    op.drop_constraint('job_route_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_route_id_fkey', 'job', 'route', ['route_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('job_tenant_id_fkey', 'job', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('job_assigned_to_fkey', 'job', 'team_member', ['assigned_to'], ['id'], ondelete='SET NULL')
    
    # optimization_request: tenant_id -> CASCADE, depot_id -> SET NULL
    op.drop_constraint('optimization_request_depot_id_fkey', 'optimization_request', type_='foreignkey')
    op.drop_constraint('optimization_request_tenant_id_fkey', 'optimization_request', type_='foreignkey')
    op.create_foreign_key('optimization_request_depot_id_fkey', 'optimization_request', 'depot', ['depot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('optimization_request_tenant_id_fkey', 'optimization_request', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # route: tenant_id -> CASCADE, driver_id/vehicle_id/depot_id -> SET NULL, optimization_request_id -> CASCADE
    op.drop_constraint('route_tenant_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_driver_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_depot_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_vehicle_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_optimization_request_id_fkey', 'route', type_='foreignkey')
    op.create_foreign_key('route_tenant_id_fkey', 'route', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('route_vehicle_id_fkey', 'route', 'vehicle', ['vehicle_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('route_optimization_request_id_fkey', 'route', 'optimization_request', ['optimization_request_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('route_depot_id_fkey', 'route', 'depot', ['depot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('route_driver_id_fkey', 'route', 'team_member', ['driver_id'], ['id'], ondelete='SET NULL')
    
    # route_stop: route_id -> CASCADE (job_id already has CASCADE)
    op.drop_constraint('route_stop_route_id_fkey', 'route_stop', type_='foreignkey')
    op.create_foreign_key('route_stop_route_id_fkey', 'route_stop', 'route', ['route_id'], ['id'], ondelete='CASCADE')
    
    # team_member: tenant_id -> CASCADE, vehicle_id -> SET NULL
    op.drop_constraint('team_member_tenant_id_fkey', 'team_member', type_='foreignkey')
    op.drop_constraint('team_member_vehicle_id_fkey', 'team_member', type_='foreignkey')
    op.create_foreign_key('team_member_tenant_id_fkey', 'team_member', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('team_member_vehicle_id_fkey', 'team_member', 'vehicle', ['vehicle_id'], ['id'], ondelete='SET NULL')
    
    # user: tenant_id -> CASCADE
    op.drop_constraint('user_tenant_id_fkey', 'user', type_='foreignkey')
    op.create_foreign_key('user_tenant_id_fkey', 'user', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # vehicle: tenant_id -> CASCADE, team_member_id -> SET NULL
    op.drop_constraint('vehicle_tenant_id_fkey', 'vehicle', type_='foreignkey')
    op.drop_constraint('fk_vehicle_team_member', 'vehicle', type_='foreignkey')
    op.create_foreign_key('fk_vehicle_team_member', 'vehicle', 'team_member', ['team_member_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('vehicle_tenant_id_fkey', 'vehicle', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # onboarding: tenant_id -> CASCADE (already has it from previous migration, just ensure)
    # Skip if constraint already exists with CASCADE
    

def downgrade() -> None:
    """Remove CASCADE and SET NULL from foreign key constraints."""
    
    # vehicle
    op.drop_constraint('vehicle_tenant_id_fkey', 'vehicle', type_='foreignkey')
    op.drop_constraint('fk_vehicle_team_member', 'vehicle', type_='foreignkey')
    op.create_foreign_key('fk_vehicle_team_member', 'vehicle', 'team_member', ['team_member_id'], ['id'])
    op.create_foreign_key('vehicle_tenant_id_fkey', 'vehicle', 'tenant', ['tenant_id'], ['id'])
    
    # user
    op.drop_constraint('user_tenant_id_fkey', 'user', type_='foreignkey')
    op.create_foreign_key('user_tenant_id_fkey', 'user', 'tenant', ['tenant_id'], ['id'])
    
    # team_member
    op.drop_constraint('team_member_vehicle_id_fkey', 'team_member', type_='foreignkey')
    op.drop_constraint('team_member_tenant_id_fkey', 'team_member', type_='foreignkey')
    op.create_foreign_key('team_member_vehicle_id_fkey', 'team_member', 'vehicle', ['vehicle_id'], ['id'])
    op.create_foreign_key('team_member_tenant_id_fkey', 'team_member', 'tenant', ['tenant_id'], ['id'])
    
    # route_stop
    op.drop_constraint('route_stop_route_id_fkey', 'route_stop', type_='foreignkey')
    op.create_foreign_key('route_stop_route_id_fkey', 'route_stop', 'route', ['route_id'], ['id'])
    
    # route
    op.drop_constraint('route_driver_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_depot_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_optimization_request_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_vehicle_id_fkey', 'route', type_='foreignkey')
    op.drop_constraint('route_tenant_id_fkey', 'route', type_='foreignkey')
    op.create_foreign_key('route_optimization_request_id_fkey', 'route', 'optimization_request', ['optimization_request_id'], ['id'])
    op.create_foreign_key('route_vehicle_id_fkey', 'route', 'vehicle', ['vehicle_id'], ['id'])
    op.create_foreign_key('route_depot_id_fkey', 'route', 'depot', ['depot_id'], ['id'])
    op.create_foreign_key('route_driver_id_fkey', 'route', 'team_member', ['driver_id'], ['id'])
    op.create_foreign_key('route_tenant_id_fkey', 'route', 'tenant', ['tenant_id'], ['id'])
    
    # optimization_request
    op.drop_constraint('optimization_request_tenant_id_fkey', 'optimization_request', type_='foreignkey')
    op.drop_constraint('optimization_request_depot_id_fkey', 'optimization_request', type_='foreignkey')
    op.create_foreign_key('optimization_request_tenant_id_fkey', 'optimization_request', 'tenant', ['tenant_id'], ['id'])
    op.create_foreign_key('optimization_request_depot_id_fkey', 'optimization_request', 'depot', ['depot_id'], ['id'])
    
    # job
    op.drop_constraint('job_assigned_to_fkey', 'job', type_='foreignkey')
    op.drop_constraint('job_tenant_id_fkey', 'job', type_='foreignkey')
    op.drop_constraint('job_route_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_route_id_fkey', 'job', 'route', ['route_id'], ['id'])
    op.create_foreign_key('job_tenant_id_fkey', 'job', 'tenant', ['tenant_id'], ['id'])
    op.create_foreign_key('job_assigned_to_fkey', 'job', 'team_member', ['assigned_to'], ['id'])
    
    # depot
    op.drop_constraint('depot_tenant_id_fkey', 'depot', type_='foreignkey')
    op.create_foreign_key('depot_tenant_id_fkey', 'depot', 'tenant', ['tenant_id'], ['id'])
