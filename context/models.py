"""
Models for the Context Management System.

This module defines the database schema for storing document metadata,
chunks, versions, conflicts, and ingestion logs.
"""

import uuid
import hashlib
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Document(models.Model):
    """
    Represents a Markdown document that has been indexed.

    Stores metadata about the source file and its processing status.
    """

    DOMAIN_CHOICES = [
        ('business', 'Business Logic'),
        ('technical', 'Technical Documentation'),
        ('features', 'Feature Documentation'),
        ('flows', 'User Flows'),
        ('integrations', 'External Integrations'),
        ('architecture', 'System Architecture'),
        ('glossary', 'Terminology & Glossary'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=500, unique=True, db_index=True)
    filename = models.CharField(max_length=255)
    title = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=50, choices=DOMAIN_CHOICES, default='other')

    # Content tracking
    content_hash = models.CharField(max_length=64, help_text="SHA-256 hash of content")
    version = models.PositiveIntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(default=timezone.now)
    file_modified_at = models.DateTimeField(null=True, blank=True)

    # Statistics
    chunk_count = models.PositiveIntegerField(default=0)
    word_count = models.PositiveIntegerField(default=0)
    char_count = models.PositiveIntegerField(default=0)

    # Status
    is_active = models.BooleanField(default=True)
    processing_error = models.TextField(blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f"{self.filename} ({self.domain})"

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def needs_update(self, new_content: str) -> bool:
        """Check if document needs to be reprocessed."""
        return self.content_hash != self.compute_hash(new_content)


class Chunk(models.Model):
    """
    Represents a semantic chunk of a document.

    Each chunk is stored as a vector in ChromaDB and contains
    metadata for retrieval and citation.
    """

    CHUNK_TYPE_CHOICES = [
        ('document_summary', 'Document Summary'),
        ('section', 'Section'),
        ('subsection', 'Subsection'),
        ('paragraph', 'Paragraph'),
        ('code', 'Code Block'),
        ('table', 'Table'),
        ('list', 'List'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )

    # Content
    content = models.TextField()
    content_hash = models.CharField(max_length=64)
    chunk_type = models.CharField(max_length=50, choices=CHUNK_TYPE_CHOICES)

    # Hierarchy
    section = models.CharField(max_length=300, blank=True, db_index=True)
    subsection = models.CharField(max_length=300, blank=True)
    hierarchy_path = models.JSONField(default=list, help_text="Breadcrumb path")
    heading_level = models.PositiveSmallIntegerField(default=0)

    # Position in source
    line_start = models.PositiveIntegerField()
    line_end = models.PositiveIntegerField()
    char_start = models.PositiveIntegerField(default=0)
    char_end = models.PositiveIntegerField(default=0)
    chunk_index = models.PositiveIntegerField(default=0, help_text="Order within document")

    # Extracted metadata
    topics = models.JSONField(default=list, help_text="Identified topics")
    entities = models.JSONField(default=list, help_text="Named entities")
    keywords = models.JSONField(default=list, help_text="Important keywords")

    # Vector store reference
    vector_id = models.CharField(max_length=100, unique=True, db_index=True)
    embedding_model = models.CharField(max_length=100, default='text-embedding-3-small')

    # Statistics
    token_count = models.PositiveIntegerField(default=0)
    word_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        verbose_name = 'Chunk'
        verbose_name_plural = 'Chunks'
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['chunk_type']),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.filename}"

    @property
    def source_reference(self) -> str:
        """Return a citation-friendly source reference."""
        return f"{self.document.path}:{self.line_start}-{self.line_end}"


class ContextVersion(models.Model):
    """
    Snapshot of the context at a point in time.

    Used for versioning and rollback capabilities.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tag = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)

    # Snapshot data
    document_ids = models.JSONField(default=list)
    chunk_ids = models.JSONField(default=list)

    # Statistics
    document_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # ChromaDB collection name for this version
    collection_name = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Context Version'
        verbose_name_plural = 'Context Versions'

    def __str__(self):
        return f"v{self.tag} ({self.document_count} docs)"


class ConflictLog(models.Model):
    """
    Records detected conflicts between documents.

    A conflict occurs when the same term or concept is defined
    differently in multiple documents.
    """

    CONFLICT_TYPE_CHOICES = [
        ('definition', 'Conflicting Definitions'),
        ('value', 'Conflicting Values'),
        ('procedure', 'Conflicting Procedures'),
        ('terminology', 'Terminology Mismatch'),
        ('outdated', 'Outdated Information'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Conflict details
    term = models.CharField(max_length=200, db_index=True)
    conflict_type = models.CharField(max_length=50, choices=CONFLICT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    description = models.TextField(help_text="Description of the conflict")

    # Sources
    source_a = models.ForeignKey(
        Chunk,
        on_delete=models.CASCADE,
        related_name='conflicts_as_source_a'
    )
    source_b = models.ForeignKey(
        Chunk,
        on_delete=models.CASCADE,
        related_name='conflicts_as_source_b'
    )

    # Context snippets
    snippet_a = models.TextField(help_text="Relevant text from source A")
    snippet_b = models.TextField(help_text="Relevant text from source B")

    # Resolution
    resolved = models.BooleanField(default=False)
    resolution_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_conflicts'
    )

    # Timestamps
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'Conflict Log'
        verbose_name_plural = 'Conflict Logs'

    def __str__(self):
        return f"Conflict: {self.term} ({self.conflict_type})"


class IngestionLog(models.Model):
    """
    Log of document ingestion operations.

    Provides audit trail and debugging information for
    the context processing pipeline.
    """

    ACTION_CHOICES = [
        ('created', 'Document Created'),
        ('updated', 'Document Updated'),
        ('deleted', 'Document Deleted'),
        ('reprocessed', 'Document Reprocessed'),
        ('error', 'Processing Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ingestion_logs'
    )
    document_path = models.CharField(max_length=500, help_text="Path at time of ingestion")

    # Action details
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # Processing stats
    chunks_created = models.PositiveIntegerField(default=0)
    chunks_updated = models.PositiveIntegerField(default=0)
    chunks_deleted = models.PositiveIntegerField(default=0)

    # Performance
    processing_time_ms = models.PositiveIntegerField(default=0)
    embedding_time_ms = models.PositiveIntegerField(default=0)

    # Error handling
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ingestion Log'
        verbose_name_plural = 'Ingestion Logs'

    def __str__(self):
        status = "OK" if self.success else "FAILED"
        return f"{self.action} {self.document_path} [{status}]"


class QueryLog(models.Model):
    """
    Log of semantic queries made to the context system.

    Useful for analytics, debugging, and improving retrieval.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Query details
    query = models.TextField()
    query_embedding_id = models.CharField(max_length=100, blank=True)

    # Filters applied
    filters = models.JSONField(default=dict)
    top_k = models.PositiveIntegerField(default=5)

    # Results
    result_count = models.PositiveIntegerField(default=0)
    result_chunk_ids = models.JSONField(default=list)
    result_scores = models.JSONField(default=list)

    # Context generated
    context_tokens = models.PositiveIntegerField(default=0)

    # Performance
    search_time_ms = models.PositiveIntegerField(default=0)

    # User context (optional)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    session_id = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Query Log'
        verbose_name_plural = 'Query Logs'

    def __str__(self):
        return f"Query: {self.query[:50]}... ({self.result_count} results)"


class DomainTerm(models.Model):
    """
    Domain-specific terminology extracted from documents.

    Used for building a glossary and improving search relevance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Term details
    term = models.CharField(max_length=200, unique=True, db_index=True)
    normalized_term = models.CharField(max_length=200, db_index=True)

    # Definition
    definition = models.TextField(blank=True)
    definition_source = models.ForeignKey(
        Chunk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='defined_terms'
    )

    # Aliases
    aliases = models.JSONField(default=list, help_text="Alternative names/spellings")

    # Usage
    occurrence_count = models.PositiveIntegerField(default=0)
    documents = models.ManyToManyField(Document, related_name='terms')

    # Classification
    category = models.CharField(max_length=100, blank=True)
    is_acronym = models.BooleanField(default=False)

    # Vector for semantic matching
    vector_id = models.CharField(max_length=100, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['term']
        verbose_name = 'Domain Term'
        verbose_name_plural = 'Domain Terms'

    def __str__(self):
        return self.term


class CoverageReport(models.Model):
    """
    Periodic reports on context coverage.

    Tracks what areas of the SaaS are well-documented vs. lacking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Report metadata
    report_date = models.DateField(auto_now_add=True)

    # Coverage by domain
    coverage_by_domain = models.JSONField(default=dict)

    # Statistics
    total_documents = models.PositiveIntegerField(default=0)
    total_chunks = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    total_terms = models.PositiveIntegerField(default=0)

    # Gaps identified
    missing_topics = models.JSONField(default=list)
    outdated_documents = models.JSONField(default=list)

    # Quality metrics
    avg_chunk_size = models.FloatField(default=0)
    avg_chunks_per_doc = models.FloatField(default=0)
    conflict_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-report_date']
        verbose_name = 'Coverage Report'
        verbose_name_plural = 'Coverage Reports'

    def __str__(self):
        return f"Coverage Report {self.report_date}"
