"""
Pipeline de enriquecimento e qualificacao de leads.
Etapas: CNPJ lookup -> Validacao WhatsApp -> Presenca digital -> Scoring
"""
import re
import time
import logging
import requests
from datetime import date
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================================
# ETAPA 1 -- Consulta CNPJ via BrasilAPI
# ============================================================

class CNPJService:
    """
    Consulta dados de CNPJ via BrasilAPI.
    API publica, gratuita. Rate limit: ~3 req/s (ser conservador).
    """
    BASE_URL = "https://brasilapi.com.br/api/cnpj/v1"

    def consultar(self, cnpj: str) -> dict | None:
        cnpj_limpo = re.sub(r'\D', '', cnpj)
        if len(cnpj_limpo) != 14:
            return None

        try:
            response = requests.get(
                f"{self.BASE_URL}/{cnpj_limpo}",
                timeout=10,
                headers={"User-Agent": "BuscaClientes/1.0"}
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.info(f"CNPJ {cnpj_limpo} nao encontrado na base")
                return None
            elif response.status_code == 429:
                logger.warning("Rate limit BrasilAPI atingido, aguardando...")
                time.sleep(2)
                return self.consultar(cnpj)
            else:
                logger.error(f"Erro BrasilAPI: {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.error(f"Erro de conexao BrasilAPI: {e}")
            return None

    def buscar_por_nome_cidade(self, nome: str, cidade: str = "", estado: str = "") -> dict | None:
        """
        Placeholder -- BrasilAPI nao tem endpoint de busca por nome.
        Em producao, integrar com base local de CNPJ ou CNPJa API.
        """
        return None


# ============================================================
# ETAPA 2 -- Validacao de WhatsApp via Evolution API
# ============================================================

class WhatsAppValidationService:
    """Valida se um numero tem WhatsApp usando a Evolution API."""

    def __init__(self):
        self.base_url = getattr(settings, 'EVOLUTION_API_URL', 'http://localhost:8080')
        self.api_key = getattr(settings, 'EVOLUTION_API_KEY', '')

    def _get_instancia_ativa(self) -> str | None:
        from disparo.models import InstanciaWhatsApp
        instancia = InstanciaWhatsApp.objects.filter(status='connected').first()
        return instancia.instance_id if instancia else None

    def validar_numero(self, telefone: str) -> bool | None:
        """
        Verifica se o numero tem WhatsApp.
        Retorna True/False ou None se nao foi possivel verificar.
        """
        instancia = self._get_instancia_ativa()
        if not instancia:
            logger.warning("Nenhuma instancia WhatsApp conectada para validacao")
            return None

        numero = re.sub(r'\D', '', telefone)
        if not numero.startswith('55'):
            numero = f'55{numero}'

        try:
            response = requests.post(
                f"{self.base_url}/chat/whatsappNumbers/{instancia}",
                json={"numbers": [numero]},
                headers={
                    "apikey": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return data[0].get('exists', False)
            return None
        except requests.RequestException as e:
            logger.error(f"Erro validacao WhatsApp: {e}")
            return None

    def validar_lote(self, telefones: list[str], delay: float = 1.0) -> dict:
        resultados = {}
        for tel in telefones:
            resultados[tel] = self.validar_numero(tel)
            time.sleep(delay)
        return resultados


# ============================================================
# ETAPA 3 -- Verificacao de Presenca Digital
# ============================================================

class PresencaDigitalService:
    """Verifica presenca online da empresa (website, redes sociais)."""

    def verificar_website(self, url: str) -> bool:
        if not url:
            return False
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code < 400
        except requests.RequestException:
            return False

    def verificar(self, cliente) -> dict:
        resultado = {
            'tem_website': False,
            'tem_redes_sociais': False,
        }

        if cliente.website:
            resultado['tem_website'] = self.verificar_website(cliente.website)

        if cliente.email:
            dominio = cliente.email.split('@')[-1] if '@' in cliente.email else ''
            genericos = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'uol.com.br', 'bol.com.br']
            if dominio and dominio not in genericos:
                resultado['tem_redes_sociais'] = True

        return resultado


# ============================================================
# ETAPA 4 -- Lead Scoring
# ============================================================

class LeadScoringService:
    """
    Calcula score do lead baseado em criterios objetivos.
    Score de 0 a 100: quente (>=80), morno (>=60), frio (>=40), descartado (<40).
    """

    CRITERIOS = {
        'cnpj_ativo': {'pontos': 30, 'descricao': 'CNPJ ativo e regular na Receita Federal'},
        'whatsapp_ativo': {'pontos': 25, 'descricao': 'WhatsApp comercial verificado'},
        'presenca_digital': {'pontos': 20, 'descricao': 'Website ou redes sociais ativas'},
        'porte_compativel': {'pontos': 15, 'descricao': 'Porte empresarial compativel (ME/EPP)'},
        'avaliacao_google': {'pontos': 10, 'descricao': 'Avaliacao no Google Maps acima de 4.0'},
    }

    def calcular(self, cliente) -> tuple[int, dict, str]:
        detalhes = {}
        score = 0

        # 1. CNPJ ativo e regular (+30)
        if cliente.cnpj and cliente.situacao_cadastral:
            situacao = cliente.situacao_cadastral.upper()
            if situacao in ['ATIVA', '02']:
                detalhes['cnpj_ativo'] = self.CRITERIOS['cnpj_ativo']['pontos']
                score += detalhes['cnpj_ativo']

        # 2. WhatsApp verificado (+25)
        if cliente.whatsapp_existe is True:
            detalhes['whatsapp_ativo'] = self.CRITERIOS['whatsapp_ativo']['pontos']
            score += detalhes['whatsapp_ativo']

        # 3. Presenca digital (+20)
        if cliente.tem_website or cliente.tem_redes_sociais:
            pontos_presenca = 0
            if cliente.tem_website:
                pontos_presenca += 12
            if cliente.tem_redes_sociais:
                pontos_presenca += 8
            detalhes['presenca_digital'] = min(pontos_presenca, self.CRITERIOS['presenca_digital']['pontos'])
            score += detalhes['presenca_digital']

        # 4. Porte compativel (+15)
        if cliente.porte:
            porte_upper = cliente.porte.upper()
            if 'MICRO' in porte_upper or porte_upper == 'ME':
                detalhes['porte_compativel'] = 15
            elif 'PEQUENO' in porte_upper or porte_upper == 'EPP':
                detalhes['porte_compativel'] = 15
            elif 'MEDIO' in porte_upper:
                detalhes['porte_compativel'] = 10
            else:
                detalhes['porte_compativel'] = 5
            score += detalhes['porte_compativel']

        # 5. Avaliacao Google Maps (+10)
        if cliente.avaliacao and cliente.avaliacao >= Decimal('4.0'):
            detalhes['avaliacao_google'] = self.CRITERIOS['avaliacao_google']['pontos']
            score += detalhes['avaliacao_google']
        elif cliente.avaliacao and cliente.avaliacao >= Decimal('3.0'):
            detalhes['avaliacao_google'] = 5
            score += 5

        # Classificacao
        if score >= 80:
            classificacao = 'quente'
        elif score >= 60:
            classificacao = 'morno'
        elif score >= 40:
            classificacao = 'frio'
        else:
            classificacao = 'descartado'

        return score, detalhes, classificacao


# ============================================================
# ORQUESTRADOR -- Pipeline completo
# ============================================================

class EnrichmentPipeline:
    """Orquestra o pipeline completo de enriquecimento."""

    def __init__(self):
        self.cnpj_service = CNPJService()
        self.whatsapp_service = WhatsAppValidationService()
        self.presenca_service = PresencaDigitalService()
        self.scoring_service = LeadScoringService()

    def enriquecer_cliente(self, cliente, validar_whatsapp=True) -> None:
        # Etapa 1: Consulta CNPJ (se tiver)
        if cliente.cnpj and not cliente.razao_social:
            dados_cnpj = self.cnpj_service.consultar(cliente.cnpj)
            if dados_cnpj:
                self._aplicar_dados_cnpj(cliente, dados_cnpj)

        # Etapa 2: Validar WhatsApp
        if validar_whatsapp and cliente.whatsapp and not cliente.whatsapp_validado:
            resultado = self.whatsapp_service.validar_numero(cliente.whatsapp)
            if resultado is not None:
                cliente.whatsapp_existe = resultado
                cliente.whatsapp_validado = True

        # Etapa 3: Presenca digital
        presenca = self.presenca_service.verificar(cliente)
        cliente.tem_website = presenca['tem_website']
        cliente.tem_redes_sociais = presenca['tem_redes_sociais']

        # Etapa 4: Scoring
        score, detalhes, classificacao = self.scoring_service.calcular(cliente)
        cliente.lead_score = score
        cliente.score_detalhes = detalhes
        cliente.classificacao = classificacao

        # Marcar como enriquecido
        cliente.enriquecido = True
        cliente.data_enriquecimento = timezone.now()
        cliente.save()

    def enriquecer_busca(self, busca, validar_whatsapp=True, callback=None) -> dict:
        """
        Enriquece todos os clientes de uma busca.
        Retorna estatisticas do enriquecimento.
        """
        clientes = busca.clientes.filter(enriquecido=False)
        total = clientes.count()
        stats = {'total': total, 'enriquecidos': 0, 'erros': 0, 'quentes': 0, 'mornos': 0, 'frios': 0}

        for i, cliente in enumerate(clientes):
            try:
                self.enriquecer_cliente(cliente, validar_whatsapp=validar_whatsapp)
                stats['enriquecidos'] += 1

                if cliente.classificacao == 'quente':
                    stats['quentes'] += 1
                elif cliente.classificacao == 'morno':
                    stats['mornos'] += 1
                elif cliente.classificacao == 'frio':
                    stats['frios'] += 1

                if callback:
                    callback(i + 1, total, cliente)

            except Exception as e:
                logger.error(f"Erro enriquecendo cliente {cliente.id}: {e}")
                cliente.erro_enriquecimento = str(e)
                cliente.save()
                stats['erros'] += 1

            # Delay entre clientes para respeitar rate limits
            time.sleep(0.5)

        # Atualizar busca
        busca.enriquecida = True
        busca.data_enriquecimento = timezone.now()
        busca.total_qualificados = busca.clientes.filter(lead_score__gte=60).count()
        busca.save()

        return stats

    def _aplicar_dados_cnpj(self, cliente, dados: dict) -> None:
        cliente.razao_social = dados.get('razao_social', '')
        cliente.nome_fantasia = dados.get('nome_fantasia', '')
        cliente.situacao_cadastral = dados.get('descricao_situacao_cadastral', '')
        cliente.porte = dados.get('porte', '')
        cliente.natureza_juridica = dados.get('descricao_natureza_juridica', '')

        cnae = dados.get('cnae_fiscal')
        if cnae:
            cliente.cnae_principal = str(cnae)
            cliente.cnae_descricao = dados.get('cnae_fiscal_descricao', '')

        capital = dados.get('capital_social')
        if capital:
            try:
                cliente.capital_social = Decimal(str(capital))
            except (ValueError, TypeError):
                pass

        data_inicio = dados.get('data_inicio_atividade')
        if data_inicio:
            try:
                cliente.data_abertura = date.fromisoformat(data_inicio)
            except (ValueError, TypeError):
                pass
