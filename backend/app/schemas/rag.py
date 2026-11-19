"""Pydantic v2 validation schemas for RAG knowledge documents, chunking, and semantic search."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentSourceType(StrEnum):
    """Categorisation of operational knowledge documents."""

    RUNBOOK = "RUNBOOK"
    POSTMORTEM = "POSTMORTEM"
    ARCHITECTURE = "ARCHITECTURE"
    SRE_PLAYBOOK = "SRE_PLAYBOOK"
    INCIDENT_SUMMARY = "INCIDENT_SUMMARY"


class DocumentChunk(BaseModel):
    """Schema representing an individual structural chunk of a knowledge document."""

    model_config = ConfigDict(from_attributes=True)

    chunk_index: int = Field(..., ge=0, description="Sequential index of the chunk in document")
    content: str = Field(..., min_length=1, description="Chunk text content")
    section_title: str | None = Field(
        default=None, description="Preserved Markdown heading/section title"
    )
    token_count: int = Field(default=0, ge=0, description="Estimated token count")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk-level metadata")


class DocumentCreate(BaseModel):
    """Request payload for indexing a new knowledge document or runbook."""

    title: str = Field(..., min_length=3, max_length=500, description="Human-readable title")
    source_type: DocumentSourceType = Field(
        default=DocumentSourceType.RUNBOOK,
        description="Type of knowledge document",
    )
    service_name: str | None = Field(
        default=None, max_length=128, description="Target service this document relates to"
    )
    category: str | None = Field(
        default=None,
        max_length=64,
        description="Functional category (e.g. database, network, auth)",
    )
    content: str = Field(
        ..., min_length=10, description="Raw markdown or text content of the document"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary tags or metadata")


class DocumentResponse(BaseModel):
    """Summary response for an indexed knowledge document."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    title: str
    source_type: DocumentSourceType
    service_name: str | None = None
    category: str | None = None
    total_chunks: int = Field(default=0, description="Number of vector chunks generated")
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentDetailResponse(DocumentResponse):
    """Full detail response including original content and chunk breakdowns."""

    content: str
    chunks: list[DocumentChunk] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    """A single citation-backed result from semantic vector similarity search."""

    document_id: str
    title: str
    source_type: DocumentSourceType
    service_name: str | None = None
    section_title: str | None = None
    chunk_index: int
    content: str
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity [0.0, 1.0]")
    citation_reference: str = Field(
        ..., description="Human-readable citation (e.g. [Runbook: Postgres Deadlocks, §Resolution])"
    )


class SemanticSearchRequest(BaseModel):
    """Request payload for semantic vector search over the knowledge base."""

    query: str = Field(
        ..., min_length=3, description="Search query or incident symptom description"
    )
    service_name: str | None = Field(default=None, description="Filter results by service name")
    source_type: DocumentSourceType | None = Field(
        default=None, description="Filter by document type"
    )
    category: str | None = Field(default=None, description="Filter by category")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to return")
    min_similarity: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Minimum cosine similarity cutoff"
    )


class SemanticSearchResponse(BaseModel):
    """Container for vector similarity search results."""

    query: str
    total_results: int
    results: list[SearchResultItem]
