"""add load_constraints to vehicle

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-28 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add new load_constraints column
    op.add_column(
        'vehicle',
        sa.Column('load_constraints', JSONB, nullable=True, server_default='[]')
    )

    # Migrate existing capacity_weight / capacity_volume into the new JSONB column
    op.execute("""
        UPDATE vehicle
        SET load_constraints = (
            CASE
                WHEN capacity_weight IS NOT NULL AND capacity_volume IS NOT NULL
                    THEN jsonb_build_array(
                        jsonb_build_object('constraint_type', 'weight', 'max_value', capacity_weight, 'unit', 'kg'),
                        jsonb_build_object('constraint_type', 'volume', 'max_value', capacity_volume, 'unit', 'm3')
                    )
                WHEN capacity_weight IS NOT NULL
                    THEN jsonb_build_array(
                        jsonb_build_object('constraint_type', 'weight', 'max_value', capacity_weight, 'unit', 'kg')
                    )
                WHEN capacity_volume IS NOT NULL
                    THEN jsonb_build_array(
                        jsonb_build_object('constraint_type', 'volume', 'max_value', capacity_volume, 'unit', 'm3')
                    )
                ELSE '[]'::jsonb
            END
        )
    """)

    # Drop the legacy columns
    op.drop_column('vehicle', 'capacity_weight')
    op.drop_column('vehicle', 'capacity_volume')

    # Add new enum values for van and bus
    op.execute("ALTER TYPE vehicletype ADD VALUE IF NOT EXISTS 'van'")
    op.execute("ALTER TYPE vehicletype ADD VALUE IF NOT EXISTS 'bus'")


def downgrade():
    # Re-add the legacy columns
    op.add_column('vehicle', sa.Column('capacity_weight', sa.Float(), nullable=True))
    op.add_column('vehicle', sa.Column('capacity_volume', sa.Float(), nullable=True))

    # Attempt to restore values from JSONB (best effort for weight and volume)
    op.execute("""
        UPDATE vehicle
        SET
            capacity_weight = (
                SELECT (elem->>'max_value')::float
                FROM jsonb_array_elements(COALESCE(load_constraints, '[]'::jsonb)) AS elem
                WHERE elem->>'constraint_type' = 'weight'
                LIMIT 1
            ),
            capacity_volume = (
                SELECT (elem->>'max_value')::float
                FROM jsonb_array_elements(COALESCE(load_constraints, '[]'::jsonb)) AS elem
                WHERE elem->>'constraint_type' = 'volume'
                LIMIT 1
            )
    """)

    # Drop the new column
    op.drop_column('vehicle', 'load_constraints')
