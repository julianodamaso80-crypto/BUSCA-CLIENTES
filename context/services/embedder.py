"""
Embedding Service.

Generates vector embeddings for text chunks using various models.
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings

from .chunker import Chunk
from ..utils.logger import get_logger


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    chunk_id: str
    vector: List[float]
    model: str
    dimensions: int
    tokens_used: int
    time_ms: int


class BaseEmbedder(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Embed a single text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        pass


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

        self.model = model
        self._api_key = api_key or os.getenv('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)

        if not self._api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=self._api_key)

        # Model dimensions
        self._dimensions_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    def embed(self, text: str) -> List[float]:
        """Embed a single text."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        # OpenAI supports batching
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def dimensions(self) -> int:
        return self._dimensions_map.get(self.model, 1536)


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local sentence-transformers embedding provider."""

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package required. "
                "Install with: pip install sentence-transformers"
            )

        self.model = model
        self._model = SentenceTransformer(model)
        self._dimensions = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> List[float]:
        """Embed a single text."""
        embedding = self._model.encode(text)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        embeddings = self._model.encode(texts)
        return [e.tolist() for e in embeddings]

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def dimensions(self) -> int:
        return self._dimensions


class EmbeddingService:
    """
    Service for generating embeddings.

    Supports multiple embedding providers and handles batching.
    """

    PROVIDERS = {
        'openai': OpenAIEmbedder,
        'sentence-transformers': SentenceTransformerEmbedder,
    }

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the embedding service.

        Args:
            provider: 'openai' or 'sentence-transformers'
            model: Model name (provider-specific)
            **kwargs: Additional provider-specific arguments
        """
        self.logger = get_logger()

        if provider not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(self.PROVIDERS.keys())}")

        # Default models per provider
        default_models = {
            'openai': 'text-embedding-3-small',
            'sentence-transformers': 'all-MiniLM-L6-v2',
        }

        model = model or default_models.get(provider)

        try:
            self.embedder = self.PROVIDERS[provider](model=model, **kwargs)
            self.logger.info(f"Initialized {provider} embedder", model=model)
        except Exception as e:
            self.logger.error(f"Failed to initialize embedder", error=str(e))
            raise

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        start_time = time.time()
        vector = self.embedder.embed(text)
        elapsed_ms = int((time.time() - start_time) * 1000)

        self.logger.debug(
            "Text embedded",
            chars=len(text),
            dimensions=len(vector),
            time_ms=elapsed_ms
        )

        return vector

    def embed_texts(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Embed multiple texts with batching.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch

        Returns:
            List of embedding vectors
        """
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1

            start_time = time.time()
            embeddings = self.embedder.embed_batch(batch)
            elapsed_ms = int((time.time() - start_time) * 1000)

            all_embeddings.extend(embeddings)

            self.logger.debug(
                f"Batch {batch_num}/{total_batches} embedded",
                texts=len(batch),
                time_ms=elapsed_ms
            )

        return all_embeddings

    def embed_chunks(self, chunks: List[Chunk]) -> List[EmbeddingResult]:
        """
        Embed a list of chunks.

        Args:
            chunks: List of Chunk objects

        Returns:
            List of EmbeddingResult objects
        """
        results = []

        # Prepare texts with context prefixes
        texts = []
        for chunk in chunks:
            # Add metadata prefix for better retrieval
            prefix_parts = []

            if chunk.section:
                prefix_parts.append(f"[Section: {chunk.section}]")

            if chunk.chunk_type:
                prefix_parts.append(f"[Type: {chunk.chunk_type}]")

            prefix = " ".join(prefix_parts)
            text = f"{prefix}\n{chunk.content}" if prefix else chunk.content
            texts.append(text)

        # Embed all texts
        start_time = time.time()
        embeddings = self.embed_texts(texts)
        total_time = int((time.time() - start_time) * 1000)

        # Create results
        for chunk, vector in zip(chunks, embeddings):
            results.append(EmbeddingResult(
                chunk_id=chunk.id,
                vector=vector,
                model=self.embedder.model_name,
                dimensions=len(vector),
                tokens_used=chunk.token_count_approx,
                time_ms=total_time // len(chunks)
            ))

            self.logger.log_embedding_generated(
                chunk_id=chunk.id,
                model=self.embedder.model_name,
                time_ms=total_time // len(chunks)
            )

        return results

    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self.embedder.model_name

    @property
    def dimensions(self) -> int:
        """Get the embedding dimensions."""
        return self.embedder.dimensions
