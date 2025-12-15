"""log table

Revision ID: 288f3bc59628
Revises: 606cec45035e
Create Date: 2025-12-15 08:04:33.819145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '288f3bc59628'
down_revision: Union[str, Sequence[str], None] = '606cec45035e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
