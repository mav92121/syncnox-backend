"""merge heads

Revision ID: d03473a50a30
Revises: 22ffbc4696ca, b3c4d5e6f7a8
Create Date: 2026-04-28 23:47:08.176233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd03473a50a30'
down_revision: Union[str, None] = ('22ffbc4696ca', 'b3c4d5e6f7a8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
