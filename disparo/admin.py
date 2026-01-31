from django.contrib import admin
from .models import (
    InstanciaWhatsApp, ConfiguracaoDisparo, CampanhaDisparo,
    LogEnvio, ContatoBloqueado, EstatisticaDiaria
)


@admin.register(InstanciaWhatsApp)
class InstanciaWhatsAppAdmin(admin.ModelAdmin):
    list_display = ['nome', 'usuario', 'status', 'numero_conectado', 'data_criacao']
    list_filter = ['status', 'data_criacao']
    search_fields = ['nome', 'usuario__username']


@admin.register(ConfiguracaoDisparo)
class ConfiguracaoDisparoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'idade_numero', 'limite_diario', 'delay_minimo', 'delay_maximo']
    list_filter = ['idade_numero']


@admin.register(CampanhaDisparo)
class CampanhaDisparoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'usuario', 'status', 'total_contatos', 'enviados', 'falhas', 'data_criacao']
    list_filter = ['status', 'data_criacao']
    search_fields = ['nome', 'usuario__username']


@admin.register(LogEnvio)
class LogEnvioAdmin(admin.ModelAdmin):
    list_display = ['nome_contato', 'numero', 'campanha', 'status', 'data_envio']
    list_filter = ['status', 'data_criacao']
    search_fields = ['nome_contato', 'numero']


@admin.register(ContatoBloqueado)
class ContatoBloqueadoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'usuario', 'motivo', 'data_bloqueio']
    list_filter = ['motivo', 'data_bloqueio']
    search_fields = ['numero']


@admin.register(EstatisticaDiaria)
class EstatisticaDiariaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'data', 'mensagens_enviadas', 'mensagens_entregues', 'mensagens_falha']
    list_filter = ['data']
