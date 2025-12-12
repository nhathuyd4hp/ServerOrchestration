"""init db

Revision ID: 606cec45035e
Revises: 9368a1d37507
Create Date: 2025-12-11 09:32:32.641788

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "606cec45035e"
down_revision: Union[str, Sequence[str], None] = "9368a1d37507"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
