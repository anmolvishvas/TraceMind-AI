"""Root Cause Analysis service orchestrating incident telemetry, RAG search, and LLM inference."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError
from app.llm.assistant import InvestigationAssistant
from app.llm.rca_engine import RCAEngine
from app.schemas.rag import SearchResultItem, SemanticSearchRequest
from app.schemas.rca import (
    InvestigationChatRequest,
    InvestigationChatResponse,
    RCARequest,
    RCAResponse,
)
from app.services.anomaly_service import AnomalyService
from app.services.incident_service import IncidentService
from app.services.rag_service import RAGService

logger = logging.getLogger("tracemind.services.rca")


class RCAService:
    """
    Coordinates incident data extraction, anomaly correlation, historical runbook
    retrieval via RAG, and AI-powered root cause analysis generation.
    """

    def __init__(
        self,
        db: AsyncSession,
        rca_engine: RCAEngine | None = None,
        assistant: InvestigationAssistant | None = None,
    ) -> None:
        self.db = db
        self.rca_engine = rca_engine or RCAEngine()
        self.assistant = assistant or InvestigationAssistant()
        self.incident_service = IncidentService(db=db)
        self.anomaly_service = AnomalyService(db=db)
        self.rag_service = RAGService(db=db)

    async def generate_rca(self, request: RCARequest) -> RCAResponse:
        """
        Synthesize multi-source operational data into evidence-grounded Root Cause Analysis.
        """
        # 1. Fetch full incident details & chronological timeline
        if not request.incident_id:
            raise EntityNotFoundError(entity="Incident", entity_id="")
        if not request.incident_id:
            raise EntityNotFoundError(entity="Incident", entity_id="")
        incident = await self.incident_service.get_incident(request.incident_id)

        # 2. Fetch recent statistical anomalies for the lead service
        anomalies, _ = await self.anomaly_service.list_anomalies(
            service_name=incident.lead_service,
            limit=10,
        )

        # 3. Retrieve relevant historical runbooks and post-mortems via RAG
        runbooks: list[SearchResultItem] = []
        if request.include_rag_context:
            search_query = (
                f"{incident.title} {incident.lead_service} {' '.join(incident.error_signatures)}"
            ).strip()
            try:
                search_res = await self.rag_service.search(
                    SemanticSearchRequest(
                        query=search_query,
                        service_name=incident.lead_service,
                        limit=5,
                        min_similarity=0.4,
                    )
                )
                runbooks = search_res.results
            except Exception as exc:
                logger.warning("RAG search failed during RCA: %s. Continuing with logs.", exc)

        # 4. Generate structured RCA via LLM
        return await self.rca_engine.analyze_incident(
            incident=incident,
            anomalies=anomalies,
            runbooks=runbooks,
            additional_notes=request.additional_context,
        )

    async def investigate_chat(
        self,
        request: InvestigationChatRequest,
    ) -> InvestigationChatResponse:
        """
        Interactive conversational turn with the incident investigation assistant.
        """
        if not request.incident_id:
            raise EntityNotFoundError(entity="Incident", entity_id="")
        incident = await self.incident_service.get_incident(request.incident_id)

        # Retrieve relevant runbooks based on query
        runbooks: list[SearchResultItem] = []
        try:
            search_res = await self.rag_service.search(
                SemanticSearchRequest(
                    query=request.query,
                    service_name=incident.lead_service,
                    limit=3,
                    min_similarity=0.4,
                )
            )
            runbooks = search_res.results
        except Exception as exc:
            logger.debug("RAG lookup failed for assistant chat: %s", exc)

        return await self.assistant.answer_query(
            request=request,
            incident=incident,
            runbooks=runbooks,
        )
