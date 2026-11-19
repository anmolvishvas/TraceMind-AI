"""REST API endpoints for RAG knowledge base management, runbook indexing, and semantic search."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.rag import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentSourceType,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.rag_service import RAGService

router = APIRouter(prefix="/rag", tags=["RAG & Knowledge Base"])


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def create_document(
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    """
    Ingest and index an operational runbook, post-mortem, or playbook.
    Splits into Markdown sections, computes vector embeddings, and stores in PostgreSQL pgvector.
    """
    service = RAGService(db=db)
    return await service.create_document(payload)


@router.get("/documents", response_model=dict[str, Any], status_code=200)
async def list_documents(
    service_name: str | None = Query(None, description="Filter by service"),
    source_type: DocumentSourceType | None = Query(None, description="Filter by document type"),
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List indexed operational knowledge documents with filtering and pagination."""
    service = RAGService(db=db)
    items, total = await service.list_documents(
        service_name=service_name,
        source_type=source_type.value if source_type else None,
        category=category,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [item.model_dump() for item in items],
    }


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse, status_code=200)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentDetailResponse:
    """Retrieve full document details along with parsed vector chunks."""
    service = RAGService(db=db)
    return await service.get_document(document_id)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an operational knowledge document and its vector chunks."""
    service = RAGService(db=db)
    await service.delete_document(document_id)


@router.post("/search", response_model=SemanticSearchResponse, status_code=200)
async def semantic_search(
    request: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SemanticSearchResponse:
    """
    Execute semantic similarity vector search over indexed runbooks and post-mortems.
    Returns cosine similarity scored snippets with structured citations.
    """
    service = RAGService(db=db)
    return await service.search(request)
