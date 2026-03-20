"""
Ingestion Service.

Handles document ingestion into the context system.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from django.utils import timezone

from .parser import MarkdownParser, ParsedDocument
from .chunker import SemanticChunker, Chunk, ChunkConfig
from .embedder import EmbeddingService
from .vectorstore import VectorStoreService
from ..utils.logger import get_logger


class IngestionService:
    """
    Service for ingesting documents into the context system.

    Orchestrates the full pipeline:
    1. Parse markdown files
    2. Chunk into semantic units
    3. Generate embeddings
    4. Store in vector database
    """

    def __init__(
        self,
        parser: Optional[MarkdownParser] = None,
        chunker: Optional[SemanticChunker] = None,
        embedder: Optional[EmbeddingService] = None,
        vectorstore: Optional[VectorStoreService] = None,
        chunk_config: Optional[ChunkConfig] = None
    ):
        """
        Initialize the ingestion service.

        Args:
            parser: MarkdownParser instance
            chunker: SemanticChunker instance
            embedder: EmbeddingService instance
            vectorstore: VectorStoreService instance
            chunk_config: ChunkConfig for chunking
        """
        self.logger = get_logger()

        self.parser = parser or MarkdownParser()
        self.chunker = chunker or SemanticChunker(chunk_config)
        self.embedder = embedder
        self.vectorstore = vectorstore

        # Lazy initialization flags
        self._embedder_initialized = embedder is not None
        self._vectorstore_initialized = vectorstore is not None

    def _ensure_services(self):
        """Ensure all services are initialized."""
        if not self._embedder_initialized:
            try:
                self.embedder = EmbeddingService(provider='openai')
            except Exception:
                self.embedder = EmbeddingService(provider='sentence-transformers')
            self._embedder_initialized = True

        if not self._vectorstore_initialized:
            self.vectorstore = VectorStoreService()
            self._vectorstore_initialized = True

    def ingest_file(
        self,
        file_path: Path,
        force: bool = False
    ) -> Tuple[int, int, int]:
        """
        Ingest a single markdown file.

        Args:
            file_path: Path to the markdown file
            force: Force re-ingestion even if unchanged

        Returns:
            Tuple of (chunks_created, chunks_updated, processing_time_ms)
        """
        self._ensure_services()

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.suffix.lower() in ('.md', '.markdown'):
            raise ValueError(f"Not a markdown file: {file_path}")

        self.logger.log_ingestion_start(str(file_path))
        start_time = time.time()

        try:
            # Parse the document
            parsed = self.parser.parse_file(file_path)

            # Check if document needs update (by hash)
            from ..models import Document
            doc_path = str(file_path)
            content_hash = Document.compute_hash(parsed.content)

            existing_doc = None
            try:
                existing_doc = Document.objects.get(path=doc_path)
                if not force and existing_doc.content_hash == content_hash:
                    self.logger.info(f"Document unchanged, skipping", path=doc_path)
                    return 0, 0, 0
            except Document.DoesNotExist:
                pass

            # Chunk the document
            chunks = self.chunker.chunk_document(parsed)

            if not chunks:
                self.logger.warning(f"No chunks generated", path=doc_path)
                return 0, 0, int((time.time() - start_time) * 1000)

            # Generate embeddings
            embeddings = self.embedder.embed_chunks(chunks)

            # Delete existing chunks if updating
            if existing_doc:
                self.vectorstore.delete_by_document(doc_path)

            # Add to vector store
            self.vectorstore.add_chunks(chunks, embeddings, doc_path)

            # Update database
            chunks_count = len(chunks)

            if existing_doc:
                existing_doc.content_hash = content_hash
                existing_doc.version += 1
                existing_doc.last_synced_at = timezone.now()
                existing_doc.chunk_count = chunks_count
                existing_doc.word_count = parsed.word_count
                existing_doc.char_count = parsed.char_count
                existing_doc.title = parsed.metadata.title or file_path.stem
                existing_doc.domain = parsed.metadata.domain
                existing_doc.processing_error = ""
                existing_doc.save()
                chunks_updated = chunks_count
                chunks_created = 0
            else:
                doc = Document.objects.create(
                    path=doc_path,
                    filename=file_path.name,
                    title=parsed.metadata.title or file_path.stem,
                    description=parsed.metadata.description,
                    domain=parsed.metadata.domain,
                    content_hash=content_hash,
                    chunk_count=chunks_count,
                    word_count=parsed.word_count,
                    char_count=parsed.char_count,
                    last_synced_at=timezone.now()
                )
                chunks_created = chunks_count
                chunks_updated = 0

            # Save chunk metadata to database
            self._save_chunks_to_db(doc_path, chunks, embeddings)

            processing_time = int((time.time() - start_time) * 1000)

            self.logger.log_ingestion_complete(
                path=doc_path,
                chunks=chunks_count,
                time_ms=processing_time
            )

            # Log the ingestion
            self._log_ingestion(
                doc_path=doc_path,
                action='updated' if existing_doc else 'created',
                chunks_created=chunks_created,
                chunks_updated=chunks_updated,
                processing_time_ms=processing_time
            )

            return chunks_created, chunks_updated, processing_time

        except Exception as e:
            self.logger.log_ingestion_error(str(file_path), str(e))
            self._log_ingestion(
                doc_path=str(file_path),
                action='error',
                error_message=str(e)
            )
            raise

    def ingest_directory(
        self,
        directory: Path,
        recursive: bool = True,
        force: bool = False
    ) -> dict:
        """
        Ingest all markdown files in a directory.

        Args:
            directory: Directory path
            recursive: Process subdirectories
            force: Force re-ingestion

        Returns:
            Dictionary with ingestion statistics
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        # Find all markdown files
        pattern = '**/*.md' if recursive else '*.md'
        md_files = list(directory.glob(pattern))

        # Also get .markdown files
        pattern2 = '**/*.markdown' if recursive else '*.markdown'
        md_files.extend(directory.glob(pattern2))

        # Filter out common exclude patterns
        exclude_patterns = ['node_modules', 'venv', '.git', '__pycache__']
        md_files = [
            f for f in md_files
            if not any(exc in str(f) for exc in exclude_patterns)
        ]

        self.logger.info(f"Found {len(md_files)} markdown files", directory=str(directory))

        stats = {
            'total_files': len(md_files),
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total_chunks_created': 0,
            'total_chunks_updated': 0,
            'total_time_ms': 0,
            'files_with_errors': []
        }

        for file_path in md_files:
            try:
                created, updated, time_ms = self.ingest_file(file_path, force=force)

                if created == 0 and updated == 0 and time_ms == 0:
                    stats['skipped'] += 1
                else:
                    stats['processed'] += 1
                    stats['total_chunks_created'] += created
                    stats['total_chunks_updated'] += updated
                    stats['total_time_ms'] += time_ms

            except Exception as e:
                stats['errors'] += 1
                stats['files_with_errors'].append({
                    'file': str(file_path),
                    'error': str(e)
                })

        return stats

    def sync_all(self, docs_directory: Optional[Path] = None) -> dict:
        """
        Synchronize all documents in the default docs directory.

        Args:
            docs_directory: Optional custom directory (defaults to 'docs/')

        Returns:
            Sync statistics
        """
        from django.conf import settings

        if docs_directory is None:
            docs_directory = Path(settings.BASE_DIR) / 'docs'

        if not docs_directory.exists():
            self.logger.warning(f"Docs directory does not exist: {docs_directory}")
            docs_directory.mkdir(parents=True, exist_ok=True)
            return {'total_files': 0, 'message': 'Directory created, no files to sync'}

        return self.ingest_directory(docs_directory, recursive=True)

    def delete_document(self, file_path: str) -> bool:
        """
        Delete a document from the context system.

        Args:
            file_path: Path to the document

        Returns:
            True if deleted, False if not found
        """
        self._ensure_services()

        from ..models import Document, Chunk

        try:
            doc = Document.objects.get(path=file_path)

            # Delete from vector store
            self.vectorstore.delete_by_document(file_path)

            # Delete chunks from DB
            Chunk.objects.filter(document=doc).delete()

            # Delete document
            doc.delete()

            self._log_ingestion(
                doc_path=file_path,
                action='deleted'
            )

            self.logger.info(f"Document deleted", path=file_path)
            return True

        except Document.DoesNotExist:
            return False

    def _save_chunks_to_db(
        self,
        doc_path: str,
        chunks: List[Chunk],
        embeddings: list
    ) -> None:
        """Save chunk metadata to database."""
        from ..models import Document, Chunk as ChunkModel

        try:
            doc = Document.objects.get(path=doc_path)
        except Document.DoesNotExist:
            return

        # Delete existing chunks
        ChunkModel.objects.filter(document=doc).delete()

        # Create new chunks
        chunk_objects = []
        for chunk, embedding in zip(chunks, embeddings):
            chunk_objects.append(ChunkModel(
                id=chunk.id,
                document=doc,
                content=chunk.content,
                content_hash=chunk.content_hash,
                chunk_type=chunk.chunk_type,
                section=chunk.section,
                subsection=chunk.subsection,
                hierarchy_path=chunk.hierarchy_path,
                heading_level=chunk.heading_level,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                chunk_index=chunk.chunk_index,
                topics=chunk.topics,
                entities=chunk.entities,
                keywords=chunk.keywords,
                vector_id=chunk.id,
                embedding_model=embedding.model,
                token_count=embedding.tokens_used,
                word_count=chunk.word_count
            ))

        ChunkModel.objects.bulk_create(chunk_objects)

    def _log_ingestion(
        self,
        doc_path: str,
        action: str,
        chunks_created: int = 0,
        chunks_updated: int = 0,
        chunks_deleted: int = 0,
        processing_time_ms: int = 0,
        error_message: str = ""
    ) -> None:
        """Log ingestion to database."""
        from ..models import Document, IngestionLog

        doc = None
        try:
            doc = Document.objects.get(path=doc_path)
        except Document.DoesNotExist:
            pass

        IngestionLog.objects.create(
            document=doc,
            document_path=doc_path,
            action=action,
            chunks_created=chunks_created,
            chunks_updated=chunks_updated,
            chunks_deleted=chunks_deleted,
            processing_time_ms=processing_time_ms,
            success=action != 'error',
            error_message=error_message
        )
