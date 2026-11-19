"""SQLAlchemy 2.0 ORM models for RAG knowledge documents, runbooks, and vector chunks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeDocumentModel(Base):
    """
    SQLAlchemy ORM model representing indexed operational knowledge documents
    such as runbooks, post-mortems, architectural designs, and SRE playbooks.
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        sa.String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        sa.String(500),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        default="RUNBOOK",
        index=True,
    )
    service_name: Mapped[str | None] = mapped_column(
        sa.String(128),
        nullable=True,
        index=True,
    )
    category: Mapped[str | None] = mapped_column(
        sa.String(64),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # 1:N relationship with document chunks
    chunks: Mapped[list[DocumentChunkModel]] = relationship(
        "DocumentChunkModel",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunkModel.chunk_index.asc()",
    )

    __table_args__ = (
        sa.Index("ix_knowledge_documents_service_source", "service_name", "source_type"),
    )


class DocumentChunkModel(Base):
    """
    SQLAlchemy ORM model representing individual text chunks with 1536-dimensional
    vector embeddings for pgvector cosine similarity search.
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        sa.String(36),
        sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
    )
    section_title: Mapped[str | None] = mapped_column(
        sa.String(255),
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        postgresql.JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationship back to parent document
    document: Mapped[KnowledgeDocumentModel] = relationship(
        "KnowledgeDocumentModel",
        back_populates="chunks",
    )

    __table_args__ = (
        sa.Index("ix_document_chunks_doc_chunk_idx", "document_id", "chunk_index", unique=True),
        sa.Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
