"""Custom domain exception hierarchy for TraceMind AI."""

from typing import Any


class TraceMindBaseException(Exception):
    """Base exception class for all TraceMind domain exceptions."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseConnectionError(TraceMindBaseException):
    """Raised when database connection or query execution fails."""


class RedisConnectionError(TraceMindBaseException):
    """Raised when Redis connection, ping, or operation fails."""


class FileValidationException(TraceMindBaseException):
    """Raised when an uploaded file violates MIME, magic bytes, or size limits."""


class LogParsingException(TraceMindBaseException):
    """Raised when log parsing encounters unrecoverable syntax errors."""


class AnomalyDetectionException(TraceMindBaseException):
    """Raised when anomaly evaluation fails due to insufficient baseline or bad inputs."""


class IncidentCorrelationException(TraceMindBaseException):
    """Raised when clustering or correlation logic fails."""


class RAGRetrievalException(TraceMindBaseException):
    """Raised when vector similarity search or document chunking fails."""


class LLMInferenceException(TraceMindBaseException):
    """Raised when external LLM API fails or structured output validation fails."""


class MCPToolException(TraceMindBaseException):
    """Raised when an MCP tool invocation fails."""
