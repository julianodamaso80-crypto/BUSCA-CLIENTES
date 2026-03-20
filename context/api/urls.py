"""
URL Configuration for Context API.
"""

from django.urls import path

from . import views

app_name = 'context_api'

urlpatterns = [
    # Ingestion
    path('ingest/', views.IngestView.as_view(), name='ingest'),
    path('sync/', views.SyncView.as_view(), name='sync'),

    # Reports & Stats
    path('coverage/', views.CoverageView.as_view(), name='coverage'),
    path('index/', views.IndexView.as_view(), name='index'),
    path('stats/', views.StatsView.as_view(), name='stats'),

    # Query
    path('query/', views.QueryView.as_view(), name='query'),

    # Agent
    path('agent/ask/', views.AgentAskView.as_view(), name='agent_ask'),

    # Conflicts
    path('conflicts/', views.ConflictsView.as_view(), name='conflicts'),
    path('conflicts/<uuid:conflict_id>/resolve/', views.ResolveConflictView.as_view(), name='resolve_conflict'),

    # Versions
    path('versions/', views.VersionView.as_view(), name='versions'),
    path('versions/compare/', views.CompareVersionsView.as_view(), name='compare_versions'),
    path('versions/<str:tag>/', views.VersionDetailView.as_view(), name='version_detail'),

    # Documents
    path('documents/', views.DocumentsView.as_view(), name='documents'),
    path('documents/<uuid:doc_id>/', views.DocumentDetailView.as_view(), name='document_detail'),
]
