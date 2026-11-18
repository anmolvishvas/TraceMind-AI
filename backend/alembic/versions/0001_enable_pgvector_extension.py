"""enable pgvector extension

Revision ID: 0001_pgvector
Revises:
Create Date: 2026-11-18 11:45:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable the pgvector extension in PostgreSQL."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    """Drop the pgvector extension."""
    op.execute("DROP EXTENSION IF EXISTS vector;")
