"""Unit tests for RAGService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import EntityNotFoundError
from app.models.rag import DocumentChunkModel, KnowledgeDocumentModel
from app.schemas.rag import DocumentCreate, DocumentSourceType, SemanticSearchRequest
from app.services.rag_service import RAGService


@pytest.mark.asyncio
async def test_rag_service_create_document() -> None:
    """Verify create_document chunks, embeds, and persists."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    service = RAGService(db=mock_db)
    payload = DocumentCreate(
        title="Payment Service Runbook",
        source_type=DocumentSourceType.RUNBOOK,
        service_name="payment-service",
        category="payment",
        content="# Overview\nHandles charges.\n\n# Troubleshooting\nCheck payment gateway status.",
    )

    doc_response = await service.create_document(payload)

    assert doc_response.title == "Payment Service Runbook"
    assert doc_response.source_type == DocumentSourceType.RUNBOOK
    assert doc_response.total_chunks >= 2
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_service_get_document_success_and_not_found() -> None:
    """Verify get_document retrieves with chunks or raises EntityNotFoundError."""
    mock_db = AsyncMock()
    now = datetime.now(UTC)

    doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-exists",
        title="Auth Runbook",
        source_type="RUNBOOK",
        service_name="auth-service",
        category="security",
        content="Full text",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    chunk = DocumentChunkModel(
        id=str(uuid4()),
        document_id=doc.id,
        chunk_index=0,
        content="JWT expiration",
        section_title="## Tokens",
        token_count=10,
        embedding=[0.0] * 1536,
        metadata_={},
    )
    doc.chunks = [chunk]

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = doc
    mock_db.execute.return_value = mock_res

    service = RAGService(db=mock_db)
    detail = await service.get_document("doc-exists")
    assert detail.document_id == "doc-exists"
    assert detail.total_chunks == 1
    assert len(detail.chunks) == 1

    # Not found case
    mock_not_found = MagicMock()
    mock_not_found.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_not_found

    with pytest.raises(EntityNotFoundError):
        await service.get_document("doc-nonexistent")


@pytest.mark.asyncio
async def test_rag_service_list_and_delete_documents() -> None:
    """Verify list_documents pagination and delete_document."""
    mock_db = AsyncMock()
    now = datetime.now(UTC)

    doc = KnowledgeDocumentModel(
        id=str(uuid4()),
        document_id="doc-to-delete",
        title="Kafka Runbook",
        source_type="RUNBOOK",
        service_name="event-bus",
        category="messaging",
        content="text",
        metadata_={},
        created_at=now,
        updated_at=now,
    )

    mock_count = MagicMock()
    mock_count.scalar.return_value = 1
    mock_rows = MagicMock()
    mock_rows.scalars.return_value.all.return_value = [doc]

    mock_db.execute.side_effect = [mock_count, mock_rows]

    service = RAGService(db=mock_db)
    items, total = await service.list_documents(service_name="event-bus", limit=10, offset=0)
    assert total == 1
    assert len(items) == 1
    assert items[0].document_id == "doc-to-delete"

    # Delete test
    mock_del_res = MagicMock()
    mock_del_res.scalar_one_or_none.return_value = doc
    mock_db.execute.side_effect = [mock_del_res]

    await service.delete_document("doc-to-delete")
    mock_db.delete.assert_awaited_once_with(doc)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_service_search() -> None:
    """Verify search delegates to vector_search."""
    mock_db = AsyncMock()
    service = RAGService(db=mock_db)

    service.vector_search.search = AsyncMock()  # type: ignore[method-assign]
    service.vector_search.search.return_value = MagicMock(total_results=2, results=[])

    req = SemanticSearchRequest(query="database crash")
    res = await service.search(req)
    assert res.total_results == 2
