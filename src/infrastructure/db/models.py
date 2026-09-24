import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""



class DocumentModel(Base):
    """SQLAlchemy model representing an ingested document in the database."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chunks: Mapped[list["ChunkModel"]] = relationship(
        "ChunkModel", back_populates="document", cascade="all, delete-orphan"
    )


class ChunkModel(Base):
    """SQLAlchemy model representing a document text chunk with vector embeddings."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[str] = mapped_column(String, nullable=False)
    policy_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    section: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    document: Mapped["DocumentModel"] = relationship(
        "DocumentModel", back_populates="chunks"
    )


class UserModel(Base):
    """SQLAlchemy model representing an authenticated user account with role permissions."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)


class ClaimModel(Base):
    """SQLAlchemy model representing an insurance claim and its adjudication result."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    policy_number: Mapped[str] = mapped_column(String, index=True, nullable=False)
    date_of_loss: Mapped[date] = mapped_column(Date, nullable=False)
    incident_description: Mapped[str] = mapped_column(Text, nullable=False)
    claim_amount_requested: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    status: Mapped[str] = mapped_column(String, index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    pipeline_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    calculated_payout: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    deductible_applied: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    policy_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjusted_payout: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    adjuster_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TraceEventModel(Base):
    """SQLAlchemy model representing an execution trace log event for multi-agent workflows."""

    __tablename__ = "trace_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    step_name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


