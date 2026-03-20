"""
URL Configuration for Context App.

Includes both API endpoints and web views.
"""

from django.urls import path, include

from . import views

app_name = 'context'

urlpatterns = [
    # Web views
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('coverage/', views.CoverageView.as_view(), name='coverage'),
    path('index/', views.IndexView.as_view(), name='index'),
    path('documents/', views.DocumentListView.as_view(), name='documents'),
    path('documents/<uuid:doc_id>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('conflicts/', views.ConflictListView.as_view(), name='conflicts'),
    path('query/', views.QueryView.as_view(), name='query'),

    # API endpoints
    path('api/', include('context.api.urls')),
]
