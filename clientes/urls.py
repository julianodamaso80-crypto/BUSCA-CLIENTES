from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('buscar/', views.buscar_clientes, name='buscar_clientes'),
    path('get-cidades/', views.get_cidades, name='get_cidades'),
    path('resultados/<int:busca_id>/', views.resultados_busca, name='resultados_busca'),
    path('historico/', views.historico_buscas, name='historico_buscas'),
    path('exportar/<int:busca_id>/', views.exportar_csv, name='exportar_csv'),
    # Enriquecimento e qualificacao
    path('enriquecer/<int:busca_id>/', views.enriquecer_busca, name='enriquecer_busca'),
    path('leads/<int:busca_id>/', views.leads_qualificados, name='leads_qualificados'),
    path('lead/<int:cliente_id>/', views.detalhe_lead, name='detalhe_lead'),
    path('exportar-qualificados/<int:busca_id>/', views.exportar_qualificados_csv, name='exportar_qualificados_csv'),
]
