"""Vector search engine utilising PostgreSQL pgvector and HNSW cosine distance indexing."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import DocumentChunkModel, KnowledgeDocumentModel
from app.schemas.rag import (
    DocumentSourceType,
    SearchResultItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

logger = logging.getLogger("tracemind.rag.vector_store")


class VectorSearchEngine:
    """
    Executes high-performance vector similarity search over operational knowledge chunks,
    applying metadata filters and generating evidence citations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query_vector: list[float],
        request: SemanticSearchRequest,
    ) -> SemanticSearchResponse:
        """
        Execute pgvector cosine distance search joined with parent knowledge document metadata.
        """
        # Cosine distance expression: chunk.embedding <=> query_vector
        cosine_dist = DocumentChunkModel.embedding.cosine_distance(query_vector)

        # Build SELECT query
        stmt = (
            select(
                DocumentChunkModel,
                KnowledgeDocumentModel,
                cosine_dist.label("distance"),
            )
            .join(
                KnowledgeDocumentModel,
                DocumentChunkModel.document_id == KnowledgeDocumentModel.id,
            )
            .order_by(cosine_dist.asc())
            .limit(request.limit * 2)  # Over-fetch slightly for threshold filtering
        )

        # Apply metadata filters
        if request.service_name:
            stmt = stmt.where(
                sa.or_(
                    KnowledgeDocumentModel.service_name == request.service_name,
                    KnowledgeDocumentModel.service_name.is_(None),
                )
            )
        if request.source_type:
            stmt = stmt.where(KnowledgeDocumentModel.source_type == request.source_type.value)
        if request.category:
            stmt = stmt.where(KnowledgeDocumentModel.category == request.category)

        res = await self.db.execute(stmt)
        rows = res.all()

        results: list[SearchResultItem] = []
        for chunk, doc, dist in rows:
            dist_val = float(dist) if dist is not None else 1.0
            similarity = max(0.0, min(1.0, 1.0 - dist_val))

            if similarity < request.min_similarity:
                continue

            sec = chunk.section_title or "General"
            citation = f"[{doc.source_type}: {doc.title}, §{sec}]"

            results.append(
                SearchResultItem(
                    document_id=doc.document_id,
                    title=doc.title,
                    source_type=DocumentSourceType(doc.source_type),
                    service_name=doc.service_name,
                    section_title=chunk.section_title,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    similarity_score=round(similarity, 4),
                    citation_reference=citation,
                )
            )

            if len(results) >= request.limit:
                break

        return SemanticSearchResponse(
            query=request.query,
            total_results=len(results),
            results=results,
        )
