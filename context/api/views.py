"""
API Views for the Context System.

Provides REST endpoints for context management and querying.
"""

import json
from pathlib import Path

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.conf import settings

from ..managers import ContextManager, VersionManager, ConflictDetector
from ..services import AgentInterface


class BaseContextView(View):
    """Base view for context API endpoints."""

    def dispatch(self, request, *args, **kwargs):
        """Handle dispatch with error handling."""
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    def json_body(self, request) -> dict:
        """Parse JSON body from request."""
        if request.body:
            return json.loads(request.body)
        return {}


@method_decorator(csrf_exempt, name='dispatch')
class IngestView(BaseContextView):
    """
    POST /api/context/ingest/
    Ingest a new document.
    """

    def post(self, request):
        data = self.json_body(request)
        path = data.get('path')
        force = data.get('force', False)

        if not path:
            return JsonResponse({
                'success': False,
                'error': 'Path is required'
            }, status=400)

        manager = ContextManager()
        result = manager.process_document(Path(path), force=force)

        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class SyncView(BaseContextView):
    """
    POST /api/context/sync/
    Sync all documents.
    """

    def post(self, request):
        data = self.json_body(request)
        path = data.get('path')

        manager = ContextManager()

        if path:
            result = manager.ingestion.ingest_directory(Path(path))
        else:
            result = manager.sync_all_documents()

        return JsonResponse({
            'success': True,
            **result
        })


class CoverageView(BaseContextView):
    """
    GET /api/context/coverage/
    Get coverage report.
    """

    def get(self, request):
        manager = ContextManager()
        report = manager.get_coverage_report()

        return JsonResponse({
            'success': True,
            'report': report
        })


class IndexView(BaseContextView):
    """
    GET /api/context/index/
    Get knowledge index.
    """

    def get(self, request):
        manager = ContextManager()
        index = manager.get_index()

        return JsonResponse({
            'success': True,
            'index': index
        })


class StatsView(BaseContextView):
    """
    GET /api/context/stats/
    Get context statistics.
    """

    def get(self, request):
        manager = ContextManager()
        stats = manager.get_stats()

        return JsonResponse({
            'success': True,
            'stats': stats
        })


@method_decorator(csrf_exempt, name='dispatch')
class QueryView(BaseContextView):
    """
    POST /api/context/query/
    Perform semantic search.
    """

    def post(self, request):
        data = self.json_body(request)
        query = data.get('query')
        top_k = data.get('top_k', 5)
        filters = data.get('filters')

        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Query is required'
            }, status=400)

        manager = ContextManager()
        result = manager.search(query, top_k=top_k, filters=filters)

        return JsonResponse({
            'success': True,
            **result
        })


@method_decorator(csrf_exempt, name='dispatch')
class AgentAskView(BaseContextView):
    """
    POST /api/agent/ask/
    Ask the agent a question with context.
    """

    def post(self, request):
        data = self.json_body(request)
        question = data.get('question')
        max_chunks = data.get('max_chunks', 5)
        max_tokens = data.get('max_tokens', 4000)

        if not question:
            return JsonResponse({
                'success': False,
                'error': 'Question is required'
            }, status=400)

        agent = AgentInterface()

        # Get prompt and sources
        prompt, sources = agent.build_prompt(
            question,
            max_chunks=max_chunks,
            max_tokens=max_tokens
        )

        # Assess confidence
        context_blocks = agent.query_engine.get_context_for_agent(question, max_chunks)
        confidence, confidence_reason = agent.assess_confidence(question, context_blocks)

        return JsonResponse({
            'success': True,
            'prompt': prompt,
            'sources': [
                {
                    'id': s.id,
                    'file': s.file,
                    'section': s.section,
                    'lines': s.lines,
                    'relevance': s.relevance
                }
                for s in sources
            ],
            'confidence': confidence.value,
            'confidence_reason': confidence_reason,
            'context_count': len(context_blocks)
        })


class ConflictsView(BaseContextView):
    """
    GET /api/context/conflicts/
    Get unresolved conflicts.

    POST /api/context/conflicts/
    Detect new conflicts.
    """

    def get(self, request):
        detector = ConflictDetector()
        conflicts = detector.get_unresolved_conflicts()

        return JsonResponse({
            'success': True,
            'conflicts': conflicts,
            'count': len(conflicts)
        })

    @method_decorator(csrf_exempt)
    def post(self, request):
        detector = ConflictDetector()
        conflicts = detector.detect_all_conflicts()

        return JsonResponse({
            'success': True,
            'detected': len(conflicts),
            'conflicts': conflicts
        })


@method_decorator(csrf_exempt, name='dispatch')
class ResolveConflictView(BaseContextView):
    """
    POST /api/context/conflicts/<id>/resolve/
    Resolve a conflict.
    """

    def post(self, request, conflict_id):
        data = self.json_body(request)
        resolution_note = data.get('resolution_note', '')

        detector = ConflictDetector()
        success = detector.resolve_conflict(
            conflict_id,
            resolution_note,
            user=request.user if request.user.is_authenticated else None
        )

        return JsonResponse({
            'success': success
        })


@method_decorator(csrf_exempt, name='dispatch')
class VersionView(BaseContextView):
    """
    GET /api/context/versions/
    List versions.

    POST /api/context/versions/
    Create a version.
    """

    def get(self, request):
        limit = int(request.GET.get('limit', 10))

        version_manager = VersionManager()
        versions = version_manager.list_versions(limit=limit)

        return JsonResponse({
            'success': True,
            'versions': versions
        })

    @method_decorator(csrf_exempt)
    def post(self, request):
        data = self.json_body(request)
        tag = data.get('tag')
        description = data.get('description', '')

        if not tag:
            return JsonResponse({
                'success': False,
                'error': 'Tag is required'
            }, status=400)

        version_manager = VersionManager()

        try:
            version = version_manager.create_version(
                tag=tag,
                description=description,
                user=request.user if request.user.is_authenticated else None
            )

            return JsonResponse({
                'success': True,
                'version': version
            })
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class VersionDetailView(BaseContextView):
    """
    GET /api/context/versions/<tag>/
    Get version details.

    DELETE /api/context/versions/<tag>/
    Delete a version.
    """

    def get(self, request, tag):
        version_manager = VersionManager()
        version = version_manager.get_version(tag)

        if not version:
            return JsonResponse({
                'success': False,
                'error': 'Version not found'
            }, status=404)

        return JsonResponse({
            'success': True,
            'version': version
        })

    @method_decorator(csrf_exempt)
    def delete(self, request, tag):
        version_manager = VersionManager()
        success = version_manager.delete_version(tag)

        return JsonResponse({
            'success': success
        })


@method_decorator(csrf_exempt, name='dispatch')
class CompareVersionsView(BaseContextView):
    """
    POST /api/context/versions/compare/
    Compare two versions.
    """

    def post(self, request):
        data = self.json_body(request)
        tag_a = data.get('tag_a')
        tag_b = data.get('tag_b')

        if not tag_a or not tag_b:
            return JsonResponse({
                'success': False,
                'error': 'Both tag_a and tag_b are required'
            }, status=400)

        version_manager = VersionManager()

        try:
            comparison = version_manager.compare_versions(tag_a, tag_b)
            return JsonResponse({
                'success': True,
                'comparison': comparison
            })
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class DocumentsView(BaseContextView):
    """
    GET /api/context/documents/
    List indexed documents.
    """

    def get(self, request):
        from ..models import Document

        domain = request.GET.get('domain')
        limit = int(request.GET.get('limit', 50))

        queryset = Document.objects.filter(is_active=True)

        if domain:
            queryset = queryset.filter(domain=domain)

        documents = queryset[:limit]

        return JsonResponse({
            'success': True,
            'documents': [
                {
                    'id': str(d.id),
                    'path': d.path,
                    'title': d.title,
                    'domain': d.domain,
                    'chunk_count': d.chunk_count,
                    'word_count': d.word_count,
                    'updated_at': d.updated_at.isoformat()
                }
                for d in documents
            ],
            'count': queryset.count()
        })


class DocumentDetailView(BaseContextView):
    """
    GET /api/context/documents/<id>/
    Get document details with chunks.

    DELETE /api/context/documents/<id>/
    Delete a document.
    """

    def get(self, request, doc_id):
        from ..models import Document, Chunk

        try:
            doc = Document.objects.get(id=doc_id)
        except Document.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Document not found'
            }, status=404)

        chunks = Chunk.objects.filter(document=doc).order_by('chunk_index')

        return JsonResponse({
            'success': True,
            'document': {
                'id': str(doc.id),
                'path': doc.path,
                'title': doc.title,
                'description': doc.description,
                'domain': doc.domain,
                'chunk_count': doc.chunk_count,
                'word_count': doc.word_count,
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat()
            },
            'chunks': [
                {
                    'id': str(c.id),
                    'type': c.chunk_type,
                    'section': c.section,
                    'content': c.content[:500] + '...' if len(c.content) > 500 else c.content,
                    'line_start': c.line_start,
                    'line_end': c.line_end
                }
                for c in chunks
            ]
        })

    @method_decorator(csrf_exempt)
    def delete(self, request, doc_id):
        from ..models import Document

        try:
            doc = Document.objects.get(id=doc_id)
        except Document.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Document not found'
            }, status=404)

        manager = ContextManager()
        success = manager.delete_document(doc.path)

        return JsonResponse({
            'success': success
        })
