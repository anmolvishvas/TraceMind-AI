"""Unit tests for EmbeddingGenerator."""

import numpy as np
import pytest

from app.rag.embeddings import EmbeddingGenerator


@pytest.mark.asyncio
async def test_deterministic_embedding_generation() -> None:
    """Verify mock mode generates unit-normalized reproducible vectors."""
    gen = EmbeddingGenerator(mock_mode=True, dimensions=1536)

    # Empty list handling
    assert await gen.generate_embeddings([]) == []

    # Single text embedding
    vec1 = await gen.generate_embedding("Database connection timeout")
    assert len(vec1) == 1536
    norm = float(np.linalg.norm(vec1))
    assert pytest.approx(norm, rel=1e-4) == 1.0

    # Determinism: same text yields identical vector
    vec2 = await gen.generate_embedding("Database connection timeout")
    assert vec1 == vec2

    # Different text yields distinct vector
    vec3 = await gen.generate_embedding("Kubernetes pod OOMKilled")
    assert vec1 != vec3


@pytest.mark.asyncio
async def test_embedding_batching() -> None:
    """Verify batch embedding generation handles multiple strings."""
    gen = EmbeddingGenerator(mock_mode=True)
    texts = [f"Error log sample #{i}" for i in range(10)]
    vectors = await gen.generate_embeddings(texts)

    assert len(vectors) == 10
    assert all(len(v) == 1536 for v in vectors)


def test_embedding_init_fallback() -> None:
    """Verify generator initializes in mock mode when key is test/mock."""
    gen = EmbeddingGenerator(api_key="test")
    assert gen.mock_mode is True
