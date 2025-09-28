"""add scoring_mode and prices

Revision ID: ce17688f8283
Revises: 2e9654d2ca0d
Create Date: 2025-09-25 21:40:12.364743

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "ce17688f8283"
down_revision: Union[str, Sequence[str], None] = "2e9654d2ca0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
