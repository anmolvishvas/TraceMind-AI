"""Pydantic v2 validation schemas for LLM Root Cause Analysis (RCA) and Investigation Assistant."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LikelihoodLevel(StrEnum):
    """Categorisation of hypothesis confidence."""

    CONFIRMED = "CONFIRMED"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CitationType(StrEnum):
    """Origin of a cited piece of evidence."""

    LOG_EVENT = "LOG_EVENT"
    RUNBOOK = "RUNBOOK"
    ANOMALY = "ANOMALY"


class EvidenceCitation(BaseModel):
    """Mandatory citation grounding every finding in verified logs or documentation."""

    citation_type: CitationType
    source_id: str = Field(..., description="Log event_id, document_id, or anomaly_id")
    service_name: str | None = Field(default=None, description="Originating service")
    timestamp: datetime | None = Field(default=None, description="Event occurrence timestamp")
    excerpt: str = Field(..., description="Quoted snippet or error message")
    reference: str = Field(
        ...,
        description="Formatted reference, e.g. '[Log: evt-123 @ 10:14:22Z (payment-service)]'",
    )


class RootCauseHypothesis(BaseModel):
    """A ranked root cause hypothesis with supporting evidence and falsification checks."""

    hypothesis_id: str
    title: str = Field(..., description="Concise statement of the proposed root cause")
    description: str = Field(..., description="Technical explanation of the failure mechanism")
    likelihood: LikelihoodLevel
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    supporting_evidence: list[EvidenceCitation] = Field(
        default_factory=list,
        description="Mandatory citations to log events or runbooks supporting this hypothesis",
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list,
        description="Observed evidence or conditions that weaken this hypothesis",
    )
    falsification_checks: list[str] = Field(
        default_factory=list,
        description="Specific tests/queries an engineer should run to prove or disprove this",
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Targeted remediation steps specific to this hypothesis",
    )


class RCARequest(BaseModel):
    """Payload to trigger an LLM-assisted Root Cause Analysis."""

    incident_id: str | None = Field(
        default=None, description="Target incident ID to analyse (optional if provided in path)"
    )
    include_rag_context: bool = Field(
        default=True, description="Whether to query historical runbooks and post-mortems"
    )
    additional_context: str | None = Field(
        default=None, description="Optional engineering notes or domain context"
    )


class RCAResponse(BaseModel):
    """
    Evidence-grounded structured incident root cause analysis.
    The LLM must never present unverified hypotheses as confirmed facts.
    """

    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    executive_summary: str = Field(
        ..., description="High-level incident summary and observed business impact"
    )
    hypotheses: list[RootCauseHypothesis] = Field(
        ..., min_length=1, description="Ranked candidate root cause hypotheses"
    )
    primary_root_cause: RootCauseHypothesis | None = Field(
        default=None, description="Highest likelihood hypothesis if supported by strong evidence"
    )
    affected_components: list[str] = Field(
        default_factory=list, description="List of services, APIs, or databases impacted"
    )
    cascading_propagation: list[str] = Field(
        default_factory=list, description="Step-by-step failure propagation across topology"
    )
    immediate_mitigation_steps: list[str] = Field(
        default_factory=list, description="Immediate actions to restore system stability"
    )
    preventive_actions: list[str] = Field(
        default_factory=list, description="Long-term architectural and configuration fixes"
    )
    recommended_runbooks: list[EvidenceCitation] = Field(
        default_factory=list, description="Citations to retrieved historical runbooks"
    )
    diagnostic_commands: list[str] = Field(
        default_factory=list, description="CLI / SQL commands for live triage"
    )
    uncertainty_disclaimer: str = Field(
        default=(
            "Root causes presented are AI-generated hypotheses based on observed telemetry. "
            "Engineers must verify using the provided falsification checks before making production changes."
        ),
        description="Explicit safety disclaimer",
    )
    generated_at: datetime
    model_used: str


class InvestigationChatMessage(BaseModel):
    """A single turn in the conversational incident investigation dialogue."""

    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    citations: list[EvidenceCitation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class InvestigationChatRequest(BaseModel):
    """Request to the interactive incident investigation assistant."""

    incident_id: str | None = Field(
        default=None, description="Target incident ID (optional if provided in path)"
    )
    query: str = Field(default="", description="Engineer's diagnostic question")
    message: str | None = Field(default=None, description="Alias for query")
    history: list[InvestigationChatMessage] = Field(
        default_factory=list, description="Previous conversation turns"
    )

    @model_validator(mode="before")
    @classmethod
    def unify_query_and_message(cls, data: Any) -> Any:
        if isinstance(data, dict):
            msg = data.get("message")
            qry = data.get("query")
            if msg and not qry:
                data["query"] = msg
            elif qry and not msg:
                data["message"] = qry
        return data


class InvestigationChatResponse(BaseModel):
    """Evidence-grounded response from the incident investigation assistant."""

    incident_id: str
    answer: str
    reply: str | None = None
    content: str | None = None
    citations: list[EvidenceCitation] = Field(
        default_factory=list, description="Supporting evidence cited in the answer"
    )
    suggested_followups: list[str] = Field(
        default_factory=list, description="Relevant next questions to ask"
    )

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ans = data.get("answer") or data.get("reply") or data.get("content") or ""
            data["answer"] = ans
            data["reply"] = ans
            data["content"] = ans
        return data
