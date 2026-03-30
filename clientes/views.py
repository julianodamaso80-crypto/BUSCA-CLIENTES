from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from .models import Estado, Cidade, BuscaCliente, ClienteEncontrado
from .services import GoogleMapsService
from .enrichment import EnrichmentPipeline
import csv
from datetime import datetime, timedelta


@login_required
def dashboard(request):
    # Estatísticas gerais
    total_buscas = BuscaCliente.objects.filter(usuario=request.user).count()
    total_clientes = ClienteEncontrado.objects.filter(busca__usuario=request.user).count()

    # Clientes com WhatsApp
    clientes_whatsapp = ClienteEncontrado.objects.filter(
        busca__usuario=request.user,
        whatsapp__isnull=False
    ).exclude(whatsapp='').count()

    # Últimas buscas
    ultimas_buscas = BuscaCliente.objects.filter(usuario=request.user)[:5]

    # Buscas dos últimos 7 dias
    data_inicio = datetime.now() - timedelta(days=7)
    buscas_semana = BuscaCliente.objects.filter(
        usuario=request.user,
        data_busca__gte=data_inicio
    ).count()

    context = {
        'total_buscas': total_buscas,
        'total_clientes': total_clientes,
        'clientes_whatsapp': clientes_whatsapp,
        'ultimas_buscas': ultimas_buscas,
        'buscas_semana': buscas_semana,
    }
    return render(request, 'clientes/dashboard.html', context)


@login_required
def buscar_clientes(request):
    estados = Estado.objects.all()

    if request.method == 'POST':
        termo_busca = request.POST.get('termo_busca')
        fonte = request.POST.get('fonte', 'google_maps')
        estado_id = request.POST.get('estado')
        cidade_id = request.POST.get('cidade')
        apenas_whatsapp = request.POST.get('apenas_whatsapp') == '1'
        apenas_email = request.POST.get('apenas_email') == '1'
        apenas_endereco = request.POST.get('apenas_endereco') == '1'
        max_resultados = int(request.POST.get('max_resultados', 50))

        # Validações
        if not termo_busca:
            messages.error(request, 'Por favor, informe o termo de busca.')
            return redirect('buscar_clientes')

        # Cria o registro da busca
        busca = BuscaCliente.objects.create(
            usuario=request.user,
            termo_busca=termo_busca,
            fonte=fonte,
            estado_id=estado_id if estado_id else None,
            cidade_id=cidade_id if cidade_id else None,
            apenas_whatsapp=apenas_whatsapp,
            apenas_email=apenas_email,
            apenas_endereco=apenas_endereco,
            max_resultados=max_resultados,
        )

        # Executa a busca
        try:
            if fonte == 'google_maps':
                service = GoogleMapsService()
                service.buscar_clientes(busca)
                messages.success(request, f'Busca concluída! {busca.total_resultados} clientes encontrados.')
            else:
                messages.warning(request, 'Busca no LinkedIn ainda não implementada.')

            return redirect('resultados_busca', busca_id=busca.id)

        except Exception as e:
            messages.error(request, f'Erro ao realizar busca: {str(e)}')
            busca.delete()
            return redirect('buscar_clientes')

    # Lista as últimas buscas do usuário
    ultimas_buscas = BuscaCliente.objects.filter(usuario=request.user)[:5]

    context = {
        'estados': estados,
        'ultimas_buscas': ultimas_buscas,
    }
    return render(request, 'clientes/buscar.html', context)


@login_required
def get_cidades(request):
    estado_id = request.GET.get('estado_id')
    cidades = Cidade.objects.filter(estado_id=estado_id).values('id', 'nome')
    return JsonResponse(list(cidades), safe=False)


@login_required
def resultados_busca(request, busca_id):
    busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)
    clientes = busca.clientes.all()

    context = {
        'busca': busca,
        'clientes': clientes,
    }
    return render(request, 'clientes/resultados.html', context)


@login_required
def historico_buscas(request):
    buscas = BuscaCliente.objects.filter(usuario=request.user)

    context = {
        'buscas': buscas,
    }
    return render(request, 'clientes/historico.html', context)


@login_required
def exportar_csv(request, busca_id):
    busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)
    clientes = busca.clientes.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="clientes_{busca_id}.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Nome', 'Telefone', 'WhatsApp', 'Email', 'Endereço',
        'Cidade', 'Estado', 'Website', 'Avaliação', 'Total Avaliações', 'Categoria'
    ])

    for cliente in clientes:
        writer.writerow([
            cliente.nome,
            cliente.telefone or '',
            cliente.whatsapp or '',
            cliente.email or '',
            cliente.endereco or '',
            cliente.cidade or '',
            cliente.estado or '',
            cliente.website or '',
            cliente.avaliacao or '',
            cliente.total_avaliacoes or '',
            cliente.categoria or '',
        ])

    return response


@login_required
def enriquecer_busca(request, busca_id):
    """
    View para iniciar o enriquecimento dos leads de uma busca.
    GET: mostra preview com opcoes
    POST: executa o enriquecimento
    """
    busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)

    if request.method == 'POST':
        validar_whatsapp = request.POST.get('validar_whatsapp') == 'on'

        pipeline = EnrichmentPipeline()
        stats = pipeline.enriquecer_busca(busca, validar_whatsapp=validar_whatsapp)

        messages.success(
            request,
            f"Enriquecimento concluido! {stats['enriquecidos']} leads processados. "
            f"{stats['quentes']} quentes | {stats['mornos']} mornos | {stats['frios']} frios"
        )
        return redirect('leads_qualificados', busca_id=busca.id)

    # GET -- mostra preview
    total_clientes = busca.clientes.count()
    total_com_telefone = busca.clientes.filter(whatsapp__isnull=False).exclude(whatsapp='').count()
    total_com_cnpj = busca.clientes.filter(cnpj__isnull=False).exclude(cnpj='').count()
    total_ja_enriquecidos = busca.clientes.filter(enriquecido=True).count()

    context = {
        'busca': busca,
        'total_clientes': total_clientes,
        'total_com_telefone': total_com_telefone,
        'total_com_cnpj': total_com_cnpj,
        'total_pendentes': total_clientes - total_ja_enriquecidos,
        'ja_enriquecida': busca.enriquecida,
    }
    return render(request, 'clientes/enriquecer.html', context)


@login_required
def leads_qualificados(request, busca_id):
    """View que mostra leads qualificados com filtros por classificacao."""
    busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)

    classificacao = request.GET.get('classificacao', 'todos')
    clientes = busca.clientes.filter(enriquecido=True)

    if classificacao != 'todos':
        clientes = clientes.filter(classificacao=classificacao)

    clientes = clientes.order_by('-lead_score')

    stats = {
        'total': busca.clientes.filter(enriquecido=True).count(),
        'quentes': busca.clientes.filter(classificacao='quente').count(),
        'mornos': busca.clientes.filter(classificacao='morno').count(),
        'frios': busca.clientes.filter(classificacao='frio').count(),
        'descartados': busca.clientes.filter(classificacao='descartado').count(),
    }

    context = {
        'busca': busca,
        'clientes': clientes,
        'classificacao_atual': classificacao,
        'stats': stats,
    }
    return render(request, 'clientes/leads_qualificados.html', context)


@login_required
def detalhe_lead(request, cliente_id):
    """View de detalhe de um lead com todos os dados de enriquecimento."""
    cliente = get_object_or_404(
        ClienteEncontrado,
        id=cliente_id,
        busca__usuario=request.user
    )
    context = {'cliente': cliente}
    return render(request, 'clientes/detalhe_lead.html', context)


@login_required
def exportar_qualificados_csv(request, busca_id):
    """Exporta leads qualificados (score >= 60) como CSV."""
    busca = get_object_or_404(BuscaCliente, id=busca_id, usuario=request.user)

    classificacao = request.GET.get('classificacao', 'todos')
    clientes = busca.clientes.filter(enriquecido=True)
    if classificacao != 'todos':
        clientes = clientes.filter(classificacao=classificacao)
    clientes = clientes.order_by('-lead_score')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leads_qualificados_{busca_id}.csv"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Nome', 'Score', 'Classificacao', 'Telefone', 'WhatsApp', 'WhatsApp Validado',
        'Email', 'CNPJ', 'Razao Social', 'Situacao', 'CNAE', 'Porte',
        'Endereco', 'Cidade', 'Estado', 'Website', 'Avaliacao',
    ])

    for c in clientes:
        writer.writerow([
            c.nome, c.lead_score, c.get_classificacao_display(),
            c.telefone or '', c.whatsapp or '',
            'Sim' if c.whatsapp_existe else ('Nao' if c.whatsapp_existe is False else '-'),
            c.email or '', c.cnpj or '', c.razao_social or '',
            c.situacao_cadastral or '', c.cnae_descricao or '', c.porte or '',
            c.endereco or '', c.cidade or '', c.estado or '',
            c.website or '', c.avaliacao or '',
        ])

    return response
