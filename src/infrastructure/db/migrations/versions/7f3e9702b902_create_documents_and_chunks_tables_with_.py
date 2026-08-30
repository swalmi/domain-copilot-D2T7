"""create_documents_and_chunks_tables_with_indexes

Revision ID: 7f3e9702b902
Revises: 
Create Date: 2026-08-30 12:59:27.315193

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '7f3e9702b902'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pgvector extension, documents table, chunks table, and FTS/HNSW indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=True)

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_id", sa.String(), nullable=False),
        sa.Column("policy_type", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("chunk_type", sa.String(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
    )
    op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"], unique=True)
    op.execute("CREATE INDEX ix_chunks_text_fts ON chunks USING gin (to_tsvector('english', text));")
    op.execute("CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);")


def downgrade() -> None:
    """Drop indexes, tables, and vector extension."""
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_fts;")
    op.drop_index("ix_chunks_content_hash", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector;")
