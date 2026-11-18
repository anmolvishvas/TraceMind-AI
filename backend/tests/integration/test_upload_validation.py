"""Integration tests for file upload validation and constant-memory streaming."""

import io

import pytest

from app.core.exceptions import FileValidationException
from app.log_processing.validator import FileUploadValidator, stream_log_lines


def test_validator_rejects_empty_filename() -> None:
    """Ensure empty or whitespace filename is rejected."""
    validator = FileUploadValidator()
    with pytest.raises(FileValidationException) as exc_info:
        validator.validate_filename("")
    assert "cannot be empty" in str(exc_info.value)


def test_validator_rejects_unsupported_extensions() -> None:
    """Ensure non-log extensions are rejected."""
    validator = FileUploadValidator()
    with pytest.raises(FileValidationException) as exc_info:
        validator.validate_filename("malicious.exe")
    assert "Unsupported file extension" in str(exc_info.value)


def test_validator_rejects_executable_magic_bytes() -> None:
    """Ensure PE and ELF binary headers are rejected."""
    validator = FileUploadValidator()
    # Windows executable
    with pytest.raises(FileValidationException) as exc_info:
        validator.validate_magic_bytes(b"MZ\x90\x00\x03\x00\x00\x00")
    assert "Binary or executable file detected" in str(exc_info.value)

    # Linux ELF executable
    with pytest.raises(FileValidationException) as exc_info:
        validator.validate_magic_bytes(b"\x7fELF\x02\x01\x01\x00")
    assert "Linux ELF" in str(exc_info.value)


def test_validator_rejects_null_byte_binary_streams() -> None:
    """Ensure high density null bytes trigger rejection."""
    validator = FileUploadValidator()
    null_bytes = b"Some prefix" + b"\x00" * 32
    with pytest.raises(FileValidationException) as exc_info:
        validator.validate_magic_bytes(null_bytes)
    assert "Binary null characters detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_log_lines_memory_bounded() -> None:
    """Ensure streaming reader yields lines across arbitrary chunk boundaries."""
    payload = "line 1\nline 2 with data\nline 3 final\n"
    stream = io.BytesIO(payload.encode("utf-8"))

    # Use very small chunk size (4 bytes) to force boundary splitting
    lines = [line async for line in stream_log_lines(stream, chunk_size=4)]
    assert lines == ["line 1", "line 2 with data", "line 3 final"]


@pytest.mark.asyncio
async def test_stream_log_lines_enforces_size_limit() -> None:
    """Ensure reader raises exception when stream exceeds max bytes."""
    payload = "a" * 1024
    stream = io.BytesIO(payload.encode("utf-8"))

    with pytest.raises(FileValidationException) as exc_info:
        _ = [line async for line in stream_log_lines(stream, chunk_size=64, max_total_bytes=512)]
    assert "maximum limit" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_upload_empty_file() -> None:
    """Ensure upload validation raises FileValidationException on empty files."""
    from unittest.mock import AsyncMock

    from fastapi import UploadFile

    validator = FileUploadValidator()
    mock_file = AsyncMock(spec=UploadFile)
    mock_file.filename = "app.log"
    mock_file.read.return_value = b""
    mock_file.size = 0

    with pytest.raises(FileValidationException) as exc_info:
        await validator.validate_upload(mock_file)
    assert "empty" in str(exc_info.value)
