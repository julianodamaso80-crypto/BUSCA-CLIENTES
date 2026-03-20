"""
Vector Store Service.

Manages vector storage and retrieval using ChromaDB.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings

from .chunker import Chunk
from .embedder import EmbeddingResult
from ..utils.logger import get_logger


@dataclass
class SearchResult:
    """Result from a vector search."""
    chunk_id: str
    score: float
    content: str
    metadata: Dict[str, Any]
    document_path: str
    section: str
    line_start: int
    line_end: int


class VectorStoreService:
    """
    Service for managing vector storage with ChromaDB.

    Handles:
    - Collection management
    - Vector insertion and updates
    - Similarity search
    - Metadata filtering
    """

    DEFAULT_COLLECTION = "knowledge_base"

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = DEFAULT_COLLECTION
    ):
        """
        Initialize the vector store.

        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the collection to use
        """
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError:
            raise ImportError("chromadb package required. Install with: pip install chromadb")

        self.logger = get_logger()

        # Set up persistence directory
        if persist_directory is None:
            persist_directory = getattr(settings, 'CHROMA_PERSIST_DIRECTORY', None)
            if persist_directory is None:
                persist_directory = str(Path(settings.BASE_DIR) / 'chroma_db')

        self.persist_directory = persist_directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self.collection_name = collection_name
        self._collection = None

        self.logger.info(
            "Vector store initialized",
            directory=persist_directory,
            collection=collection_name
        )

    @property
    def collection(self):
        """Get or create the collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
        return self._collection

    def add_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[EmbeddingResult],
        document_path: str
    ) -> int:
        """
        Add chunks with their embeddings to the store.

        Args:
            chunks: List of Chunk objects
            embeddings: List of EmbeddingResult objects
            document_path: Path of the source document

        Returns:
            Number of chunks added
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length")

        ids = []
        vectors = []
        metadatas = []
        documents = []

        for chunk, embedding in zip(chunks, embeddings):
            ids.append(chunk.id)
            vectors.append(embedding.vector)
            documents.append(chunk.content)

            metadata = {
                "document_path": document_path,
                "chunk_type": chunk.chunk_type,
                "section": chunk.section or "",
                "subsection": chunk.subsection or "",
                "hierarchy_path": " > ".join(chunk.hierarchy_path),
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "word_count": chunk.word_count,
                "chunk_index": chunk.chunk_index,
                "content_hash": chunk.content_hash,
            }

            # Add keywords as metadata
            if chunk.keywords:
                metadata["keywords"] = ", ".join(chunk.keywords[:10])

            metadatas.append(metadata)

        # Add to collection
        self.collection.add(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents
        )

        self.logger.info(
            f"Added {len(chunks)} chunks to vector store",
            document=document_path
        )

        return len(chunks)

    def update_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[EmbeddingResult],
        document_path: str
    ) -> int:
        """
        Update existing chunks in the store.

        Args:
            chunks: List of Chunk objects
            embeddings: List of EmbeddingResult objects
            document_path: Path of the source document

        Returns:
            Number of chunks updated
        """
        ids = []
        vectors = []
        metadatas = []
        documents = []

        for chunk, embedding in zip(chunks, embeddings):
            ids.append(chunk.id)
            vectors.append(embedding.vector)
            documents.append(chunk.content)

            metadata = {
                "document_path": document_path,
                "chunk_type": chunk.chunk_type,
                "section": chunk.section or "",
                "subsection": chunk.subsection or "",
                "hierarchy_path": " > ".join(chunk.hierarchy_path),
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "word_count": chunk.word_count,
                "chunk_index": chunk.chunk_index,
                "content_hash": chunk.content_hash,
            }

            if chunk.keywords:
                metadata["keywords"] = ", ".join(chunk.keywords[:10])

            metadatas.append(metadata)

        self.collection.update(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents
        )

        self.logger.info(
            f"Updated {len(chunks)} chunks in vector store",
            document=document_path
        )

        return len(chunks)

    def delete_by_document(self, document_path: str) -> int:
        """
        Delete all chunks from a document.

        Args:
            document_path: Path of the document

        Returns:
            Number of chunks deleted
        """
        # Get IDs to delete
        results = self.collection.get(
            where={"document_path": document_path},
            include=[]
        )

        if results['ids']:
            self.collection.delete(ids=results['ids'])
            self.logger.info(
                f"Deleted {len(results['ids'])} chunks",
                document=document_path
            )
            return len(results['ids'])

        return 0

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        include_content: bool = True
    ) -> List[SearchResult]:
        """
        Search for similar chunks.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Metadata filters (ChromaDB where clause)
            include_content: Whether to include content in results

        Returns:
            List of SearchResult objects
        """
        include = ["metadatas", "distances"]
        if include_content:
            include.append("documents")

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=filters,
            include=include
        )

        search_results = []

        if results['ids'] and results['ids'][0]:
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                distance = results['distances'][0][i] if results['distances'] else 0

                # Convert distance to similarity score (cosine)
                score = 1 - distance

                content = ""
                if include_content and results.get('documents'):
                    content = results['documents'][0][i]

                search_results.append(SearchResult(
                    chunk_id=chunk_id,
                    score=score,
                    content=content,
                    metadata=metadata,
                    document_path=metadata.get('document_path', ''),
                    section=metadata.get('section', ''),
                    line_start=metadata.get('line_start', 0),
                    line_end=metadata.get('line_end', 0)
                ))

        return search_results

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get chunks by their IDs.

        Args:
            ids: List of chunk IDs

        Returns:
            List of chunk data dictionaries
        """
        results = self.collection.get(
            ids=ids,
            include=["metadatas", "documents"]
        )

        chunks = []
        for i, chunk_id in enumerate(results['ids']):
            chunks.append({
                'id': chunk_id,
                'content': results['documents'][i] if results['documents'] else "",
                'metadata': results['metadatas'][i] if results['metadatas'] else {}
            })

        return chunks

    def get_document_chunks(self, document_path: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a document.

        Args:
            document_path: Path of the document

        Returns:
            List of chunk data dictionaries
        """
        results = self.collection.get(
            where={"document_path": document_path},
            include=["metadatas", "documents"]
        )

        chunks = []
        for i, chunk_id in enumerate(results['ids']):
            chunks.append({
                'id': chunk_id,
                'content': results['documents'][i] if results['documents'] else "",
                'metadata': results['metadatas'][i] if results['metadatas'] else {}
            })

        # Sort by chunk_index
        chunks.sort(key=lambda x: x['metadata'].get('chunk_index', 0))

        return chunks

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with statistics
        """
        count = self.collection.count()

        # Get unique documents
        results = self.collection.get(include=["metadatas"])
        documents = set()
        chunk_types = {}

        if results['metadatas']:
            for meta in results['metadatas']:
                doc = meta.get('document_path', '')
                if doc:
                    documents.add(doc)

                chunk_type = meta.get('chunk_type', 'unknown')
                chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

        return {
            'total_chunks': count,
            'total_documents': len(documents),
            'chunk_types': chunk_types,
            'collection_name': self.collection_name,
            'persist_directory': self.persist_directory
        }

    def reset(self) -> None:
        """Reset the collection (delete all data)."""
        self.client.delete_collection(self.collection_name)
        self._collection = None
        self.logger.warning("Vector store collection reset", collection=self.collection_name)

    def create_version_snapshot(self, version_tag: str) -> str:
        """
        Create a snapshot collection for versioning.

        Args:
            version_tag: Tag for the version

        Returns:
            Name of the snapshot collection
        """
        snapshot_name = f"{self.collection_name}_v_{version_tag}"

        # Get all data from current collection
        all_data = self.collection.get(
            include=["metadatas", "documents", "embeddings"]
        )

        if not all_data['ids']:
            return snapshot_name

        # Create snapshot collection
        snapshot = self.client.get_or_create_collection(
            name=snapshot_name,
            metadata={"hnsw:space": "cosine", "version": version_tag}
        )

        snapshot.add(
            ids=all_data['ids'],
            embeddings=all_data['embeddings'],
            metadatas=all_data['metadatas'],
            documents=all_data['documents']
        )

        self.logger.info(
            f"Created version snapshot",
            version=version_tag,
            chunks=len(all_data['ids'])
        )

        return snapshot_name
