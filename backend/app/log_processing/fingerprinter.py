"""Deterministic error signature fingerprinter for incident clustering and grouping."""

import hashlib
import re
from typing import Final

# Regex patterns to normalize out volatile and dynamic tokens
HEX_ADDRESS_PATTERN: Final[re.Pattern[str]] = re.compile(r"0x[0-9a-fA-F]+")
UUID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
ISO_TIMESTAMP_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
IP_PORT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")
LINE_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?i)(?:line\s+|:)(\d+)(?:\b|,|\))")
FILE_PATH_NORMALIZE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[/\\](?:[a-zA-Z0-9_\.\-]+[/\\])+([a-zA-Z0-9_\.\-]+\.(?:py|java|ts|js|go|rs|cpp|c|cs|rb|php))"
)


class ErrorFingerprinter:
    """
    Computes deterministic SHA-256 signatures for operational errors and stack traces.
    Strips volatile dynamic state (pointers, timestamps, ports, request IDs) to group
    identical root causes accurately.
    """

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Strip ephemeral identifiers, memory pointers, and timestamps from error text.
        """
        if not text:
            return ""

        normalized = text.strip()
        # 1. Replace memory addresses (e.g. 0x7f8a9c1e)
        normalized = HEX_ADDRESS_PATTERN.sub("<HEX>", normalized)
        # 2. Replace UUIDs
        normalized = UUID_PATTERN.sub("<UUID>", normalized)
        # 3. Replace ISO timestamps
        normalized = ISO_TIMESTAMP_PATTERN.sub("<TIMESTAMP>", normalized)
        # 4. Replace IP and ports
        normalized = IP_PORT_PATTERN.sub("<IP:PORT>", normalized)
        # 5. Normalize file paths to basename only (e.g. /opt/app/handlers/auth.py -> auth.py)
        normalized = FILE_PATH_NORMALIZE_PATTERN.sub(r"\1", normalized)
        # 6. Normalize line numbers to avoid fingerprint churn across minor edits
        normalized = LINE_NUMBER_PATTERN.sub(":<LINE>", normalized)

        # 7. Collapse excess whitespace
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def compute_signature(
        cls,
        exception_type: str | None,
        message: str | None,
        stack_trace: str | None = None,
    ) -> str:
        """
        Generate a 64-character SHA-256 fingerprint for the error.

        Args:
            exception_type: The exception class name (e.g. ConnectionRefusedError, NullPointerException).
            message: The error message.
            stack_trace: The full or partial stack trace if available.

        Returns:
            A deterministic 64-character hexadecimal SHA-256 string.
        """
        hasher = hashlib.sha256()

        exc_clean = (exception_type or "").strip().lower()
        hasher.update(exc_clean.encode("utf-8"))
        hasher.update(b"::")

        if stack_trace and stack_trace.strip():
            norm_trace = cls.normalize_text(stack_trace)
            hasher.update(norm_trace.encode("utf-8"))
        elif message and message.strip():
            norm_msg = cls.normalize_text(message)
            hasher.update(norm_msg.encode("utf-8"))
        else:
            hasher.update(b"unknown_error")

        return hasher.hexdigest()
