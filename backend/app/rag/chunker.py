"""Hierarchical and structure-aware chunking for operational Markdown runbooks and post-mortems."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.rag import DocumentChunk


class MarkdownDocumentChunker:
    """
    Splits operational Markdown documents into semantic chunks preserving heading
    hierarchies, code blocks, diagnostic instructions, and procedures.
    """

    def __init__(
        self,
        max_chunk_chars: int = 1000,
        overlap_chars: int = 150,
        min_chunk_chars: int = 50,
    ) -> None:
        if max_chunk_chars <= overlap_chars:
            raise ValueError("max_chunk_chars must be strictly greater than overlap_chars")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        self.min_chunk_chars = min_chunk_chars
        # Regex to capture Markdown headings (# Heading, ## Subheading)
        self.heading_pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)

    def chunk_document(
        self,
        content: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """
        Split document content into structured chunks with preserved section titles.
        """
        base_meta = document_metadata or {}
        cleaned_content = content.strip()
        if not cleaned_content:
            return []

        # 1. Parse document into sections based on headings
        sections = self._split_by_headings(cleaned_content)

        # 2. Convert each section into one or more chunks respecting size & overlap
        chunks: list[DocumentChunk] = []
        chunk_idx = 0

        for heading, sec_text in sections:
            sec_text = sec_text.strip()
            if not sec_text:
                continue

            if len(sec_text) <= self.max_chunk_chars:
                # Section fits in a single chunk
                token_est = max(1, len(sec_text) // 4)
                chunk_meta = {**base_meta, "section": heading}
                chunks.append(
                    DocumentChunk(
                        chunk_index=chunk_idx,
                        content=sec_text,
                        section_title=heading,
                        token_count=token_est,
                        metadata=chunk_meta,
                    )
                )
                chunk_idx += 1
            else:
                # Subdivide oversized section into overlapping windows
                sub_chunks = self._sliding_window_split(sec_text)
                for sub_text in sub_chunks:
                    sub_text = sub_text.strip()
                    if len(sub_text) < self.min_chunk_chars and chunks:
                        # Append tiny tail fragment to previous chunk if small
                        continue

                    token_est = max(1, len(sub_text) // 4)
                    chunk_meta = {**base_meta, "section": heading, "sub_chunk": True}
                    chunks.append(
                        DocumentChunk(
                            chunk_index=chunk_idx,
                            content=sub_text,
                            section_title=heading,
                            token_count=token_est,
                            metadata=chunk_meta,
                        )
                    )
                    chunk_idx += 1

        # Fallback: if no chunks generated due to min_chunk_chars, emit full content
        if not chunks and cleaned_content:
            chunks.append(
                DocumentChunk(
                    chunk_index=0,
                    content=cleaned_content,
                    section_title=None,
                    token_count=max(1, len(cleaned_content) // 4),
                    metadata=base_meta,
                )
            )

        return chunks

    def _split_by_headings(self, content: str) -> list[tuple[str | None, str]]:
        """
        Split markdown text into (heading, text) pairs.
        """
        matches = list(self.heading_pattern.finditer(content))
        if not matches:
            return [(None, content)]

        sections: list[tuple[str | None, str]] = []
        # Check text before the first heading
        first_start = matches[0].start()
        if first_start > 0:
            preamble = content[:first_start].strip()
            if preamble:
                sections.append((None, preamble))

        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            # Include the heading itself in the body for context
            full_section_text = f"{heading}\n\n{body}" if body else heading
            sections.append((heading, full_section_text))

        return sections

    def _sliding_window_split(self, text: str) -> list[str]:
        """
        Split text into overlapping pieces, attempting to break at paragraphs or newlines.
        """
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.max_chunk_chars, text_len)
            if end < text_len:
                # Try to break at paragraph boundary
                last_newline = text.rfind("\n\n", start, end)
                if last_newline != -1 and last_newline > start + self.overlap_chars:
                    end = last_newline + 2
                else:
                    # Try single newline
                    last_single = text.rfind("\n", start, end)
                    if last_single != -1 and last_single > start + self.overlap_chars:
                        end = last_single + 1
                    else:
                        # Try space boundary
                        last_space = text.rfind(" ", start, end)
                        if last_space != -1 and last_space > start + self.overlap_chars:
                            end = last_space + 1

            chunk_content = text[start:end]
            chunks.append(chunk_content)

            if end >= text_len:
                break
            start = max(start + 1, end - self.overlap_chars)

        return chunks
