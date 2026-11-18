"""Unit tests for PII and sensitive secret scrubbing."""

from app.core.security import PIIScrubber, sanitize_log_message


def test_scrub_aws_and_openai_keys() -> None:
    """Ensure AWS access keys and OpenAI keys are redacted."""
    raw = "Failed AWS upload with key AKIAIOSFODNN7EXAMPLE and sk-proj-12345678901234567890abcdef"
    scrubbed = PIIScrubber.scrub(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED_AWS_KEY]" in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed


def test_scrub_github_tokens_and_jwt() -> None:
    """Ensure GitHub tokens and JWTs are redacted."""
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    raw = f"Auth failed with ghp_1234567890abcdef1234567890abcdef1234 and token={jwt}"
    scrubbed = PIIScrubber.scrub(raw)
    assert "ghp_1234567890" not in scrubbed
    assert "[REDACTED_GITHUB_TOKEN]" in scrubbed
    assert "[REDACTED_JWT]" in scrubbed


def test_scrub_url_embedded_passwords_and_kv_pairs() -> None:
    """Ensure database connection strings and key-value secrets are redacted."""
    raw = "Connecting to postgresql://admin:superSecretPass123@db.prod.internal:5432/main with api_key='secret-key-999'"
    scrubbed = PIIScrubber.scrub(raw)
    assert "superSecretPass123" not in scrubbed
    assert "[REDACTED_CREDENTIAL]" in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_scrub_credit_cards_and_emails() -> None:
    """Ensure credit card numbers and user emails are masked."""
    raw = "Customer user@example.com purchased order with card 4532-1234-5678-9012"
    scrubbed = sanitize_log_message(raw)
    assert "user@example.com" not in scrubbed
    assert "[REDACTED_PII]" in scrubbed
    assert "4532-1234-5678-9012" not in scrubbed
    assert "[REDACTED_CC]" in scrubbed


def test_scrub_private_keys() -> None:
    """Ensure multi-line private keys are scrubbed."""
    raw = (
        "Server startup failed:\n"
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y3...\n"
        "-----END RSA PRIVATE KEY-----\n"
        "Exit code 1"
    )
    scrubbed = PIIScrubber.scrub(raw)
    assert "BEGIN RSA PRIVATE KEY" not in scrubbed
    assert "[REDACTED_PRIVATE_KEY]" in scrubbed
