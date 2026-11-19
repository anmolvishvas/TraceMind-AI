"""Unit tests for VectorSearchEngine."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.rag import DocumentChunkModel, KnowledgeDocumentModel
from app.rag.vector_store import VectorSearchEngine
from app.schemas.rag import DocumentSourceType, SemanticSearchRequest


@pytest.mark.asyncio
async def test_vector_search_engine_ranking() -> None:
    """Verify vector search calculates similarity and formats citation references."""
    mock_db = AsyncMock()

    doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-123",
        title="PostgreSQL Runbook",
        source_type="RUNBOOK",
        service_name="payment-service",
        category="database",
        content="Full text",
        metadata_={},
    )
    chunk = DocumentChunkModel(
        id=str(uuid4()),
        document_id=doc.id,
        chunk_index=0,
        content="Check active connection count using pg_stat_activity",
        section_title="## Connection Limits",
        token_count=15,
        embedding=[0.1] * 1536,
        metadata_={},
    )

    # Mock query result: [(chunk, doc, distance=0.15)] -> similarity = 0.85
    mock_res = MagicMock()
    mock_res.all.return_value = [(chunk, doc, 0.15)]
    mock_db.execute.return_value = mock_res

    engine = VectorSearchEngine(db=mock_db)
    request = SemanticSearchRequest(
        query="database connection pool",
        service_name="payment-service",
        source_type=DocumentSourceType.RUNBOOK,
        category="database",
        limit=5,
        min_similarity=0.7,
    )
    response = await engine.search(query_vector=[0.1] * 1536, request=request)

    assert response.total_results == 1
    item = response.results[0]
    assert item.document_id == "doc-123"
    assert item.similarity_score == 0.85
    assert item.citation_reference == "[RUNBOOK: PostgreSQL Runbook, §## Connection Limits]"
    assert "pg_stat_activity" in item.content


@pytest.mark.asyncio
async def test_vector_search_min_similarity_filter() -> None:
    """Verify results below min_similarity are filtered out."""
    mock_db = AsyncMock()
    doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-low",
        title="Unrelated doc",
        source_type="ARCHITECTURE",
        service_name=None,
        content="Irrelevant",
    )
    chunk = DocumentChunkModel(
        id=str(uuid4()),
        document_id=doc.id,
        chunk_index=0,
        content="Irrelevant content",
        embedding=[0.0] * 1536,
    )

    # distance=0.8 -> similarity = 0.2
    mock_res = MagicMock()
    mock_res.all.return_value = [(chunk, doc, 0.8)]
    mock_db.execute.return_value = mock_res

    engine = VectorSearchEngine(db=mock_db)
    request = SemanticSearchRequest(query="query", min_similarity=0.6)
    response = await engine.search(query_vector=[0.0] * 1536, request=request)

    assert response.total_results == 0
    assert response.results == []
