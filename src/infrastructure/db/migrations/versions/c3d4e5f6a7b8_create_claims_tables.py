"""create_claims_tables

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create claims table for durable claim persistence across API/worker processes."""
    op.create_table(
        "claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_number", sa.String(), nullable=False),
        sa.Column("date_of_loss", sa.Date(), nullable=False),
        sa.Column("incident_description", sa.Text(), nullable=False),
        sa.Column("claim_amount_requested", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("celery_task_id", sa.String(), nullable=True),
        sa.Column("calculated_payout", sa.Numeric(14, 2), nullable=True),
        sa.Column("deductible_applied", sa.Numeric(14, 2), nullable=True),
        sa.Column("policy_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("reasoning_text", sa.Text(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claims_policy_number", "claims", ["policy_number"])
    op.create_index("ix_claims_status", "claims", ["status"])
    op.create_index("ix_claims_correlation_id", "claims", ["correlation_id"])


def downgrade() -> None:
    """Drop claims table and its indexes."""
    op.drop_index("ix_claims_correlation_id", table_name="claims")
    op.drop_index("ix_claims_status", table_name="claims")
    op.drop_index("ix_claims_policy_number", table_name="claims")
    op.drop_table("claims")