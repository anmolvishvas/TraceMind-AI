"""Unit tests for MarkdownDocumentChunker."""

import pytest

from app.rag.chunker import MarkdownDocumentChunker


def test_chunker_empty_and_whitespace() -> None:
    """Verify chunker returns empty list on empty or whitespace strings."""
    chunker = MarkdownDocumentChunker()
    assert chunker.chunk_document("") == []
    assert chunker.chunk_document("    \n\n  ") == []


def test_chunker_invalid_overlap() -> None:
    """Verify ValueError is raised when max_chunk_chars <= overlap_chars."""
    with pytest.raises(ValueError, match="strictly greater"):
        MarkdownDocumentChunker(max_chunk_chars=100, overlap_chars=100)


def test_chunker_headings_preserved() -> None:
    """Verify headings are extracted into section_title and preserved in chunk text."""
    doc = """# Runbook: Redis Memory Saturation

## Symptoms
Redis memory usage exceeds 90%. Cache evictions spiking.

## Immediate Mitigation
Run redis-cli flushdb on cache nodes if transient.
Scale cluster instances.

## Root Cause Analysis
Inspect top memory keys using memory usage command.
"""
    chunker = MarkdownDocumentChunker(max_chunk_chars=500, overlap_chars=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 3
    section_titles = [c.section_title for c in chunks]
    assert any("Symptoms" in (s or "") for s in section_titles)
    assert any("Immediate Mitigation" in (s or "") for s in section_titles)
    assert any("Root Cause Analysis" in (s or "") for s in section_titles)
    assert all(c.token_count > 0 for c in chunks)


def test_chunker_sliding_window_split() -> None:
    """Verify oversized sections are subdivided with overlapping windows."""
    long_section = "## Detailed Diagnostic Logs\n\n" + (
        "Log line message detail data error.\n" * 40
    )
    chunker = MarkdownDocumentChunker(max_chunk_chars=200, overlap_chars=50)
    chunks = chunker.chunk_document(long_section)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= 300  # Within tolerance
        assert c.section_title == "## Detailed Diagnostic Logs"
        assert c.metadata.get("sub_chunk") is True


def test_chunker_no_headings_fallback() -> None:
    """Verify documents without headings are chunked cleanly."""
    plain_text = "This is a plain operational note without any markdown headers.\n\n" * 10
    chunker = MarkdownDocumentChunker(max_chunk_chars=150, overlap_chars=30)
    chunks = chunker.chunk_document(plain_text)

    assert len(chunks) > 1
    assert chunks[0].section_title is None
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
