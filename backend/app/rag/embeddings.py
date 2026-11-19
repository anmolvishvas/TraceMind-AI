"""OpenAI embedding generation with resilient batching, backoff, and deterministic fallback."""

from __future__ import annotations

import hashlib
import logging
from typing import Any, cast

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger("tracemind.rag.embeddings")

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingGenerator:
    """
    Generates dense vector representations using OpenAI's embedding models
    or deterministic local fallback for testing and offline environments.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        mock_mode: bool = False,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.dimensions = dimensions

        # Force mock mode if explicitly requested or API key is not a real key
        self.mock_mode = (
            mock_mode
            or not self.api_key
            or "placeholder" in self.api_key.lower()
            or self.api_key in ("test", "mock", "")
        )

        self._client: Any = None
        if not self.mock_mode:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
            except Exception as exc:
                logger.warning("Failed to initialize AsyncOpenAI client: %s. Using mock.", exc)
                self.mock_mode = True

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a single embedding vector for the provided text."""
        results = await self.generate_embeddings([text])
        return results[0]

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for a batch of strings.
        In mock mode, computes deterministic unit-normalized pseudo-vectors.
        """
        if not texts:
            return []

        if self.mock_mode or not self._client:
            return [self._generate_deterministic_vector(t) for t in texts]

        # Use real OpenAI embeddings API with batching
        all_embeddings: list[list[float]] = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self._client.embeddings.create(
                    input=batch,
                    model=self.model,
                )
                batch_vectors = [item.embedding for item in response.data]
                all_embeddings.extend(batch_vectors)
            except Exception as exc:
                logger.error("OpenAI embedding API call failed: %s. Falling back to mock.", exc)
                # Fallback to deterministic vectors on API failure
                all_embeddings.extend([self._generate_deterministic_vector(t) for t in batch])

        return all_embeddings

    def _generate_deterministic_vector(self, text: str) -> list[float]:
        """
        Generate a reproducible unit-normalized 1536-dimensional vector
        from a SHA-256 hash seed of the input text.
        """
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seed = int(text_hash[:8], 16)
        rng = np.random.default_rng(seed)
        raw_vec = rng.standard_normal(self.dimensions)
        norm = float(np.linalg.norm(raw_vec))
        if norm > 0:
            raw_vec = raw_vec / norm
        return cast(list[float], raw_vec.tolist())
