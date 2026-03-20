from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
import json
import threading

from .models import (
    PlanoAquecimento, ChipAquecimento, GrupoAquecimento,
    ConversaAquecimento, MensagemAquecimento, LogDiarioAquecimento
)
from .services import AquecimentoService
from disparo.models import InstanciaWhatsApp
from disparo.services import EvolutionAPIService


PERSONAS_PADRAO = [
    {'apelido': 'Carlos', 'persona': 'Homem de 28 anos, trabalha com vendas, gosta de futebol e churrasco'},
    {'apelido': 'Ana', 'persona': 'Mulher de 25 anos, trabalha em escritorio, gosta de series e academia'},
    {'apelido': 'Pedro', 'persona': 'Homem de 32 anos, empreendedor, fala sobre negocios e tecnologia'},
    {'apelido': 'Julia', 'persona': 'Mulher de 22 anos, universitaria, usa muita giria e emoji'},
    {'apelido': 'Rafael', 'persona': 'Homem de 30 anos, trabalha com TI, gosta de games e filmes'},
    {'apelido': 'Mariana', 'persona': 'Mulher de 27 anos, trabalha com marketing, adora viagens'},
    {'apelido': 'Lucas', 'persona': 'Homem de 24 anos, personal trainer, fala de treino e dieta'},
    {'apelido': 'Camila', 'persona': 'Mulher de 29 anos, mae, fala sobre filhos e rotina'},
    {'apelido': 'Bruno', 'persona': 'Homem de 35 anos, motorista de app, pragmatico e direto'},
    {'apelido': 'Fernanda', 'persona': 'Mulher de 26 anos, designer, criativa e usa muitos emojis'},
    {'apelido': 'Thiago', 'persona': 'Homem de 31 anos, vendedor, extrovertido e brincalhao'},
    {'apelido': 'Leticia', 'persona': 'Mulher de 23 anos, estagiaria, animada e curiosa'},
    {'apelido': 'Gustavo', 'persona': 'Homem de 33 anos, engenheiro, analitico mas amigavel'},
    {'apelido': 'Beatriz', 'persona': 'Mulher de 28 anos, professora, paciente e atenciosa'},
    {'apelido': 'Diego', 'persona': 'Homem de 26 anos, freelancer, descontraido e criativo'},
    {'apelido': 'Isabela', 'persona': 'Mulher de 30 anos, advogada, objetiva e inteligente'},
    {'apelido': 'Matheus', 'persona': 'Homem de 22 anos, estudante, fala de festas e rolezinho'},
    {'apelido': 'Larissa', 'persona': 'Mulher de 24 anos, influencer, fala de tendencias e moda'},
    {'apelido': 'Felipe', 'persona': 'Homem de 29 anos, cozinheiro, fala de comida e receitas'},
    {'apelido': 'Amanda', 'persona': 'Mulher de 31 anos, psicologa, reflexiva e empatica'},
]


@login_required
def aquecimento_dashboard(request):
    """Dashboard principal do sistema de aquecimento"""
    planos = PlanoAquecimento.objects.filter(usuario=request.user)
    instancias = InstanciaWhatsApp.objects.filter(usuario=request.user)

    context = {
        'planos': planos,
        'instancias': instancias,
    }
    return render(request, 'aquecimento/dashboard.html', context)


@login_required
def criar_plano(request):
    """Cria um novo plano de aquecimento"""
    if request.method == 'POST':
        nome = request.POST.get('nome', 'Plano de Aquecimento')
        dias = int(request.POST.get('dias_aquecimento', 21))
        msgs_inicio = int(request.POST.get('msgs_dia_inicio', 3))
        msgs_meta = int(request.POST.get('msgs_dia_meta', 200))
        habilitar_grupo = request.POST.get('habilitar_grupo') == 'on'
        habilitar_privado = request.POST.get('habilitar_privado') == 'on'
        delay_min = int(request.POST.get('delay_minimo', 60))
        delay_max = int(request.POST.get('delay_maximo', 300))
        horario_inicio = request.POST.get('horario_inicio', '08:00')
        horario_fim = request.POST.get('horario_fim', '21:00')

        plano = PlanoAquecimento.objects.create(
            usuario=request.user,
            nome=nome,
            dias_aquecimento=dias,
            msgs_dia_inicio=msgs_inicio,
            msgs_dia_meta=msgs_meta,
            habilitar_grupo=habilitar_grupo,
            habilitar_privado=habilitar_privado,
            delay_minimo=delay_min,
            delay_maximo=delay_max,
            horario_inicio=horario_inicio,
            horario_fim=horario_fim,
        )

        messages.success(request, f'Plano "{nome}" criado! Agora adicione os chips.')
        return redirect('aquecimento:detalhe_plano', plano_id=plano.id)

    instancias = InstanciaWhatsApp.objects.filter(usuario=request.user)
    context = {'instancias': instancias}
    return render(request, 'aquecimento/criar_plano.html', context)


@login_required
def detalhe_plano(request, plano_id):
    """Detalhes de um plano de aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    chips = plano.chips.all()
    grupos = plano.grupos.filter(ativo=True)
    conversas = plano.conversas.order_by('-data_ultima_msg')[:20]

    # Calcular progresso
    meta_hoje = plano.calcular_msgs_para_dia()
    progresso_chips = []
    from datetime import date
    for chip in chips:
        log = LogDiarioAquecimento.objects.filter(chip=chip, data=date.today()).first()
        progresso_chips.append({
            'chip': chip,
            'enviadas_hoje': log.msgs_enviadas if log else 0,
            'meta_hoje': meta_hoje,
            'percentual': int((log.msgs_enviadas / meta_hoje * 100) if log and meta_hoje > 0 else 0),
        })

    # Previsao de crescimento
    previsao = []
    for dia in range(1, plano.dias_aquecimento + 1):
        previsao.append({
            'dia': dia,
            'msgs': plano.calcular_msgs_para_dia(dia),
        })

    context = {
        'plano': plano,
        'chips': chips,
        'grupos': grupos,
        'conversas': conversas,
        'progresso_chips': progresso_chips,
        'meta_hoje': meta_hoje,
        'previsao': json.dumps(previsao),
        'personas_disponiveis': PERSONAS_PADRAO,
    }
    return render(request, 'aquecimento/detalhe_plano.html', context)


@login_required
@require_POST
def adicionar_chip(request, plano_id):
    """Adiciona um chip ao plano de aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)

    if plano.chips.count() >= 20:
        return JsonResponse({'success': False, 'error': 'Limite de 20 chips atingido'})

    instancia_id = request.POST.get('instancia_id')
    apelido = request.POST.get('apelido', '')
    persona = request.POST.get('persona', '')

    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    # Se nao informou persona, usar uma aleatoria
    if not persona or not apelido:
        usados = list(plano.chips.values_list('apelido', flat=True))
        disponiveis = [p for p in PERSONAS_PADRAO if p['apelido'] not in usados]
        if disponiveis:
            escolhida = disponiveis[0]
            apelido = apelido or escolhida['apelido']
            persona = persona or escolhida['persona']

    # Buscar numero conectado
    numero = instancia.numero_conectado or ''

    chip = ChipAquecimento.objects.create(
        plano=plano,
        instancia=instancia,
        numero=numero,
        apelido=apelido,
        persona=persona,
        status='conectado' if instancia.status == 'connected' else 'aguardando',
    )

    return JsonResponse({
        'success': True,
        'chip_id': chip.id,
        'apelido': chip.apelido,
        'status': chip.get_status_display(),
    })


@login_required
@require_POST
def remover_chip(request, plano_id, chip_id):
    """Remove um chip do plano"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    chip = get_object_or_404(ChipAquecimento, id=chip_id, plano=plano)
    chip.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def iniciar_aquecimento(request, plano_id):
    """Inicia o aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)

    chips_conectados = plano.chips.filter(status__in=['conectado', 'aquecendo'])
    if chips_conectados.count() < 2:
        return JsonResponse({
            'success': False,
            'error': 'Precisa de pelo menos 2 chips conectados para iniciar'
        })

    # Atualizar status
    plano.status = 'ativo'
    plano.data_inicio = timezone.now()
    plano.dia_atual = 1
    plano.save()

    # Marcar chips como aquecendo
    chips_conectados.update(status='aquecendo')

    # Criar grupo se habilitado
    service = AquecimentoService(plano)
    if plano.habilitar_grupo and not plano.grupos.filter(ativo=True).exists():
        resultado_grupo = service.criar_grupo_aquecimento()
        if not resultado_grupo['success']:
            messages.warning(request, f'Grupo nao foi criado: {resultado_grupo["error"]}')

    return JsonResponse({
        'success': True,
        'message': 'Aquecimento iniciado! Os chips vao comecar a conversar.'
    })


@login_required
@require_POST
def pausar_aquecimento(request, plano_id):
    """Pausa o aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    plano.status = 'pausado'
    plano.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def retomar_aquecimento(request, plano_id):
    """Retoma o aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    plano.status = 'ativo'
    plano.save()
    return JsonResponse({'success': True})


@login_required
@require_POST
def executar_ciclo(request, plano_id):
    """Executa um ciclo de aquecimento manualmente (ou chamado por cron/celery)"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    service = AquecimentoService(plano)
    resultado = service.executar_ciclo()
    return JsonResponse(resultado)


@login_required
@require_GET
def status_aquecimento(request, plano_id):
    """Retorna status atual do aquecimento em JSON"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)

    from datetime import date
    chips_status = []
    for chip in plano.chips.all():
        log = LogDiarioAquecimento.objects.filter(chip=chip, data=date.today()).first()
        chips_status.append({
            'id': chip.id,
            'apelido': chip.apelido,
            'status': chip.status,
            'status_display': chip.get_status_display(),
            'msgs_hoje': log.msgs_enviadas if log else 0,
            'meta_hoje': plano.calcular_msgs_para_dia(),
            'erros': chip.erros_consecutivos,
        })

    conversas_ativas = plano.conversas.filter(ativa=True).count()
    ultimas_msgs = []
    for msg in MensagemAquecimento.objects.filter(
        conversa__plano=plano, enviada=True
    ).order_by('-data_envio')[:10]:
        ultimas_msgs.append({
            'remetente': msg.remetente.apelido,
            'texto': msg.texto[:100],
            'tipo': msg.conversa.tipo,
            'hora': msg.data_envio.strftime('%H:%M') if msg.data_envio else '',
        })

    return JsonResponse({
        'plano_status': plano.status,
        'dia_atual': plano.dia_atual,
        'dias_total': plano.dias_aquecimento,
        'meta_hoje': plano.calcular_msgs_para_dia(),
        'chips': chips_status,
        'conversas_ativas': conversas_ativas,
        'ultimas_mensagens': ultimas_msgs,
    })


@login_required
@require_POST
def verificar_chips(request, plano_id):
    """Verifica status de conexao de todos os chips"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    service = AquecimentoService(plano)
    resultados = service.verificar_status_chips()
    return JsonResponse({'success': True, 'chips': resultados})


@login_required
@require_POST
def criar_grupo(request, plano_id):
    """Cria grupo de aquecimento manualmente"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    service = AquecimentoService(plano)
    resultado = service.criar_grupo_aquecimento()

    if resultado['success']:
        return JsonResponse({
            'success': True,
            'grupo_nome': resultado['grupo'].nome_grupo,
        })
    return JsonResponse(resultado)


@login_required
def historico_conversas(request, plano_id):
    """Historico de conversas do aquecimento"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    conversas = plano.conversas.all()[:50]

    context = {
        'plano': plano,
        'conversas': conversas,
    }
    return render(request, 'aquecimento/historico.html', context)


@login_required
def ver_conversa(request, plano_id, conversa_id):
    """Ve mensagens de uma conversa especifica"""
    plano = get_object_or_404(PlanoAquecimento, id=plano_id, usuario=request.user)
    conversa = get_object_or_404(ConversaAquecimento, id=conversa_id, plano=plano)
    mensagens = conversa.mensagens.all()

    context = {
        'plano': plano,
        'conversa': conversa,
        'mensagens': mensagens,
    }
    return render(request, 'aquecimento/ver_conversa.html', context)
