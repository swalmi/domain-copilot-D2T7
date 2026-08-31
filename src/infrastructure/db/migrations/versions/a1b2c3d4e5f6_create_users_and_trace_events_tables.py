"""create_users_and_trace_events_tables

Revision ID: a1b2c3d4e5f6
Revises: 7f3e9702b902
Create Date: 2026-08-31 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, UUID

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '7f3e9702b902'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users table and trace_events table for authentication and audit logging."""
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "trace_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_trace_events_correlation_id", "trace_events", ["correlation_id"]
    )


def downgrade() -> None:
    """Drop trace_events and users tables."""
    op.drop_index("ix_trace_events_correlation_id", table_name="trace_events")
    op.drop_table("trace_events")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
