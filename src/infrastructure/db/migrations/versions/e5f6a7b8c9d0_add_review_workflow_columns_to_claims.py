"""add review workflow columns to claims

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-24 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ownership, pipeline progress, and admin review-edit columns to claims."""
    op.add_column("claims", sa.Column("user_id", sa.UUID(), nullable=True))
    op.add_column("claims", sa.Column("pipeline_stage", sa.String(), nullable=True))
    op.add_column("claims", sa.Column("adjusted_payout", sa.Numeric(14, 2), nullable=True))
    op.add_column("claims", sa.Column("adjuster_notes", sa.Text(), nullable=True))
    op.add_column("claims", sa.Column("admin_justification", sa.Text(), nullable=True))
    op.create_index("ix_claims_user_id", "claims", ["user_id"])


def downgrade() -> None:
    """Remove review workflow columns from claims table."""
    op.drop_index("ix_claims_user_id", table_name="claims")
    op.drop_column("claims", "admin_justification")
    op.drop_column("claims", "adjuster_notes")
    op.drop_column("claims", "adjusted_payout")
    op.drop_column("claims", "pipeline_stage")
    op.drop_column("claims", "user_id")
