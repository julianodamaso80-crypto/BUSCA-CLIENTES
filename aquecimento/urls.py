from django.urls import path
from . import views

app_name = 'aquecimento'

urlpatterns = [
    # Dashboard
    path('', views.aquecimento_dashboard, name='dashboard'),

    # Planos
    path('criar/', views.criar_plano, name='criar_plano'),
    path('<int:plano_id>/', views.detalhe_plano, name='detalhe_plano'),

    # Chips
    path('<int:plano_id>/adicionar-chip/', views.adicionar_chip, name='adicionar_chip'),
    path('<int:plano_id>/chip-status/<int:chip_id>/', views.chip_qr_status, name='chip_qr_status'),
    path('<int:plano_id>/remover-chip/<int:chip_id>/', views.remover_chip, name='remover_chip'),

    # Controle do aquecimento
    path('<int:plano_id>/iniciar/', views.iniciar_aquecimento, name='iniciar'),
    path('<int:plano_id>/pausar/', views.pausar_aquecimento, name='pausar'),
    path('<int:plano_id>/retomar/', views.retomar_aquecimento, name='retomar'),
    path('<int:plano_id>/executar-ciclo/', views.executar_ciclo, name='executar_ciclo'),

    # Status e monitoramento
    path('<int:plano_id>/status/', views.status_aquecimento, name='status'),
    path('<int:plano_id>/verificar-chips/', views.verificar_chips, name='verificar_chips'),

    # Grupo
    path('<int:plano_id>/criar-grupo/', views.criar_grupo, name='criar_grupo'),

    # Historico
    path('<int:plano_id>/historico/', views.historico_conversas, name='historico'),
    path('<int:plano_id>/conversa/<int:conversa_id>/', views.ver_conversa, name='ver_conversa'),
]
