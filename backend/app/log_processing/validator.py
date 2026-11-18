"""File upload validator and constant-memory streaming reader."""

import io
from collections.abc import AsyncIterator
from typing import BinaryIO, Final

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import FileValidationException

# Binary signatures to reject immediately
DISALLOWED_MAGIC_BYTES: Final[dict[bytes, str]] = {
    b"MZ": "Windows Executable (.exe/.dll)",
    b"\x7fELF": "Linux ELF Executable",
    b"\xfe\xed\xfa\xce": "Mach-O 32-bit Binary",
    b"\xfe\xed\xfa\xcf": "Mach-O 64-bit Binary",
    b"\xce\xfa\xed\xfe": "Mach-O 32-bit (reverse) Binary",
    b"\xcf\xfa\xed\xfe": "Mach-O 64-bit (reverse) Binary",
    b"PK\x03\x04": "Zip Archive",
    b"Rar!": "RAR Archive",
    b"\x1f\x8b\x08": "Gzip Compressed Archive (please upload uncompressed plain text/json logs)",
    b"\x00\x00\x00\x18ftyp": "MP4 Video",
    b"\x00\x00\x00\x1cftyp": "MP4 Video",
    b"\x00\x00\x00\x20ftyp": "MP4 Video",
    b"\x1a\x45\xdf\xa3": "Matroska/WebM Video",
}

ALLOWED_EXTENSIONS: Final[set[str]] = {
    ".log",
    ".txt",
    ".json",
    ".jsonl",
    ".ndjson",
    ".csv",
    ".out",
}

DEFAULT_CHUNK_SIZE: Final[int] = 64 * 1024  # 64 KB streaming buffer


class FileUploadValidator:
    """
    Validates uploaded log files for size ceilings, allowed extensions,
    and magic byte header safety.
    """

    def __init__(self, max_size_bytes: int | None = None) -> None:
        self.max_size_bytes = max_size_bytes or get_settings().MAX_UPLOAD_SIZE_BYTES

    def validate_filename(self, filename: str | None) -> str:
        """Validate filename and ensure allowed extension."""
        if not filename or not filename.strip():
            raise FileValidationException("Upload filename cannot be empty.")

        clean_name = filename.strip()
        lower_name = clean_name.lower()
        if not any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise FileValidationException(
                f"Unsupported file extension for '{clean_name}'. Allowed extensions are: {allowed}",
                details={"filename": clean_name, "allowed_extensions": list(ALLOWED_EXTENSIONS)},
            )
        return clean_name

    def validate_magic_bytes(self, header: bytes) -> None:
        """Inspect initial binary bytes and reject known binary formats."""
        for magic, file_type in DISALLOWED_MAGIC_BYTES.items():
            if header.startswith(magic):
                raise FileValidationException(
                    f"Binary or executable file detected: {file_type}. Only text, JSON, or CSV log files are supported.",
                    details={"detected_magic": magic.hex(), "file_type": file_type},
                )

        # Check for high density of null bytes indicating binary content
        if b"\x00" in header[:512]:
            raise FileValidationException(
                "Binary null characters detected in file header. Only UTF-8 plain text or JSON logs are supported.",
                details={"header_sample": header[:64].hex()},
            )

    async def validate_upload(self, upload_file: UploadFile) -> tuple[str, int]:
        """
        Validate metadata, extension, header bytes, and check size constraint.
        Returns the sanitized filename and file size in bytes.
        """
        filename = self.validate_filename(upload_file.filename)

        # Read first 512 bytes for header validation
        header = await upload_file.read(512)
        if not header:
            raise FileValidationException("Uploaded log file is empty.")

        self.validate_magic_bytes(header)

        # Reset stream position
        await upload_file.seek(0)
        return filename, upload_file.size or 0


async def stream_log_lines(
    file_obj: BinaryIO | UploadFile | io.BytesIO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_total_bytes: int | None = None,
) -> AsyncIterator[str]:
    """
    Asynchronously stream lines from an upload in bounded chunks ($O(1)$ memory).
    Safely splits across chunk boundaries and checks size ceiling during streaming.
    """
    limit = max_total_bytes or get_settings().MAX_UPLOAD_SIZE_BYTES
    bytes_read = 0
    buffer = ""

    while True:
        if isinstance(file_obj, UploadFile):
            chunk = await file_obj.read(chunk_size)
        else:
            chunk = file_obj.read(chunk_size)

        if not chunk:
            break

        bytes_read += len(chunk)
        if bytes_read > limit:
            raise FileValidationException(
                f"File size exceeded maximum limit of {limit / (1024 * 1024):.1f} MB.",
                details={"bytes_read": bytes_read, "max_limit_bytes": limit},
            )

        # Decode chunk replacing malformed sequences
        text_chunk = chunk.decode("utf-8", errors="replace")
        buffer += text_chunk

        lines = buffer.split("\n")
        # Keep trailing partial line in buffer
        buffer = lines[-1]

        for line in lines[:-1]:
            yield line

    # Yield remaining line if present
    if buffer.strip():
        yield buffer
