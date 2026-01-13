"""add_cascade_delete_to_foreign_keys

Revision ID: 97c05195d429
Revises: c7e8f9a0b1c2
Create Date: 2026-01-05 14:34:30.521531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '97c05195d429'
down_revision: Union[str, None] = 'c7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def get_fk_constraint_name(table_name: str, column_name: str) -> str | None:
    """Find the actual FK constraint name for a column by inspecting the schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    
    try:
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            if column_name in fk.get('constrained_columns', []):
                return fk.get('name')
    except Exception:
        pass
    
    return None


def safe_drop_fk(table_name: str, column_name: str, fallback_name: str = None):
    """Safely drop a FK constraint by inspecting the actual constraint name."""
    constraint_name = get_fk_constraint_name(table_name, column_name)
    
    if constraint_name:
        try:
            op.drop_constraint(constraint_name, table_name, type_='foreignkey')
            return True
        except Exception as e:
            print(f"Warning: Could not drop constraint {constraint_name} on {table_name}: {e}")
    elif fallback_name:
        # Try the fallback name
        try:
            op.drop_constraint(fallback_name, table_name, type_='foreignkey')
            return True
        except Exception as e:
            print(f"Warning: Could not drop fallback constraint {fallback_name} on {table_name}: {e}")
    
    return False


def upgrade() -> None:
    """Add CASCADE and SET NULL to foreign key constraints."""
    
    # depot: tenant_id -> CASCADE
    safe_drop_fk('depot', 'tenant_id', 'depot_tenant_id_fkey')
    op.create_foreign_key('depot_tenant_id_fkey', 'depot', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # job: tenant_id -> CASCADE, assigned_to -> SET NULL, route_id -> SET NULL
    safe_drop_fk('job', 'assigned_to', 'job_assigned_to_fkey')
    safe_drop_fk('job', 'tenant_id', 'job_tenant_id_fkey')
    safe_drop_fk('job', 'route_id', 'job_route_id_fkey')
    op.create_foreign_key('job_route_id_fkey', 'job', 'route', ['route_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('job_tenant_id_fkey', 'job', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('job_assigned_to_fkey', 'job', 'team_member', ['assigned_to'], ['id'], ondelete='SET NULL')
    
    # optimization_request: tenant_id -> CASCADE, depot_id -> SET NULL
    safe_drop_fk('optimization_request', 'depot_id', 'optimization_request_depot_id_fkey')
    safe_drop_fk('optimization_request', 'tenant_id', 'optimization_request_tenant_id_fkey')
    op.create_foreign_key('optimization_request_depot_id_fkey', 'optimization_request', 'depot', ['depot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('optimization_request_tenant_id_fkey', 'optimization_request', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # route: tenant_id -> CASCADE, driver_id/vehicle_id/depot_id -> SET NULL, optimization_request_id -> CASCADE
    safe_drop_fk('route', 'tenant_id', 'route_tenant_id_fkey')
    safe_drop_fk('route', 'driver_id', 'route_driver_id_fkey')
    safe_drop_fk('route', 'depot_id', 'route_depot_id_fkey')
    safe_drop_fk('route', 'vehicle_id', 'route_vehicle_id_fkey')
    safe_drop_fk('route', 'optimization_request_id', 'route_optimization_request_id_fkey')
    op.create_foreign_key('route_tenant_id_fkey', 'route', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('route_vehicle_id_fkey', 'route', 'vehicle', ['vehicle_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('route_optimization_request_id_fkey', 'route', 'optimization_request', ['optimization_request_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('route_depot_id_fkey', 'route', 'depot', ['depot_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('route_driver_id_fkey', 'route', 'team_member', ['driver_id'], ['id'], ondelete='SET NULL')
    
    # route_stop: route_id -> CASCADE (job_id already has CASCADE)
    safe_drop_fk('route_stop', 'route_id', 'route_stop_route_id_fkey')
    op.create_foreign_key('route_stop_route_id_fkey', 'route_stop', 'route', ['route_id'], ['id'], ondelete='CASCADE')
    
    # team_member: tenant_id -> CASCADE, vehicle_id -> SET NULL
    safe_drop_fk('team_member', 'tenant_id', 'team_member_tenant_id_fkey')
    safe_drop_fk('team_member', 'vehicle_id', 'team_member_vehicle_id_fkey')
    op.create_foreign_key('team_member_tenant_id_fkey', 'team_member', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('team_member_vehicle_id_fkey', 'team_member', 'vehicle', ['vehicle_id'], ['id'], ondelete='SET NULL')
    
    # user: tenant_id -> CASCADE
    safe_drop_fk('user', 'tenant_id', 'user_tenant_id_fkey')
    op.create_foreign_key('user_tenant_id_fkey', 'user', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')
    
    # vehicle: tenant_id -> CASCADE, team_member_id -> SET NULL
    safe_drop_fk('vehicle', 'tenant_id', 'vehicle_tenant_id_fkey')
    safe_drop_fk('vehicle', 'team_member_id', 'fk_vehicle_team_member')
    op.create_foreign_key('fk_vehicle_team_member', 'vehicle', 'team_member', ['team_member_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('vehicle_tenant_id_fkey', 'vehicle', 'tenant', ['tenant_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Remove CASCADE and SET NULL from foreign key constraints."""
    
    # vehicle
    safe_drop_fk('vehicle', 'tenant_id', 'vehicle_tenant_id_fkey')
    safe_drop_fk('vehicle', 'team_member_id', 'fk_vehicle_team_member')
    op.create_foreign_key('fk_vehicle_team_member', 'vehicle', 'team_member', ['team_member_id'], ['id'])
    op.create_foreign_key('vehicle_tenant_id_fkey', 'vehicle', 'tenant', ['tenant_id'], ['id'])
    
    # user
    safe_drop_fk('user', 'tenant_id', 'user_tenant_id_fkey')
    op.create_foreign_key('user_tenant_id_fkey', 'user', 'tenant', ['tenant_id'], ['id'])
    
    # team_member
    safe_drop_fk('team_member', 'vehicle_id', 'team_member_vehicle_id_fkey')
    safe_drop_fk('team_member', 'tenant_id', 'team_member_tenant_id_fkey')
    op.create_foreign_key('team_member_vehicle_id_fkey', 'team_member', 'vehicle', ['vehicle_id'], ['id'])
    op.create_foreign_key('team_member_tenant_id_fkey', 'team_member', 'tenant', ['tenant_id'], ['id'])
    
    # route_stop
    safe_drop_fk('route_stop', 'route_id', 'route_stop_route_id_fkey')
    op.create_foreign_key('route_stop_route_id_fkey', 'route_stop', 'route', ['route_id'], ['id'])
    
    # route
    safe_drop_fk('route', 'driver_id', 'route_driver_id_fkey')
    safe_drop_fk('route', 'depot_id', 'route_depot_id_fkey')
    safe_drop_fk('route', 'optimization_request_id', 'route_optimization_request_id_fkey')
    safe_drop_fk('route', 'vehicle_id', 'route_vehicle_id_fkey')
    safe_drop_fk('route', 'tenant_id', 'route_tenant_id_fkey')
    op.create_foreign_key('route_optimization_request_id_fkey', 'route', 'optimization_request', ['optimization_request_id'], ['id'])
    op.create_foreign_key('route_vehicle_id_fkey', 'route', 'vehicle', ['vehicle_id'], ['id'])
    op.create_foreign_key('route_depot_id_fkey', 'route', 'depot', ['depot_id'], ['id'])
    op.create_foreign_key('route_driver_id_fkey', 'route', 'team_member', ['driver_id'], ['id'])
    op.create_foreign_key('route_tenant_id_fkey', 'route', 'tenant', ['tenant_id'], ['id'])
    
    # optimization_request
    safe_drop_fk('optimization_request', 'tenant_id', 'optimization_request_tenant_id_fkey')
    safe_drop_fk('optimization_request', 'depot_id', 'optimization_request_depot_id_fkey')
    op.create_foreign_key('optimization_request_tenant_id_fkey', 'optimization_request', 'tenant', ['tenant_id'], ['id'])
    op.create_foreign_key('optimization_request_depot_id_fkey', 'optimization_request', 'depot', ['depot_id'], ['id'])
    
    # job
    safe_drop_fk('job', 'assigned_to', 'job_assigned_to_fkey')
    safe_drop_fk('job', 'tenant_id', 'job_tenant_id_fkey')
    safe_drop_fk('job', 'route_id', 'job_route_id_fkey')
    op.create_foreign_key('job_route_id_fkey', 'job', 'route', ['route_id'], ['id'])
    op.create_foreign_key('job_tenant_id_fkey', 'job', 'tenant', ['tenant_id'], ['id'])
    op.create_foreign_key('job_assigned_to_fkey', 'job', 'team_member', ['assigned_to'], ['id'])
    
    # depot
    safe_drop_fk('depot', 'tenant_id', 'depot_tenant_id_fkey')
    op.create_foreign_key('depot_tenant_id_fkey', 'depot', 'tenant', ['tenant_id'], ['id'])

