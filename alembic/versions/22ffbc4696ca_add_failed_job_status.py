"""add failed job status

Revision ID: 22ffbc4696ca
Revises: 261fb778f4d2
Create Date: 2026-03-16 21:25:43.559297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '22ffbc4696ca'
down_revision: Union[str, None] = '261fb778f4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE for adding enum values.
    # We use execute with connection.execute and autocommit block if needed,
    # but op.execute generally works with 'ADD VALUE IF NOT EXISTS' in native PG 9.3+
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'failed'")


def downgrade() -> None:
    # Removing enum values in PostgreSQL is not natively supported in a simple ALTER TYPE.
    # It requires creating a new type, altering columns to the new type, and dropping the old type.
    # Since adding a status is backwards compatible, we leave this empty.
    pass
