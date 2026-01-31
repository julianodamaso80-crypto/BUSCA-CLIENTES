from django.urls import path
from . import views

app_name = 'disparo'

urlpatterns = [
    # Dashboard
    path('', views.disparo_dashboard, name='dashboard'),

    # WhatsApp Connection
    path('conectar/', views.conectar_whatsapp, name='conectar'),
    path('api/criar-instancia/', views.criar_instancia, name='criar_instancia'),
    path('api/qrcode/<int:instancia_id>/', views.obter_qrcode, name='obter_qrcode'),
    path('api/verificar-conexao/<int:instancia_id>/', views.verificar_conexao, name='verificar_conexao'),
    path('api/desconectar/<int:instancia_id>/', views.desconectar_instancia, name='desconectar'),
    path('api/deletar-instancia/<int:instancia_id>/', views.deletar_instancia, name='deletar_instancia'),

    # Campanhas
    path('campanha/criar/', views.criar_campanha, name='criar_campanha'),
    path('campanha/<int:campanha_id>/', views.detalhe_campanha, name='detalhe_campanha'),
    path('campanha/<int:campanha_id>/iniciar/', views.iniciar_campanha, name='iniciar_campanha'),
    path('campanha/<int:campanha_id>/pausar/', views.pausar_campanha, name='pausar_campanha'),
    path('campanha/<int:campanha_id>/cancelar/', views.cancelar_campanha, name='cancelar_campanha'),
    path('campanha/<int:campanha_id>/progresso/', views.progresso_campanha, name='progresso_campanha'),

    # Teste
    path('api/enviar-teste/', views.enviar_mensagem_teste, name='enviar_teste'),

    # Configurações
    path('configuracoes/', views.configuracoes, name='configuracoes'),

    # Contatos Bloqueados
    path('bloqueados/', views.contatos_bloqueados, name='contatos_bloqueados'),
    path('api/desbloquear/<int:contato_id>/', views.desbloquear_contato, name='desbloquear_contato'),
]
