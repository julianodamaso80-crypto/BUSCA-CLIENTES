"""
Query Engine Service.

Handles semantic search queries with context assembly.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .embedder import EmbeddingService
from .vectorstore import VectorStoreService, SearchResult
from ..utils.logger import get_logger
from ..utils.text_processing import TextProcessor


@dataclass
class QueryResult:
    """Result of a semantic query."""
    query: str
    results: List[SearchResult]
    context: str
    total_tokens: int
    search_time_ms: int
    filters_applied: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextBlock:
    """A block of context for the agent."""
    source: str
    section: str
    content: str
    relevance_score: float
    line_reference: str


class QueryEngine:
    """
    Engine for semantic search and context retrieval.

    Handles:
    - Query embedding
    - Vector similarity search
    - Result reranking
    - Context assembly
    """

    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        vectorstore: Optional[VectorStoreService] = None
    ):
        """
        Initialize the query engine.

        Args:
            embedder: EmbeddingService instance (creates default if None)
            vectorstore: VectorStoreService instance (creates default if None)
        """
        self.logger = get_logger()

        # Initialize services
        self.embedder = embedder
        self.vectorstore = vectorstore

        self._lazy_init = embedder is None or vectorstore is None

    def _ensure_initialized(self):
        """Lazy initialization of services."""
        if self._lazy_init:
            if self.embedder is None:
                try:
                    self.embedder = EmbeddingService(provider='openai')
                except Exception:
                    # Fallback to local embeddings
                    self.embedder = EmbeddingService(provider='sentence-transformers')

            if self.vectorstore is None:
                self.vectorstore = VectorStoreService()

            self._lazy_init = False

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0
    ) -> QueryResult:
        """
        Perform semantic search.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            min_score: Minimum relevance score

        Returns:
            QueryResult with search results and assembled context
        """
        self._ensure_initialized()

        start_time = time.time()

        # Embed the query
        query_vector = self.embedder.embed_text(query)

        # Search vector store
        results = self.vectorstore.search(
            query_vector=query_vector,
            top_k=top_k * 2,  # Get more for filtering
            filters=filters,
            include_content=True
        )

        # Filter by minimum score
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        # Take top_k after filtering
        results = results[:top_k]

        # Assemble context
        context, total_tokens = self._assemble_context(results)

        elapsed_ms = int((time.time() - start_time) * 1000)

        self.logger.log_search_query(
            query=query,
            results=len(results),
            time_ms=elapsed_ms
        )

        return QueryResult(
            query=query,
            results=results,
            context=context,
            total_tokens=total_tokens,
            search_time_ms=elapsed_ms,
            filters_applied=filters or {}
        )

    def search_with_context(
        self,
        query: str,
        top_k: int = 5,
        include_parent: bool = True,
        include_siblings: bool = False,
        max_context_tokens: int = 4000
    ) -> QueryResult:
        """
        Search with expanded context.

        Args:
            query: Search query
            top_k: Number of results
            include_parent: Include parent section context
            include_siblings: Include sibling chunks
            max_context_tokens: Maximum tokens in context

        Returns:
            QueryResult with expanded context
        """
        # Basic search first
        result = self.search(query, top_k=top_k)

        if not result.results:
            return result

        # Expand context if requested
        expanded_results = list(result.results)

        if include_siblings:
            expanded_results = self._expand_with_siblings(expanded_results)

        # Re-assemble context with limit
        context, total_tokens = self._assemble_context(
            expanded_results,
            max_tokens=max_context_tokens,
            include_parent=include_parent
        )

        result.context = context
        result.total_tokens = total_tokens

        return result

    def get_context_for_agent(
        self,
        query: str,
        max_chunks: int = 5,
        max_tokens: int = 4000
    ) -> List[ContextBlock]:
        """
        Get formatted context blocks for the agent.

        Args:
            query: User query
            max_chunks: Maximum number of chunks
            max_tokens: Maximum tokens

        Returns:
            List of ContextBlock objects
        """
        result = self.search(query, top_k=max_chunks)

        blocks = []
        current_tokens = 0

        for r in result.results:
            # Estimate tokens
            chunk_tokens = TextProcessor.count_tokens_approx(r.content)

            if current_tokens + chunk_tokens > max_tokens:
                break

            blocks.append(ContextBlock(
                source=r.document_path,
                section=r.section,
                content=r.content,
                relevance_score=r.score,
                line_reference=f"{r.line_start}-{r.line_end}"
            ))

            current_tokens += chunk_tokens

        return blocks

    def _assemble_context(
        self,
        results: List[SearchResult],
        max_tokens: int = 8000,
        include_parent: bool = True
    ) -> tuple[str, int]:
        """
        Assemble context from search results.

        Args:
            results: Search results
            max_tokens: Maximum tokens
            include_parent: Include parent context

        Returns:
            Tuple of (assembled context, token count)
        """
        if not results:
            return "", 0

        context_parts = []
        current_tokens = 0

        for i, result in enumerate(results):
            # Format source reference
            source_ref = f"[FONTE {i + 1}: {result.document_path}"
            if result.section:
                source_ref += f", Secao: {result.section}"
            source_ref += f", Linhas: {result.line_start}-{result.line_end}]"

            # Build chunk text
            chunk_text = f"{source_ref}\n{result.content}"

            # Add hierarchy if available
            hierarchy = result.metadata.get('hierarchy_path', '')
            if hierarchy and include_parent:
                chunk_text = f"Contexto: {hierarchy}\n\n{chunk_text}"

            # Estimate tokens
            chunk_tokens = TextProcessor.count_tokens_approx(chunk_text)

            if current_tokens + chunk_tokens > max_tokens:
                # Truncate if needed
                remaining = max_tokens - current_tokens
                if remaining > 100:
                    chunk_text = TextProcessor.truncate_text(
                        chunk_text,
                        remaining * 4  # Approximate chars
                    )
                    chunk_tokens = TextProcessor.count_tokens_approx(chunk_text)
                else:
                    break

            context_parts.append(chunk_text)
            current_tokens += chunk_tokens

        context = "\n\n---\n\n".join(context_parts)
        return context, current_tokens

    def _expand_with_siblings(
        self,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        Expand results with sibling chunks from same document.

        Args:
            results: Original search results

        Returns:
            Expanded list of results
        """
        expanded = list(results)
        seen_ids = {r.chunk_id for r in results}

        for result in results:
            # Get chunks from same document
            doc_chunks = self.vectorstore.get_document_chunks(result.document_path)

            # Find current chunk index
            current_idx = None
            for i, chunk in enumerate(doc_chunks):
                if chunk['id'] == result.chunk_id:
                    current_idx = i
                    break

            if current_idx is None:
                continue

            # Add previous and next chunks
            for offset in [-1, 1]:
                sibling_idx = current_idx + offset
                if 0 <= sibling_idx < len(doc_chunks):
                    sibling = doc_chunks[sibling_idx]
                    if sibling['id'] not in seen_ids:
                        seen_ids.add(sibling['id'])
                        meta = sibling['metadata']
                        expanded.append(SearchResult(
                            chunk_id=sibling['id'],
                            score=result.score * 0.8,  # Lower score for siblings
                            content=sibling['content'],
                            metadata=meta,
                            document_path=meta.get('document_path', ''),
                            section=meta.get('section', ''),
                            line_start=meta.get('line_start', 0),
                            line_end=meta.get('line_end', 0)
                        ))

        # Sort by score
        expanded.sort(key=lambda x: x.score, reverse=True)
        return expanded

    def suggest_related_queries(self, query: str, n: int = 3) -> List[str]:
        """
        Suggest related queries based on indexed content.

        Args:
            query: Original query
            n: Number of suggestions

        Returns:
            List of suggested queries
        """
        # Search for related content
        results = self.search(query, top_k=10)

        # Extract unique sections and keywords
        sections = set()
        keywords = set()

        for r in results.results:
            if r.section:
                sections.add(r.section)

            meta_keywords = r.metadata.get('keywords', '')
            if meta_keywords:
                keywords.update(meta_keywords.split(', '))

        # Generate suggestions
        suggestions = []

        for section in list(sections)[:n]:
            if section.lower() not in query.lower():
                suggestions.append(f"Como funciona {section}?")

        for keyword in list(keywords)[:n - len(suggestions)]:
            if keyword.lower() not in query.lower():
                suggestions.append(f"O que e {keyword}?")

        return suggestions[:n]
