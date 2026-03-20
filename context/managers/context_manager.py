"""
Context Manager.

Main orchestrator for the context system.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from ..services.ingestion import IngestionService
from ..services.query_engine import QueryEngine
from ..services.vectorstore import VectorStoreService
from ..services.embedder import EmbeddingService
from ..utils.logger import get_logger


class ContextManager:
    """
    Main orchestrator for the context system.

    Coordinates all context operations including:
    - Document ingestion and updates
    - Index management
    - Coverage analysis
    - Context queries
    """

    def __init__(self):
        """Initialize the context manager."""
        self.logger = get_logger()

        # Lazy initialization of services
        self._ingestion_service: Optional[IngestionService] = None
        self._query_engine: Optional[QueryEngine] = None
        self._vectorstore: Optional[VectorStoreService] = None
        self._embedder: Optional[EmbeddingService] = None

    @property
    def ingestion(self) -> IngestionService:
        """Get ingestion service."""
        if self._ingestion_service is None:
            self._ingestion_service = IngestionService()
        return self._ingestion_service

    @property
    def query(self) -> QueryEngine:
        """Get query engine."""
        if self._query_engine is None:
            self._query_engine = QueryEngine()
        return self._query_engine

    @property
    def vectorstore(self) -> VectorStoreService:
        """Get vector store service."""
        if self._vectorstore is None:
            self._vectorstore = VectorStoreService()
        return self._vectorstore

    def process_document(self, path: Path, force: bool = False) -> Dict[str, Any]:
        """
        Process a single document.

        Args:
            path: Path to the document
            force: Force reprocessing

        Returns:
            Processing result dictionary
        """
        try:
            created, updated, time_ms = self.ingestion.ingest_file(path, force=force)
            return {
                'success': True,
                'path': str(path),
                'chunks_created': created,
                'chunks_updated': updated,
                'processing_time_ms': time_ms
            }
        except Exception as e:
            return {
                'success': False,
                'path': str(path),
                'error': str(e)
            }

    def sync_all_documents(self, docs_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Synchronize all documents in the docs directory.

        Args:
            docs_dir: Optional custom docs directory

        Returns:
            Sync statistics
        """
        if docs_dir is None:
            docs_dir = Path(settings.BASE_DIR) / 'docs'

        self.logger.info(f"Starting sync", directory=str(docs_dir))

        return self.ingestion.sync_all(docs_dir)

    def update_document(self, path: str) -> Dict[str, Any]:
        """
        Update a specific document (reprocess if changed).

        Args:
            path: Path to the document

        Returns:
            Update result
        """
        return self.process_document(Path(path), force=False)

    def reprocess_document(self, path: str) -> Dict[str, Any]:
        """
        Force reprocess a document.

        Args:
            path: Path to the document

        Returns:
            Processing result
        """
        return self.process_document(Path(path), force=True)

    def delete_document(self, path: str) -> bool:
        """
        Delete a document from the context system.

        Args:
            path: Path to the document

        Returns:
            True if deleted
        """
        return self.ingestion.delete_document(path)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Perform a semantic search.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            Search results
        """
        result = self.query.search(query, top_k=top_k, filters=filters)

        return {
            'query': result.query,
            'results': [
                {
                    'chunk_id': r.chunk_id,
                    'score': r.score,
                    'content': r.content,
                    'source': r.document_path,
                    'section': r.section,
                    'lines': f"{r.line_start}-{r.line_end}"
                }
                for r in result.results
            ],
            'context': result.context,
            'total_tokens': result.total_tokens,
            'search_time_ms': result.search_time_ms
        }

    def get_index(self) -> Dict[str, Any]:
        """
        Get the knowledge index structure.

        Returns:
            Index structure dictionary
        """
        from ..models import Document, Chunk, DomainTerm

        # Get documents by domain
        documents = Document.objects.filter(is_active=True)

        index = {
            'domains': {},
            'total_documents': documents.count(),
            'total_chunks': Chunk.objects.count(),
            'total_terms': DomainTerm.objects.count()
        }

        # Group by domain
        for doc in documents:
            if doc.domain not in index['domains']:
                index['domains'][doc.domain] = {
                    'documents': [],
                    'chunk_count': 0
                }

            index['domains'][doc.domain]['documents'].append({
                'path': doc.path,
                'title': doc.title,
                'chunks': doc.chunk_count,
                'updated': doc.updated_at.isoformat()
            })
            index['domains'][doc.domain]['chunk_count'] += doc.chunk_count

        return index

    def get_coverage_report(self) -> Dict[str, Any]:
        """
        Generate a coverage report.

        Returns:
            Coverage report dictionary
        """
        from ..models import Document, Chunk, ConflictLog, CoverageReport

        # Calculate statistics
        docs = Document.objects.filter(is_active=True)
        chunks = Chunk.objects.all()

        total_docs = docs.count()
        total_chunks = chunks.count()

        if total_docs == 0:
            return {
                'total_documents': 0,
                'total_chunks': 0,
                'coverage_by_domain': {},
                'message': 'No documents indexed'
            }

        # Coverage by domain
        domain_stats = docs.values('domain').annotate(
            doc_count=Count('id'),
            chunk_count=Sum('chunk_count'),
            word_count=Sum('word_count')
        )

        coverage_by_domain = {
            stat['domain']: {
                'documents': stat['doc_count'],
                'chunks': stat['chunk_count'] or 0,
                'words': stat['word_count'] or 0
            }
            for stat in domain_stats
        }

        # Calculate average stats
        avg_stats = chunks.aggregate(
            avg_size=Avg('word_count'),
            total_tokens=Sum('token_count')
        )

        # Check for conflicts
        unresolved_conflicts = ConflictLog.objects.filter(resolved=False).count()

        # Identify potential gaps
        expected_domains = ['business', 'features', 'flows', 'integrations', 'technical', 'architecture']
        missing_domains = [d for d in expected_domains if d not in coverage_by_domain]

        # Find outdated documents (not updated in 30 days)
        outdated_threshold = timezone.now() - timedelta(days=30)
        outdated_docs = list(docs.filter(updated_at__lt=outdated_threshold).values_list('path', flat=True))

        report = {
            'generated_at': timezone.now().isoformat(),
            'total_documents': total_docs,
            'total_chunks': total_chunks,
            'total_tokens': avg_stats['total_tokens'] or 0,
            'avg_chunk_size': round(avg_stats['avg_size'] or 0, 2),
            'coverage_by_domain': coverage_by_domain,
            'unresolved_conflicts': unresolved_conflicts,
            'missing_domains': missing_domains,
            'outdated_documents': outdated_docs,
            'health_score': self._calculate_health_score(
                total_docs,
                len(missing_domains),
                unresolved_conflicts,
                len(outdated_docs)
            )
        }

        # Save report
        CoverageReport.objects.create(
            coverage_by_domain=coverage_by_domain,
            total_documents=total_docs,
            total_chunks=total_chunks,
            total_tokens=avg_stats['total_tokens'] or 0,
            missing_topics=missing_domains,
            outdated_documents=outdated_docs,
            avg_chunk_size=avg_stats['avg_size'] or 0,
            conflict_count=unresolved_conflicts
        )

        return report

    def _calculate_health_score(
        self,
        total_docs: int,
        missing_domains: int,
        conflicts: int,
        outdated: int
    ) -> int:
        """Calculate a health score from 0-100."""
        if total_docs == 0:
            return 0

        score = 100

        # Penalize missing domains (up to -30)
        score -= min(missing_domains * 5, 30)

        # Penalize conflicts (up to -20)
        score -= min(conflicts * 2, 20)

        # Penalize outdated docs (up to -20)
        outdated_ratio = outdated / total_docs
        score -= int(outdated_ratio * 20)

        # Bonus for having more documents
        if total_docs >= 10:
            score += 10
        elif total_docs >= 5:
            score += 5

        return max(0, min(100, score))

    def get_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics.

        Returns:
            Statistics dictionary
        """
        from ..models import Document, Chunk, IngestionLog, QueryLog

        # Document stats
        doc_stats = Document.objects.filter(is_active=True).aggregate(
            total=Count('id'),
            total_words=Sum('word_count'),
            total_chars=Sum('char_count')
        )

        # Chunk stats
        chunk_stats = Chunk.objects.aggregate(
            total=Count('id'),
            total_tokens=Sum('token_count')
        )

        # Vector store stats
        vs_stats = self.vectorstore.get_stats()

        # Recent activity
        recent_ingestions = IngestionLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        recent_queries = QueryLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()

        return {
            'documents': {
                'total': doc_stats['total'] or 0,
                'total_words': doc_stats['total_words'] or 0,
                'total_chars': doc_stats['total_chars'] or 0
            },
            'chunks': {
                'total': chunk_stats['total'] or 0,
                'total_tokens': chunk_stats['total_tokens'] or 0
            },
            'vector_store': vs_stats,
            'activity': {
                'ingestions_7d': recent_ingestions,
                'queries_7d': recent_queries
            }
        }

    def reset_all(self, confirm: bool = False) -> bool:
        """
        Reset the entire context system.

        Args:
            confirm: Must be True to proceed

        Returns:
            True if reset
        """
        if not confirm:
            return False

        from ..models import Document, Chunk, IngestionLog, QueryLog, ConflictLog

        # Clear vector store
        self.vectorstore.reset()

        # Clear database
        Chunk.objects.all().delete()
        ConflictLog.objects.all().delete()
        IngestionLog.objects.all().delete()
        QueryLog.objects.all().delete()
        Document.objects.all().delete()

        self.logger.warning("Context system reset complete")

        return True
