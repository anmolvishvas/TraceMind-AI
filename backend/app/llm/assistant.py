"""Interactive AI incident investigation assistant for collaborative on-call diagnosis."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.llm.client import LLMClient
from app.llm.prompts import INVESTIGATION_ASSISTANT_SYSTEM_PROMPT
from app.schemas.incident import IncidentDetailResponse
from app.schemas.rag import SearchResultItem
from app.schemas.rca import (
    CitationType,
    EvidenceCitation,
    InvestigationChatRequest,
    InvestigationChatResponse,
)

logger = logging.getLogger("tracemind.llm.assistant")


class InvestigationAssistant:
    """
    Multi-turn conversational assistant grounded in the incident's live timeline,
    correlated error logs, and retrieved operational knowledge.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def answer_query(
        self,
        request: InvestigationChatRequest,
        incident: IncidentDetailResponse,
        runbooks: list[SearchResultItem] | None = None,
    ) -> InvestigationChatResponse:
        """
        Generate grounded response to an engineer's investigation question.
        """
        # 1. Build context header
        context_prompt = self._build_context_prompt(incident, runbooks or [])

        # 2. Build OpenAI chat message sequence
        messages: list[dict[str, str]] = [
            {"role": "system", "content": INVESTIGATION_ASSISTANT_SYSTEM_PROMPT},
            {"role": "system", "content": f"CURRENT INCIDENT CONTEXT:\n{context_prompt}"},
        ]

        # Append previous conversation history
        for msg in request.history[-6:]:  # Keep recent turns to manage context window
            messages.append({"role": msg.role, "content": msg.content})

        # Append current user question
        messages.append({"role": "user", "content": request.query})

        # 3. Query LLM
        answer = await self.llm_client.chat(messages=messages)

        # 4. Extract citations from answer and context
        citations = self._extract_citations(answer, incident, runbooks or [])

        # 5. Formulate suggested follow-up questions
        followups = self._generate_followups(request.query, incident)

        return InvestigationChatResponse(
            incident_id=incident.incident_id,
            answer=answer,
            citations=citations,
            suggested_followups=followups,
        )

    def _build_context_prompt(
        self,
        incident: IncidentDetailResponse,
        runbooks: list[SearchResultItem],
    ) -> str:
        """Format incident timeline and runbooks into concise context text."""
        lines = [
            f"Incident ID: {incident.incident_id} | Status: {incident.status.value} | Severity: {incident.severity.value}",
            f"Lead Service: {incident.lead_service} | Affected: {', '.join(incident.affected_services)}",
            f"Started: {incident.started_at.isoformat()} | Detected: {incident.detected_at.isoformat()}",
            "Correlated Log Events:",
        ]
        for c in incident.correlations[:10]:
            lines.append(f"- Event {c.event_id}: {c.reason} (Confidence: {c.confidence_score})")

        if runbooks:
            lines.append("Relevant Runbook Excerpts:")
            for r in runbooks[:3]:
                lines.append(f"- [{r.citation_reference}]: {r.content[:300]}")

        return "\n".join(lines)

    def _extract_citations(
        self,
        answer: str,
        incident: IncidentDetailResponse,
        runbooks: list[SearchResultItem],
    ) -> list[EvidenceCitation]:
        """Extract explicit citations referenced in the assistant's answer."""
        citations: list[EvidenceCitation] = []
        now = datetime.now(UTC)

        # Check for log citations
        for c in incident.correlations:
            if c.event_id in answer:
                citations.append(
                    EvidenceCitation(
                        citation_type=CitationType.LOG_EVENT,
                        source_id=c.event_id,
                        service_name=incident.lead_service,
                        timestamp=now,
                        excerpt=c.reason or "Correlated error event",
                        reference=f"[Log: {c.event_id} ({incident.lead_service})]",
                    )
                )

        # Check for runbook citations
        for r in runbooks:
            if r.document_id in answer or (r.title and r.title.lower() in answer.lower()):
                citations.append(
                    EvidenceCitation(
                        citation_type=CitationType.RUNBOOK,
                        source_id=r.document_id,
                        service_name=r.service_name,
                        excerpt=r.content[:150],
                        reference=r.citation_reference,
                    )
                )

        # Default fallback citation if none detected directly in text
        if not citations and incident.correlations:
            top_corr = incident.correlations[0]
            citations.append(
                EvidenceCitation(
                    citation_type=CitationType.LOG_EVENT,
                    source_id=top_corr.event_id,
                    service_name=incident.lead_service,
                    timestamp=now,
                    excerpt=top_corr.reason or "Correlated event",
                    reference=f"[Log: {top_corr.event_id} ({incident.lead_service})]",
                )
            )

        return citations

    def _generate_followups(
        self,
        current_query: str,
        incident: IncidentDetailResponse,
    ) -> list[str]:
        """Produce relevant investigation follow-up questions."""
        return [
            f"What happened in {incident.lead_service} right before the first failure?",
            "What diagnostic commands should I run to inspect downstream database locks?",
            "Are there any similar historical incidents with documented resolutions?",
        ]
