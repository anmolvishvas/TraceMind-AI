"""PII Scrubber and sensitive credential redaction engine."""

import re
from typing import Final

# Pre-compiled high-performance regex patterns for secrets and sensitive data
AWS_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b((?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16})\b")
OPENAI_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,})\b")
GITHUB_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,})\b")
JWT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
)
BEARER_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(Bearer\s+)[A-Za-z0-9_\-\.~+/=]{20,}\b"
)
PRIVATE_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"
)
PASSWORD_KV_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|auth[_-]?token|access[_-]?token|client[_-]?secret)\s*([:=])\s*['\"]?([^\s'\",;&]+)['\"]?"
)
URL_CREDENTIAL_PATTERN: Final[re.Pattern[str]] = re.compile(r"(https?://)([^:\s]+):([^@\s]+)@")
CREDIT_CARD_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b")
EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

REDACTED_SECRET: Final[str] = "[REDACTED_SECRET]"
REDACTED_TOKEN: Final[str] = "[REDACTED_TOKEN]"
REDACTED_CREDENTIAL: Final[str] = "[REDACTED_CREDENTIAL]"
REDACTED_PII: Final[str] = "[REDACTED_PII]"


class PIIScrubber:
    """
    High-throughput string sanitizer that redacts credentials, API keys, tokens,
    and personally identifiable information (PII) before storage or LLM prompt injection.
    """

    @classmethod
    def scrub(cls, text: str, redact_emails: bool = True) -> str:
        """
        Sanitize input text by applying deterministic redaction rules.

        Args:
            text: The raw log message or stack trace string.
            redact_emails: Whether to redact email addresses.

        Returns:
            The sanitized string with all sensitive elements masked.
        """
        if not text:
            return ""

        # 1. Redact multi-line Private Keys
        scrubbed = PRIVATE_KEY_PATTERN.sub("[REDACTED_PRIVATE_KEY]", text)

        # 2. Redact Known API Keys and Access Tokens
        scrubbed = AWS_KEY_PATTERN.sub("[REDACTED_AWS_KEY]", scrubbed)
        scrubbed = OPENAI_KEY_PATTERN.sub("[REDACTED_API_KEY]", scrubbed)
        scrubbed = GITHUB_TOKEN_PATTERN.sub("[REDACTED_GITHUB_TOKEN]", scrubbed)
        scrubbed = JWT_PATTERN.sub("[REDACTED_JWT]", scrubbed)
        scrubbed = BEARER_TOKEN_PATTERN.sub(r"\1" + REDACTED_TOKEN, scrubbed)

        # 3. Redact embedded credentials in URLs (e.g. postgres://user:pass@host)
        scrubbed = URL_CREDENTIAL_PATTERN.sub(r"\1\2:" + REDACTED_CREDENTIAL + "@", scrubbed)

        # 4. Redact Key-Value Secret assignments (e.g. password=XYZ, secret: "ABC")
        scrubbed = PASSWORD_KV_PATTERN.sub(r"\1\2" + REDACTED_SECRET, scrubbed)

        # 5. Redact Credit Card Numbers
        scrubbed = CREDIT_CARD_PATTERN.sub("[REDACTED_CC]", scrubbed)

        # 6. Redact Emails if enabled
        if redact_emails:
            scrubbed = EMAIL_PATTERN.sub(REDACTED_PII, scrubbed)

        return scrubbed


def sanitize_log_message(message: str) -> str:
    """Functional convenience wrapper for log message sanitization."""
    return PIIScrubber.scrub(message)
