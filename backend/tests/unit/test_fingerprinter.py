"""Unit tests for the deterministic error signature fingerprinter."""

from app.log_processing.fingerprinter import ErrorFingerprinter


def test_fingerprint_volatile_tokens_normalization() -> None:
    """Verify volatile addresses, timestamps, UUIDs, and paths are stripped."""
    trace1 = (
        "Traceback (most recent call last):\n"
        '  File "/var/app/deploy-1234/handlers/user.py", line 102, in get_user\n'
        "    user = <User object at 0x7fa1b4028c10>\n"
        "  File '/var/app/deploy-1234/db/repo.py', line 54, in query\n"
        "ConnectionError: [2026-11-18 10:14:02.123] Failed for req-4a8f902b-8a7c-4821-b384-cb9188d30e3e on 10.0.1.5:5432"
    )

    trace2 = (
        "Traceback (most recent call last):\n"
        '  File "/root/app/deploy-9999/handlers/user.py", line 108, in get_user\n'
        "    user = <User object at 0x00007ffe34ab12>\n"
        "  File '/root/app/deploy-9999/db/repo.py', line 60, in query\n"
        "ConnectionError: [2026-11-18 10:18:45.999] Failed for req-999f902b-8a7c-4821-b384-cb9188d39999 on 192.168.1.1:5432"
    )

    sig1 = ErrorFingerprinter.compute_signature(
        exception_type="ConnectionError",
        message="Failed for req",
        stack_trace=trace1,
    )
    sig2 = ErrorFingerprinter.compute_signature(
        exception_type="ConnectionError",
        message="Failed for req",
        stack_trace=trace2,
    )

    # Identical underlying stack traces must yield the EXACT same SHA-256 fingerprint
    assert sig1 == sig2
    assert len(sig1) == 64


def test_fingerprint_differing_exceptions_yield_distinct_signatures() -> None:
    """Ensure distinct bugs produce different fingerprints."""
    sig1 = ErrorFingerprinter.compute_signature(
        exception_type="ConnectionRefusedError",
        message="Database port 5432 unreachable",
    )
    sig2 = ErrorFingerprinter.compute_signature(
        exception_type="TimeoutError",
        message="Gateway read timed out after 3000ms",
    )
    assert sig1 != sig2


def test_fingerprint_fallback_for_empty_inputs() -> None:
    """Verify fallback signature for empty or None inputs."""
    sig = ErrorFingerprinter.compute_signature(None, None, None)
    assert len(sig) == 64
