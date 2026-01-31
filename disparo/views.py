from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
import json

from .models import (
    InstanciaWhatsApp, ConfiguracaoDisparo, CampanhaDisparo,
    LogEnvio, ContatoBloqueado, EstatisticaDiaria
)
from .services import EvolutionAPIService, DisparoService
from clientes.models import BuscaCliente, ClienteEncontrado


@login_required
def disparo_dashboard(request):
    """Dashboard principal de disparo"""
    # Obter ou criar configuração
    config, created = ConfiguracaoDisparo.objects.get_or_create(
        usuario=request.user,
        defaults={'idade_numero': 'novo', 'limite_diario': 50}
    )

    # Instâncias WhatsApp
    instancias = InstanciaWhatsApp.objects.filter(usuario=request.user)

    # Campanhas
    campanhas = CampanhaDisparo.objects.filter(usuario=request.user)[:10]

    # Estatísticas
    disparo_service = DisparoService(request.user)
    mensagens_restantes = disparo_service.mensagens_restantes_hoje()

    # Listas disponíveis (buscas com clientes)
    listas_disponiveis = BuscaCliente.objects.filter(
        usuario=request.user,
        total_resultados__gt=0
    ).order_by('-data_busca')

    context = {
        'config': config,
        'instancias': instancias,
        'campanhas': campanhas,
        'mensagens_restantes': mensagens_restantes,
        'listas_disponiveis': listas_disponiveis,
    }
    return render(request, 'disparo/dashboard.html', context)


@login_required
def conectar_whatsapp(request):
    """Página de conexão com WhatsApp"""
    instancias = InstanciaWhatsApp.objects.filter(usuario=request.user)

    context = {
        'instancias': instancias,
    }
    return render(request, 'disparo/conectar.html', context)


@login_required
@require_POST
def criar_instancia(request):
    """Cria uma nova instância do WhatsApp"""
    nome = request.POST.get('nome', f'instancia_{request.user.id}')

    # Verificar se já existe
    if InstanciaWhatsApp.objects.filter(usuario=request.user, nome=nome).exists():
        return JsonResponse({'success': False, 'error': 'Já existe uma instância com este nome'})

    # Criar no Evolution API
    evolution = EvolutionAPIService()
    resultado = evolution.criar_instancia(nome)

    if resultado['success']:
        instancia = InstanciaWhatsApp.objects.create(
            usuario=request.user,
            nome=nome,
            instance_id=resultado['data'].get('instance', {}).get('instanceId'),
            status='qr_code'
        )
        return JsonResponse({
            'success': True,
            'instancia_id': instancia.id,
            'nome': nome
        })
    else:
        return JsonResponse({'success': False, 'error': resultado.get('error', 'Erro ao criar instância')})


@login_required
@require_GET
def obter_qrcode(request, instancia_id):
    """Obtém o QR Code para conexão"""
    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    evolution = EvolutionAPIService()
    resultado = evolution.obter_qrcode(instancia.nome)

    if resultado['success']:
        data = resultado['data']
        # O QR code pode vir em diferentes formatos
        qr_code = data.get('base64') or data.get('qrcode', {}).get('base64')
        pairingCode = data.get('pairingCode')

        return JsonResponse({
            'success': True,
            'qr_code': qr_code,
            'pairing_code': pairingCode
        })
    else:
        return JsonResponse({'success': False, 'error': resultado.get('error')})


@login_required
@require_GET
def verificar_conexao(request, instancia_id):
    """Verifica o status da conexão"""
    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    evolution = EvolutionAPIService()
    resultado = evolution.verificar_conexao(instancia.nome)

    if resultado['success']:
        data = resultado['data']
        state = data.get('instance', {}).get('state') or data.get('state')

        if state == 'open':
            instancia.status = 'connected'
            instancia.ultima_conexao = timezone.now()
        elif state == 'connecting':
            instancia.status = 'connecting'
        elif state == 'close':
            instancia.status = 'disconnected'
        else:
            instancia.status = 'qr_code'

        instancia.save()

        return JsonResponse({
            'success': True,
            'status': instancia.status,
            'status_display': instancia.get_status_display()
        })
    else:
        return JsonResponse({'success': False, 'error': resultado.get('error')})


@login_required
@require_POST
def desconectar_instancia(request, instancia_id):
    """Desconecta a instância"""
    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    evolution = EvolutionAPIService()
    resultado = evolution.desconectar(instancia.nome)

    if resultado['success']:
        instancia.status = 'disconnected'
        instancia.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'error': resultado.get('error')})


@login_required
@require_POST
def deletar_instancia(request, instancia_id):
    """Deleta a instância"""
    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    evolution = EvolutionAPIService()
    evolution.deletar_instancia(instancia.nome)

    instancia.delete()
    return JsonResponse({'success': True})


@login_required
def criar_campanha(request):
    """Página de criação de campanha"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        instancia_id = request.POST.get('instancia')
        busca_id = request.POST.get('lista')
        mensagem = request.POST.get('mensagem')
        usar_nome = request.POST.get('usar_nome') == 'on'

        # Validações
        instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)
        busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)

        # Criar campanha
        campanha = CampanhaDisparo.objects.create(
            usuario=request.user,
            instancia=instancia,
            busca=busca,
            nome=nome,
            mensagem=mensagem,
            usar_nome_cliente=usar_nome,
        )

        # Criar logs de envio para cada contato
        disparo_service = DisparoService(request.user)
        clientes = ClienteEncontrado.objects.filter(busca=busca)

        contatos_validos = 0
        for cliente in clientes:
            numero = cliente.whatsapp or cliente.telefone
            if numero and disparo_service.validar_numero(numero):
                # Verificar se não está bloqueado
                if not disparo_service.numero_esta_bloqueado(numero):
                    mensagem_personalizada = disparo_service.personalizar_mensagem(
                        mensagem, cliente.nome, usar_nome
                    )
                    LogEnvio.objects.create(
                        campanha=campanha,
                        nome_contato=cliente.nome,
                        numero=numero,
                        mensagem_enviada=mensagem_personalizada,
                        status='pendente'
                    )
                    contatos_validos += 1

        campanha.total_contatos = contatos_validos
        campanha.save()

        messages.success(request, f'Campanha criada com {contatos_validos} contatos!')
        return redirect('disparo:detalhe_campanha', campanha_id=campanha.id)

    # GET - mostrar formulário
    instancias = InstanciaWhatsApp.objects.filter(usuario=request.user, status='connected')
    listas = BuscaCliente.objects.filter(usuario=request.user, total_resultados__gt=0)

    context = {
        'instancias': instancias,
        'listas': listas,
    }
    return render(request, 'disparo/criar_campanha.html', context)


@login_required
def detalhe_campanha(request, campanha_id):
    """Detalhes de uma campanha"""
    campanha = get_object_or_404(CampanhaDisparo, id=campanha_id, usuario=request.user)
    logs = LogEnvio.objects.filter(campanha=campanha)[:100]

    # Estatísticas
    stats = {
        'pendentes': logs.filter(status='pendente').count(),
        'enviados': logs.filter(status='enviado').count(),
        'entregues': logs.filter(status='entregue').count(),
        'falhas': logs.filter(status='falha').count(),
        'bloqueados': logs.filter(status='bloqueado').count(),
    }

    context = {
        'campanha': campanha,
        'logs': logs,
        'stats': stats,
    }
    return render(request, 'disparo/detalhe_campanha.html', context)


@login_required
@require_POST
def iniciar_campanha(request, campanha_id):
    """Inicia o disparo de uma campanha"""
    campanha = get_object_or_404(CampanhaDisparo, id=campanha_id, usuario=request.user)

    # Verificar se instância está conectada
    if campanha.instancia.status != 'connected':
        return JsonResponse({
            'success': False,
            'error': 'WhatsApp não está conectado. Conecte primeiro.'
        })

    # Verificar se pode enviar
    disparo_service = DisparoService(request.user)

    if not disparo_service.pode_enviar_hoje():
        return JsonResponse({
            'success': False,
            'error': 'Limite diário de mensagens atingido.'
        })

    if not disparo_service.esta_no_horario_permitido():
        return JsonResponse({
            'success': False,
            'error': f'Fora do horário permitido ({disparo_service.config.horario_inicio} - {disparo_service.config.horario_fim})'
        })

    # Atualizar status
    campanha.status = 'em_andamento'
    campanha.data_inicio = timezone.now()
    campanha.save()

    return JsonResponse({
        'success': True,
        'message': 'Campanha iniciada! O disparo está em andamento.'
    })


@login_required
@require_POST
def pausar_campanha(request, campanha_id):
    """Pausa uma campanha"""
    campanha = get_object_or_404(CampanhaDisparo, id=campanha_id, usuario=request.user)
    campanha.status = 'pausada'
    campanha.save()

    return JsonResponse({'success': True})


@login_required
@require_POST
def cancelar_campanha(request, campanha_id):
    """Cancela uma campanha"""
    campanha = get_object_or_404(CampanhaDisparo, id=campanha_id, usuario=request.user)
    campanha.status = 'cancelada'
    campanha.save()

    return JsonResponse({'success': True})


@login_required
@require_POST
def enviar_mensagem_teste(request):
    """Envia uma mensagem de teste"""
    data = json.loads(request.body)
    instancia_id = data.get('instancia_id')
    numero = data.get('numero')
    mensagem = data.get('mensagem')

    instancia = get_object_or_404(InstanciaWhatsApp, id=instancia_id, usuario=request.user)

    if instancia.status != 'connected':
        return JsonResponse({'success': False, 'error': 'WhatsApp não está conectado'})

    evolution = EvolutionAPIService()
    resultado = evolution.enviar_mensagem_texto(instancia.nome, numero, mensagem)

    if resultado['success']:
        return JsonResponse({'success': True, 'message': 'Mensagem enviada com sucesso!'})
    else:
        return JsonResponse({'success': False, 'error': resultado.get('error')})


@login_required
def configuracoes(request):
    """Página de configurações de disparo"""
    config, created = ConfiguracaoDisparo.objects.get_or_create(
        usuario=request.user,
        defaults={'idade_numero': 'novo', 'limite_diario': 50}
    )

    if request.method == 'POST':
        config.idade_numero = request.POST.get('idade_numero', 'novo')
        config.limite_diario = int(request.POST.get('limite_diario', 50))
        config.delay_minimo = int(request.POST.get('delay_minimo', 15))
        config.delay_maximo = int(request.POST.get('delay_maximo', 60))
        config.pausa_apos_mensagens = int(request.POST.get('pausa_apos_mensagens', 20))
        config.duracao_pausa = int(request.POST.get('duracao_pausa', 300))
        config.horario_inicio = request.POST.get('horario_inicio', '08:00')
        config.horario_fim = request.POST.get('horario_fim', '20:00')
        config.enviar_apenas_dias_uteis = request.POST.get('enviar_apenas_dias_uteis') == 'on'
        config.max_tentativas_por_contato = int(request.POST.get('max_tentativas_por_contato', 3))
        config.save()

        messages.success(request, 'Configurações salvas com sucesso!')
        return redirect('disparo:configuracoes')

    context = {
        'config': config,
    }
    return render(request, 'disparo/configuracoes.html', context)


@login_required
@require_GET
def progresso_campanha(request, campanha_id):
    """Retorna o progresso da campanha em JSON"""
    campanha = get_object_or_404(CampanhaDisparo, id=campanha_id, usuario=request.user)

    return JsonResponse({
        'status': campanha.status,
        'total': campanha.total_contatos,
        'enviados': campanha.enviados,
        'entregues': campanha.entregues,
        'falhas': campanha.falhas,
        'taxa_entrega': campanha.taxa_entrega,
    })


@login_required
def contatos_bloqueados(request):
    """Lista de contatos bloqueados"""
    bloqueados = ContatoBloqueado.objects.filter(usuario=request.user)

    context = {
        'bloqueados': bloqueados,
    }
    return render(request, 'disparo/contatos_bloqueados.html', context)


@login_required
@require_POST
def desbloquear_contato(request, contato_id):
    """Remove um contato da lista de bloqueados"""
    contato = get_object_or_404(ContatoBloqueado, id=contato_id, usuario=request.user)
    contato.delete()

    return JsonResponse({'success': True})
