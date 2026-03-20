"""
Web Views for the Context System.

Provides HTML views for context management dashboard.
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from .managers import ContextManager, ConflictDetector, VersionManager


class DashboardView(LoginRequiredMixin, TemplateView):
    """Context system dashboard."""
    template_name = 'context/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        manager = ContextManager()

        context['stats'] = manager.get_stats()
        context['recent_report'] = manager.get_coverage_report()

        # Get unresolved conflicts count
        detector = ConflictDetector()
        context['unresolved_conflicts'] = len(detector.get_unresolved_conflicts())

        # Get latest version
        version_manager = VersionManager()
        versions = version_manager.list_versions(limit=1)
        context['latest_version'] = versions[0] if versions else None

        return context


class CoverageView(LoginRequiredMixin, TemplateView):
    """Coverage report view."""
    template_name = 'context/coverage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        manager = ContextManager()
        context['report'] = manager.get_coverage_report()

        return context


class IndexView(LoginRequiredMixin, TemplateView):
    """Knowledge index view."""
    template_name = 'context/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        manager = ContextManager()
        context['index'] = manager.get_index()

        return context


class DocumentListView(LoginRequiredMixin, TemplateView):
    """List of indexed documents."""
    template_name = 'context/documents.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from .models import Document

        domain = self.request.GET.get('domain')

        queryset = Document.objects.filter(is_active=True)
        if domain:
            queryset = queryset.filter(domain=domain)

        context['documents'] = queryset.order_by('-updated_at')
        context['selected_domain'] = domain
        context['domains'] = Document.DOMAIN_CHOICES

        return context


class DocumentDetailView(LoginRequiredMixin, TemplateView):
    """Document detail view."""
    template_name = 'context/document_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from .models import Document, Chunk

        doc_id = kwargs.get('doc_id')

        try:
            doc = Document.objects.get(id=doc_id)
            context['document'] = doc
            context['chunks'] = Chunk.objects.filter(document=doc).order_by('chunk_index')
        except Document.DoesNotExist:
            context['document'] = None
            context['error'] = 'Document not found'

        return context


class ConflictListView(LoginRequiredMixin, TemplateView):
    """List of conflicts."""
    template_name = 'context/conflicts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        detector = ConflictDetector()
        context['conflicts'] = detector.get_unresolved_conflicts()

        return context


class QueryView(LoginRequiredMixin, TemplateView):
    """Semantic search interface."""
    template_name = 'context/query.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get('q')

        if query:
            manager = ContextManager()
            result = manager.search(query, top_k=10)
            context['query'] = query
            context['results'] = result['results']
            context['context_text'] = result['context']
            context['search_time'] = result['search_time_ms']
            context['total_tokens'] = result['total_tokens']

        return context
