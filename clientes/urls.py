from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('buscar/', views.buscar_clientes, name='buscar_clientes'),
    path('get-cidades/', views.get_cidades, name='get_cidades'),
    path('resultados/<int:busca_id>/', views.resultados_busca, name='resultados_busca'),
    path('historico/', views.historico_buscas, name='historico_buscas'),
    path('exportar/<int:busca_id>/', views.exportar_csv, name='exportar_csv'),
]
