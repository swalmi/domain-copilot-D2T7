"""add error_message to claims

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add error_message column to claims table for failed-task diagnostics."""
    op.add_column("claims", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove error_message column from claims table."""
    op.drop_column("claims", "error_message")
