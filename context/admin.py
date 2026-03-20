"""
Admin configuration for Context System models.
"""

from django.contrib import admin

from .models import (
    Document,
    Chunk,
    ContextVersion,
    ConflictLog,
    IngestionLog,
    QueryLog,
    DomainTerm,
    CoverageReport
)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'title', 'domain', 'chunk_count', 'word_count', 'updated_at', 'is_active']
    list_filter = ['domain', 'is_active', 'created_at']
    search_fields = ['filename', 'title', 'path']
    readonly_fields = ['id', 'content_hash', 'created_at', 'updated_at']
    ordering = ['-updated_at']


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_type', 'section', 'chunk_index', 'word_count', 'created_at']
    list_filter = ['chunk_type', 'document__domain']
    search_fields = ['content', 'section', 'subsection']
    readonly_fields = ['id', 'vector_id', 'content_hash', 'created_at', 'updated_at']
    raw_id_fields = ['document']
    ordering = ['document', 'chunk_index']


@admin.register(ContextVersion)
class ContextVersionAdmin(admin.ModelAdmin):
    list_display = ['tag', 'document_count', 'chunk_count', 'total_tokens', 'created_at', 'created_by']
    list_filter = ['created_at']
    search_fields = ['tag', 'description']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(ConflictLog)
class ConflictLogAdmin(admin.ModelAdmin):
    list_display = ['term', 'conflict_type', 'severity', 'resolved', 'detected_at']
    list_filter = ['conflict_type', 'severity', 'resolved']
    search_fields = ['term', 'description']
    readonly_fields = ['id', 'detected_at']
    ordering = ['-detected_at']


@admin.register(IngestionLog)
class IngestionLogAdmin(admin.ModelAdmin):
    list_display = ['document_path', 'action', 'success', 'chunks_created', 'processing_time_ms', 'created_at']
    list_filter = ['action', 'success', 'created_at']
    search_fields = ['document_path']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    list_display = ['query_truncated', 'result_count', 'search_time_ms', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['query']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']

    def query_truncated(self, obj):
        return obj.query[:50] + '...' if len(obj.query) > 50 else obj.query
    query_truncated.short_description = 'Query'


@admin.register(DomainTerm)
class DomainTermAdmin(admin.ModelAdmin):
    list_display = ['term', 'category', 'occurrence_count', 'is_acronym', 'updated_at']
    list_filter = ['category', 'is_acronym']
    search_fields = ['term', 'definition', 'aliases']
    readonly_fields = ['id', 'normalized_term', 'created_at', 'updated_at']
    ordering = ['term']


@admin.register(CoverageReport)
class CoverageReportAdmin(admin.ModelAdmin):
    list_display = ['report_date', 'total_documents', 'total_chunks', 'total_tokens', 'conflict_count']
    list_filter = ['report_date']
    readonly_fields = ['id', 'created_at']
    ordering = ['-report_date']
