"""create_user_column_mapping_table

Revision ID: 5229713fa73f
Revises: de9170b8beda
Create Date: 2025-12-23 15:19:17.495834

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5229713fa73f'
down_revision: Union[str, None] = 'de9170b8beda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_column_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('mapping_config', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'entity_type', name='uix_tenant_entity_mapping')
    )
    op.create_index(op.f('ix_user_column_mapping_id'), 'user_column_mapping', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_column_mapping_id'), table_name='user_column_mapping')
    op.drop_table('user_column_mapping')
