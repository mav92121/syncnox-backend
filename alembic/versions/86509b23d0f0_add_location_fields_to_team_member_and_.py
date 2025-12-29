"""add_location_fields_to_team_member_and_vehicle_fields

Revision ID: 86509b23d0f0
Revises: 5229713fa73f
Create Date: 2025-12-29 16:00:49.247903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '86509b23d0f0'
down_revision: Union[str, None] = '5229713fa73f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add location fields to team_member
    op.add_column('team_member', sa.Column('start_location', geoalchemy2.types.Geometry(geometry_type='POINT', from_text='ST_GeomFromEWKT', name='geometry'), nullable=True))
    op.add_column('team_member', sa.Column('start_address', sa.String(), nullable=True))
    op.add_column('team_member', sa.Column('end_location', geoalchemy2.types.Geometry(geometry_type='POINT', from_text='ST_GeomFromEWKT', name='geometry'), nullable=True))
    op.add_column('team_member', sa.Column('end_address', sa.String(), nullable=True))
    
    # Create spatial indexes for location columns (if not exists)
    op.create_index('idx_team_member_start_location', 'team_member', ['start_location'], unique=False, postgresql_using='gist', if_not_exists=True)
    op.create_index('idx_team_member_end_location', 'team_member', ['end_location'], unique=False, postgresql_using='gist', if_not_exists=True)
    
    # Add new fields to vehicle
    op.add_column('vehicle', sa.Column('team_member_id', sa.Integer(), nullable=True))
    op.add_column('vehicle', sa.Column('license_plate', sa.String(), nullable=True))
    op.add_column('vehicle', sa.Column('make', sa.String(), nullable=True))
    op.add_column('vehicle', sa.Column('model', sa.String(), nullable=True))
    
    # Create foreign key for vehicle -> team_member
    op.create_foreign_key('fk_vehicle_team_member', 'vehicle', 'team_member', ['team_member_id'], ['id'])


def downgrade() -> None:
    # Remove vehicle fields
    op.drop_constraint('fk_vehicle_team_member', 'vehicle', type_='foreignkey')
    op.drop_column('vehicle', 'model')
    op.drop_column('vehicle', 'make')
    op.drop_column('vehicle', 'license_plate')
    op.drop_column('vehicle', 'team_member_id')
    
    # Remove team_member location fields
    op.drop_index('idx_team_member_end_location', table_name='team_member', postgresql_using='gist')
    op.drop_index('idx_team_member_start_location', table_name='team_member', postgresql_using='gist')
    op.drop_column('team_member', 'end_address')
    op.drop_column('team_member', 'end_location')
    op.drop_column('team_member', 'start_address')
    op.drop_column('team_member', 'start_location')
