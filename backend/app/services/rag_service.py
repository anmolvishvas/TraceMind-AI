"""RAG Service orchestrating document indexing, chunking, embeddings, and semantic search."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundError
from app.models.rag import DocumentChunkModel, KnowledgeDocumentModel
from app.rag.chunker import MarkdownDocumentChunker
from app.rag.embeddings import EmbeddingGenerator
from app.rag.vector_store import VectorSearchEngine
from app.schemas.rag import (
    DocumentChunk,
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentSourceType,
    SemanticSearchRequest,
    SemanticSearchResponse,
)

logger = logging.getLogger("tracemind.services.rag")


class RAGService:
    """
    Business service managing the ingestion, vector indexing, retrieval,
    and search lifecycle of operational runbooks and historical post-mortems.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_generator: EmbeddingGenerator | None = None,
        chunker: MarkdownDocumentChunker | None = None,
    ) -> None:
        self.db = db
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.chunker = chunker or MarkdownDocumentChunker()
        self.vector_search = VectorSearchEngine(db=db)

    async def create_document(self, payload: DocumentCreate) -> DocumentResponse:
        """
        Ingest a knowledge document, split into structured chunks, compute embeddings,
        and persist both document and vector chunks within an atomic transaction.
        """
        doc_pk = str(uuid4())
        doc_id = f"doc-{uuid4().hex[:12]}"

        # 1. Chunk document
        chunks_data = self.chunker.chunk_document(
            content=payload.content,
            document_metadata={
                "source_type": payload.source_type.value,
                "service_name": payload.service_name,
                "category": payload.category,
                **payload.metadata,
            },
        )

        # 2. Compute embeddings for all chunks in batch
        texts_to_embed = [c.content for c in chunks_data]
        embeddings = await self.embedding_generator.generate_embeddings(texts_to_embed)

        # 3. Instantiate Document Model
        now = datetime.now(UTC)
        doc_model = KnowledgeDocumentModel(
            id=doc_pk,
            document_id=doc_id,
            title=payload.title,
            source_type=payload.source_type.value,
            service_name=payload.service_name,
            category=payload.category,
            content=payload.content,
            metadata_=payload.metadata,
            created_at=now,
            updated_at=now,
        )
        self.db.add(doc_model)

        # 4. Instantiate Chunk Models
        for chunk, emb in zip(chunks_data, embeddings, strict=True):
            chunk_model = DocumentChunkModel(
                id=str(uuid4()),
                document_id=doc_pk,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                section_title=chunk.section_title,
                token_count=chunk.token_count,
                embedding=emb,
                metadata_=chunk.metadata,
                created_at=now,
            )
            self.db.add(chunk_model)

        await self.db.commit()
        await self.db.refresh(doc_model)

        logger.info(
            "Indexed knowledge document %s ('%s') with %d vector chunks",
            doc_id,
            payload.title,
            len(chunks_data),
        )

        return DocumentResponse(
            document_id=doc_model.document_id,
            title=doc_model.title,
            source_type=DocumentSourceType(doc_model.source_type),
            service_name=doc_model.service_name,
            category=doc_model.category,
            total_chunks=len(chunks_data),
            created_at=doc_model.created_at or now,
            updated_at=doc_model.updated_at or now,
            metadata=doc_model.metadata_,
        )

    async def get_document(self, document_id: str) -> DocumentDetailResponse:
        """Retrieve full document details with its chunks."""
        stmt = (
            select(KnowledgeDocumentModel)
            .options(selectinload(KnowledgeDocumentModel.chunks))
            .where(KnowledgeDocumentModel.document_id == document_id)
        )
        res = await self.db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise EntityNotFoundError(entity="Knowledge Document", entity_id=document_id)

        chunks_schema = [
            DocumentChunk(
                chunk_index=c.chunk_index,
                content=c.content,
                section_title=c.section_title,
                token_count=c.token_count,
                metadata=c.metadata_,
            )
            for c in doc.chunks
        ]

        return DocumentDetailResponse(
            document_id=doc.document_id,
            title=doc.title,
            source_type=DocumentSourceType(doc.source_type),
            service_name=doc.service_name,
            category=doc.category,
            total_chunks=len(chunks_schema),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            metadata=doc.metadata_,
            content=doc.content,
            chunks=chunks_schema,
        )

    async def list_documents(
        self,
        service_name: str | None = None,
        source_type: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DocumentResponse], int]:
        """List indexed documents with filtering and pagination."""
        count_stmt = select(func.count(KnowledgeDocumentModel.id))
        query_stmt = select(KnowledgeDocumentModel).order_by(
            KnowledgeDocumentModel.created_at.desc()
        )

        if service_name:
            count_stmt = count_stmt.where(KnowledgeDocumentModel.service_name == service_name)
            query_stmt = query_stmt.where(KnowledgeDocumentModel.service_name == service_name)
        if source_type:
            count_stmt = count_stmt.where(KnowledgeDocumentModel.source_type == source_type)
            query_stmt = query_stmt.where(KnowledgeDocumentModel.source_type == source_type)
        if category:
            count_stmt = count_stmt.where(KnowledgeDocumentModel.category == category)
            query_stmt = query_stmt.where(KnowledgeDocumentModel.category == category)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        query_stmt = query_stmt.limit(limit).offset(offset)
        rows_res = await self.db.execute(query_stmt)
        docs = rows_res.scalars().all()

        items = [
            DocumentResponse(
                document_id=d.document_id,
                title=d.title,
                source_type=DocumentSourceType(d.source_type),
                service_name=d.service_name,
                category=d.category,
                total_chunks=0,
                created_at=d.created_at,
                updated_at=d.updated_at,
                metadata=d.metadata_,
            )
            for d in docs
        ]

        return items, total

    async def delete_document(self, document_id: str) -> None:
        """Delete document and all associated chunks."""
        stmt = select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.document_id == document_id
        )
        res = await self.db.execute(stmt)
        doc = res.scalar_one_or_none()
        if not doc:
            raise EntityNotFoundError(entity="Knowledge Document", entity_id=document_id)

        await self.db.delete(doc)
        await self.db.commit()
        logger.info("Deleted knowledge document %s", document_id)

    async def search(self, request: SemanticSearchRequest) -> SemanticSearchResponse:
        """
        Convert search query to dense vector and execute semantic search.
        """
        query_vector = await self.embedding_generator.generate_embedding(request.query)
        return await self.vector_search.search(query_vector, request)
