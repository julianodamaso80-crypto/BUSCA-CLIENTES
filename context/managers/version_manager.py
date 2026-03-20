"""
Version Manager.

Handles context versioning and snapshots.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from ..services.vectorstore import VectorStoreService
from ..utils.logger import get_logger

User = get_user_model()


class VersionManager:
    """
    Manages context versions and snapshots.

    Provides:
    - Version tagging
    - Snapshot creation
    - Version comparison
    - Rollback capabilities
    """

    def __init__(self, vectorstore: Optional[VectorStoreService] = None):
        """Initialize the version manager."""
        self.logger = get_logger()
        self._vectorstore = vectorstore

    @property
    def vectorstore(self) -> VectorStoreService:
        """Get vector store service."""
        if self._vectorstore is None:
            self._vectorstore = VectorStoreService()
        return self._vectorstore

    def create_version(
        self,
        tag: str,
        description: str = "",
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Create a new version snapshot.

        Args:
            tag: Version tag (e.g., "v1.0", "2024-01-release")
            description: Version description
            user: User creating the version

        Returns:
            Version metadata dictionary
        """
        from ..models import Document, Chunk, ContextVersion

        # Check if tag already exists
        if ContextVersion.objects.filter(tag=tag).exists():
            raise ValueError(f"Version tag '{tag}' already exists")

        # Get current state
        documents = Document.objects.filter(is_active=True)
        chunks = Chunk.objects.all()

        doc_ids = list(documents.values_list('id', flat=True))
        chunk_ids = list(chunks.values_list('id', flat=True))

        # Create snapshot in vector store
        collection_name = self.vectorstore.create_version_snapshot(tag)

        # Calculate total tokens
        total_tokens = sum(c.token_count for c in chunks)

        # Create version record
        version = ContextVersion.objects.create(
            tag=tag,
            description=description,
            document_ids=[str(d) for d in doc_ids],
            chunk_ids=[str(c) for c in chunk_ids],
            document_count=len(doc_ids),
            chunk_count=len(chunk_ids),
            total_tokens=total_tokens,
            collection_name=collection_name,
            created_by=user
        )

        self.logger.info(
            f"Created version",
            tag=tag,
            documents=len(doc_ids),
            chunks=len(chunk_ids)
        )

        return {
            'id': str(version.id),
            'tag': version.tag,
            'description': version.description,
            'document_count': version.document_count,
            'chunk_count': version.chunk_count,
            'total_tokens': version.total_tokens,
            'created_at': version.created_at.isoformat(),
            'collection_name': version.collection_name
        }

    def list_versions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List all versions.

        Args:
            limit: Maximum versions to return

        Returns:
            List of version dictionaries
        """
        from ..models import ContextVersion

        versions = ContextVersion.objects.order_by('-created_at')[:limit]

        return [
            {
                'id': str(v.id),
                'tag': v.tag,
                'description': v.description,
                'document_count': v.document_count,
                'chunk_count': v.chunk_count,
                'total_tokens': v.total_tokens,
                'created_at': v.created_at.isoformat(),
                'created_by': v.created_by.username if v.created_by else None
            }
            for v in versions
        ]

    def get_version(self, tag: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific version by tag.

        Args:
            tag: Version tag

        Returns:
            Version dictionary or None
        """
        from ..models import ContextVersion

        try:
            v = ContextVersion.objects.get(tag=tag)
            return {
                'id': str(v.id),
                'tag': v.tag,
                'description': v.description,
                'document_count': v.document_count,
                'chunk_count': v.chunk_count,
                'total_tokens': v.total_tokens,
                'document_ids': v.document_ids,
                'chunk_ids': v.chunk_ids,
                'created_at': v.created_at.isoformat(),
                'collection_name': v.collection_name
            }
        except ContextVersion.DoesNotExist:
            return None

    def compare_versions(self, tag_a: str, tag_b: str) -> Dict[str, Any]:
        """
        Compare two versions.

        Args:
            tag_a: First version tag
            tag_b: Second version tag

        Returns:
            Comparison dictionary
        """
        from ..models import ContextVersion

        try:
            v_a = ContextVersion.objects.get(tag=tag_a)
            v_b = ContextVersion.objects.get(tag=tag_b)
        except ContextVersion.DoesNotExist as e:
            raise ValueError(f"Version not found: {e}")

        # Compare document sets
        docs_a = set(v_a.document_ids)
        docs_b = set(v_b.document_ids)

        docs_added = list(docs_b - docs_a)
        docs_removed = list(docs_a - docs_b)
        docs_unchanged = list(docs_a & docs_b)

        # Compare chunk sets
        chunks_a = set(v_a.chunk_ids)
        chunks_b = set(v_b.chunk_ids)

        chunks_added = len(chunks_b - chunks_a)
        chunks_removed = len(chunks_a - chunks_b)

        return {
            'version_a': {
                'tag': v_a.tag,
                'documents': v_a.document_count,
                'chunks': v_a.chunk_count,
                'tokens': v_a.total_tokens
            },
            'version_b': {
                'tag': v_b.tag,
                'documents': v_b.document_count,
                'chunks': v_b.chunk_count,
                'tokens': v_b.total_tokens
            },
            'diff': {
                'documents_added': len(docs_added),
                'documents_removed': len(docs_removed),
                'documents_unchanged': len(docs_unchanged),
                'chunks_added': chunks_added,
                'chunks_removed': chunks_removed,
                'token_diff': v_b.total_tokens - v_a.total_tokens
            }
        }

    def delete_version(self, tag: str) -> bool:
        """
        Delete a version.

        Args:
            tag: Version tag to delete

        Returns:
            True if deleted
        """
        from ..models import ContextVersion

        try:
            version = ContextVersion.objects.get(tag=tag)

            # Delete the snapshot collection if it exists
            if version.collection_name:
                try:
                    self.vectorstore.client.delete_collection(version.collection_name)
                except Exception:
                    pass  # Collection might already be deleted

            version.delete()

            self.logger.info(f"Deleted version", tag=tag)
            return True

        except ContextVersion.DoesNotExist:
            return False

    def get_version_stats(self) -> Dict[str, Any]:
        """
        Get statistics about versions.

        Returns:
            Statistics dictionary
        """
        from ..models import ContextVersion

        versions = ContextVersion.objects.all()

        if not versions.exists():
            return {
                'total_versions': 0,
                'latest_version': None,
                'oldest_version': None
            }

        latest = versions.order_by('-created_at').first()
        oldest = versions.order_by('created_at').first()

        return {
            'total_versions': versions.count(),
            'latest_version': {
                'tag': latest.tag,
                'created_at': latest.created_at.isoformat()
            } if latest else None,
            'oldest_version': {
                'tag': oldest.tag,
                'created_at': oldest.created_at.isoformat()
            } if oldest else None,
            'total_snapshots_size': sum(v.chunk_count for v in versions)
        }

    def auto_version(self, prefix: str = "auto") -> Dict[str, Any]:
        """
        Create an automatic version with timestamp.

        Args:
            prefix: Prefix for the tag

        Returns:
            Created version dictionary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = f"{prefix}_{timestamp}"

        return self.create_version(
            tag=tag,
            description=f"Auto-generated version at {timestamp}"
        )
