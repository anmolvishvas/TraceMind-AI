"""Resilient OpenAI API client with JSON structured output and deterministic mock fallback."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from app.core.config import get_settings

logger = logging.getLogger("tracemind.llm.client")

DEFAULT_LLM_MODEL = "gpt-4o-mini"


class LLMClient:
    """
    Asynchronous client for interacting with LLM providers with automatic fallback
    to deterministic local generation for testing and offline environments.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_LLM_MODEL,
        mock_mode: bool = False,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model

        self.mock_mode = (
            mock_mode
            or not self.api_key
            or "placeholder" in self.api_key.lower()
            or self.api_key in ("test", "mock", "")
        )

        self._client: Any = None
        if not self.mock_mode:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
            except Exception as exc:
                logger.warning("Failed to initialize AsyncOpenAI: %s. Using mock.", exc)
                self.mock_mode = True

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """
        Execute chat completion expecting a structured JSON response.
        """
        if self.mock_mode or not self._client:
            return self._mock_json_response(user_prompt)

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            raw_content = response.choices[0].message.content or "{}"
            return cast(dict[str, Any], json.loads(raw_content))
        except Exception as exc:
            logger.error("LLM API completion failed: %s. Falling back to local mock.", exc)
            return self._mock_json_response(user_prompt)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> str:
        """
        Execute multi-turn chat completion.
        """
        if self.mock_mode or not self._client:
            return self._mock_chat_response(messages)

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM API chat failed: %s. Falling back to mock.", exc)
            return self._mock_chat_response(messages)

    def _mock_json_response(self, user_prompt: str) -> dict[str, Any]:
        """
        Synthesize realistic structured RCA JSON for unit testing and offline development.
        """
        # Extract incident info or service mentions from prompt
        lead_service = "upstream-service"
        if "payment-service" in user_prompt:
            lead_service = "payment-service"
        elif "auth-service" in user_prompt:
            lead_service = "auth-service"

        return {
            "executive_summary": (
                f"Service degradation observed in {lead_service} due to unhandled exceptions "
                "leading to cascading failures across dependent microservices."
            ),
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-001",
                    "title": f"Database connection pool exhaustion in {lead_service}",
                    "description": (
                        f"Excessive latency in downstream queries caused {lead_service} worker threads "
                        "to exhaust the database connection pool, triggering HTTP 500 responses."
                    ),
                    "likelihood": "HIGH",
                    "confidence_score": 0.88,
                    "supporting_evidence": [
                        {
                            "citation_type": "LOG_EVENT",
                            "source_id": "evt-mock-01",
                            "service_name": lead_service,
                            "timestamp": "2026-11-19T10:00:00Z",
                            "excerpt": "TimeoutError: QueuePool limit of size 20 overflow 10 reached",
                            "reference": f"[Log: evt-mock-01 @ 10:00:00Z ({lead_service})]",
                        }
                    ],
                    "falsification_checks": [
                        f"Check active database connections for {lead_service}",
                        "Inspect slow query log for locks lasting > 5 seconds",
                    ],
                }
            ],
            "primary_root_cause": {
                "hypothesis_id": "hyp-001",
                "title": f"Database connection pool exhaustion in {lead_service}",
                "description": f"Worker threads in {lead_service} exhausted the database pool.",
                "likelihood": "HIGH",
                "confidence_score": 0.88,
                "supporting_evidence": [
                    {
                        "citation_type": "LOG_EVENT",
                        "source_id": "evt-mock-01",
                        "service_name": lead_service,
                        "timestamp": "2026-11-19T10:00:00Z",
                        "excerpt": "TimeoutError: QueuePool limit of size 20 overflow 10 reached",
                        "reference": f"[Log: evt-mock-01 @ 10:00:00Z ({lead_service})]",
                    }
                ],
                "falsification_checks": [
                    f"Check active database connections for {lead_service}",
                ],
            },
            "affected_components": [lead_service, "api-gateway"],
            "cascading_propagation": [
                f"{lead_service} encountered pool exhaustion",
                f"api-gateway timed out awaiting response from {lead_service}",
                "Clients received HTTP 504 Gateway Timeout errors",
            ],
            "immediate_mitigation_steps": [
                f"Increase connection pool size for {lead_service}",
                f"Restart stuck instances of {lead_service}",
            ],
            "preventive_actions": [
                "Implement circuit breaker in api-gateway",
                "Add database connection metrics to alerting dashboard",
            ],
            "recommended_runbooks": [
                {
                    "citation_type": "RUNBOOK",
                    "source_id": "doc-runbook-db",
                    "service_name": lead_service,
                    "excerpt": "Database Connection Pool Exhaustion Runbook: §Mitigation",
                    "reference": "[Runbook: Database Pool Runbook, §Mitigation]",
                }
            ],
            "diagnostic_commands": [
                f"kubectl logs -n production -l app={lead_service} --tail=100",
                "SELECT count(*), state FROM pg_stat_activity GROUP BY state;",
            ],
            "uncertainty_disclaimer": (
                "Root causes presented are AI-generated hypotheses based on observed telemetry. "
                "Engineers must verify using the provided falsification checks before making production changes."
            ),
        }

    def _mock_chat_response(self, messages: list[dict[str, str]]) -> str:
        """
        Synthesize realistic interactive assistant chat responses for testing.
        """
        return (
            "Based on the correlated logs and incident timeline, the primary issue originated "
            "from unexpected failures in the service. Specifically, log event indicates an upstream "
            "timeout. [Log: evt-100 @ 10:00:00Z (payment-service)].\n\n"
            "I recommend checking the database locks using:\n"
            "`SELECT * FROM pg_stat_activity WHERE wait_event_type = 'Lock';`"
        )
