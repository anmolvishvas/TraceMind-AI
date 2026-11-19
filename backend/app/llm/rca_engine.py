"""Evidence-based Root Cause Analysis (RCA) engine enforcing strict citation of logs and runbooks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.llm.client import LLMClient
from app.llm.prompts import RCA_SYSTEM_PROMPT
from app.schemas.anomaly import AnomalyRecord
from app.schemas.incident import IncidentDetailResponse
from app.schemas.rag import SearchResultItem
from app.schemas.rca import (
    CitationType,
    EvidenceCitation,
    LikelihoodLevel,
    RCAResponse,
    RootCauseHypothesis,
)

logger = logging.getLogger("tracemind.llm.rca_engine")


class RCAEngine:
    """
    Synthesizes multi-dimensional incident context (telemetry, timeline, errors,
    statistical anomalies, and retrieved runbooks) into evidence-grounded root cause analyses.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def analyze_incident(
        self,
        incident: IncidentDetailResponse,
        anomalies: list[AnomalyRecord] | None = None,
        runbooks: list[SearchResultItem] | None = None,
        additional_notes: str | None = None,
    ) -> RCAResponse:
        """
        Synthesize incident telemetry and documentation into a structured RCAResponse.
        """
        # 1. Format incident context
        user_prompt = self._build_rca_prompt(
            incident=incident,
            anomalies=anomalies or [],
            runbooks=runbooks or [],
            additional_notes=additional_notes,
        )

        # 2. Query LLM with JSON mode
        raw_json = await self.llm_client.generate_json(
            system_prompt=RCA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # 3. Parse and validate JSON into RCAResponse schema
        return self._parse_rca_response(
            incident_id=incident.incident_id,
            raw_json=raw_json,
        )

    def _build_rca_prompt(
        self,
        incident: IncidentDetailResponse,
        anomalies: list[AnomalyRecord],
        runbooks: list[SearchResultItem],
        additional_notes: str | None = None,
    ) -> str:
        """Assemble structured context prompt for the LLM."""
        prompt_parts: list[str] = [
            f"# INCIDENT TO INVESTIGATE: {incident.incident_id}",
            f"Title: {incident.title}",
            f"Severity: {incident.severity.value}",
            f"Lead Service: {incident.lead_service}",
            f"Affected Services: {', '.join(incident.affected_services)}",
            f"Error Signatures: {', '.join(incident.error_signatures)}",
            f"Started At: {incident.started_at.isoformat()}",
            f"Detected At: {incident.detected_at.isoformat()}",
            "",
            "## CHRONOLOGICAL PROGRESSION TIMELINE:",
        ]

        if incident.timeline and incident.timeline.milestones:
            for ms in incident.timeline.milestones:
                prompt_parts.append(
                    f"- [{ms.timestamp.isoformat()}] [{ms.milestone_type.value}] "
                    f"Service: {ms.service_name} | {ms.description}"
                )
        else:
            prompt_parts.append("- No timeline milestones recorded.")

        prompt_parts.append("")
        prompt_parts.append("## CORRELATED LOG EVENTS & EXCEPTIONS:")
        if incident.correlations:
            for c in incident.correlations[:20]:  # Limit top 20 to preserve token budget
                prompt_parts.append(
                    f"- Event ID: {c.event_id} | Type: {c.correlation_type.value} | "
                    f"Confidence: {c.confidence_score} | Reason: {c.reason}"
                )
        else:
            prompt_parts.append("- No correlated log events directly attached.")

        prompt_parts.append("")
        prompt_parts.append("## STATISTICAL ANOMALIES DETECTED:")
        if anomalies:
            for a in anomalies[:10]:
                prompt_parts.append(
                    f"- [{a.timestamp.isoformat()}] Service: {a.service_name} | "
                    f"Metric: {a.metric_name} | Value: {a.current_value} (Baseline: {a.baseline_mean} ± {a.baseline_std}) | "
                    f"Method: {a.detection_method.value} | Severity: {a.severity.value}"
                )
        else:
            prompt_parts.append("- No statistical anomalies flagged for this window.")

        prompt_parts.append("")
        prompt_parts.append("## RETRIEVED HISTORICAL RUNBOOKS & POST-MORTEMS (RAG):")
        if runbooks:
            for r in runbooks[:5]:
                prompt_parts.append(
                    f"### Citation: {r.citation_reference}\n"
                    f"Document ID: {r.document_id} | Service: {r.service_name} | Title: {r.title}\n"
                    f"Content:\n{r.content[:500]}\n"
                )
        else:
            prompt_parts.append("- No matching runbooks or post-mortems retrieved.")

        if additional_notes:
            prompt_parts.append("")
            prompt_parts.append(f"## ADDITIONAL OPERATOR NOTES:\n{additional_notes}")

        prompt_parts.append("")
        prompt_parts.append(
            "Synthesize this operational evidence and return a JSON object with keys: "
            "executive_summary, hypotheses, primary_root_cause, affected_components, "
            "cascading_propagation, immediate_mitigation_steps, preventive_actions, "
            "recommended_runbooks, diagnostic_commands, uncertainty_disclaimer."
        )

        return "\n".join(prompt_parts)

    def _parse_rca_response(
        self,
        incident_id: str,
        raw_json: dict[str, Any],
    ) -> RCAResponse:
        """Parse raw JSON from LLM into strongly validated Pydantic model."""
        now = datetime.now(UTC)

        hypotheses_data = raw_json.get("hypotheses", [])
        parsed_hypotheses: list[RootCauseHypothesis] = []

        for h in hypotheses_data:
            citations_raw = h.get("supporting_evidence", [])
            citations = [
                EvidenceCitation(
                    citation_type=CitationType(c.get("citation_type", "LOG_EVENT")),
                    source_id=c.get("source_id", "unknown"),
                    service_name=c.get("service_name"),
                    timestamp=now,
                    excerpt=c.get("excerpt", ""),
                    reference=c.get("reference", "[Reference]"),
                )
                for c in citations_raw
            ]

            parsed_hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id=h.get("hypothesis_id", f"hyp-{len(parsed_hypotheses) + 1}"),
                    title=h.get("title", "Unknown Hypothesis"),
                    description=h.get("description", ""),
                    likelihood=LikelihoodLevel(h.get("likelihood", "MEDIUM")),
                    confidence_score=float(h.get("confidence_score", 0.5)),
                    supporting_evidence=citations,
                    falsification_checks=h.get("falsification_checks", []),
                )
            )

        if not parsed_hypotheses:
            # Fallback hypothesis if LLM returned empty list
            parsed_hypotheses.append(
                RootCauseHypothesis(
                    hypothesis_id="hyp-001",
                    title="Inconclusive telemetry failure",
                    description="Insufficient log data to isolate specific root cause with high confidence.",
                    likelihood=LikelihoodLevel.LOW,
                    confidence_score=0.3,
                    supporting_evidence=[],
                    falsification_checks=["Inspect service logs directly for unhandled panics"],
                )
            )

        primary_h = parsed_hypotheses[0] if parsed_hypotheses else None

        runbook_citations: list[EvidenceCitation] = []
        for rb in raw_json.get("recommended_runbooks", []):
            runbook_citations.append(
                EvidenceCitation(
                    citation_type=CitationType.RUNBOOK,
                    source_id=rb.get("source_id", "doc-unknown"),
                    service_name=rb.get("service_name"),
                    excerpt=rb.get("excerpt", ""),
                    reference=rb.get("reference", "[Runbook]"),
                )
            )

        return RCAResponse(
            incident_id=incident_id,
            executive_summary=raw_json.get(
                "executive_summary",
                f"Incident analysis for {incident_id}.",
            ),
            hypotheses=parsed_hypotheses,
            primary_root_cause=primary_h,
            affected_components=raw_json.get("affected_components", []),
            cascading_propagation=raw_json.get("cascading_propagation", []),
            immediate_mitigation_steps=raw_json.get("immediate_mitigation_steps", []),
            preventive_actions=raw_json.get("preventive_actions", []),
            recommended_runbooks=runbook_citations,
            diagnostic_commands=raw_json.get("diagnostic_commands", []),
            uncertainty_disclaimer=raw_json.get(
                "uncertainty_disclaimer",
                (
                    "Root causes presented are AI-generated hypotheses based on observed telemetry. "
                    "Engineers must verify using the provided falsification checks before making production changes."
                ),
            ),
            generated_at=now,
            model_used=self.llm_client.model,
        )
