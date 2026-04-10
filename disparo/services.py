import requests
import random
import time
import re
from datetime import date, datetime, timedelta
from django.conf import settings
from django.utils import timezone


class EvolutionAPIService:
    """Serviço de integração com Evolution API para WhatsApp"""

    def __init__(self):
        self.base_url = getattr(settings, 'EVOLUTION_API_URL', 'http://localhost:8080')
        self.api_key = getattr(settings, 'EVOLUTION_API_KEY', 'change-me')
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': self.api_key
        }

    def criar_instancia(self, nome_instancia):
        """Cria uma nova instância no Evolution API (basico)"""
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": nome_instancia,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return {'success': True, 'data': response.json()}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def criar_instancia_completa(self, nome_instancia, webhook_url=None):
        """Cria instancia na Evolution com todas configuracoes automaticas:
        - QR Code habilitado
        - Webhook configurado
        - Rejeitar chamadas
        - Ignorar grupos
        - Sem sync de historico
        """
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": nome_instancia,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "groupsIgnore": True,
            "rejectCall": True,
            "msgCall": "Nao aceito chamadas, envie mensagem de texto.",
            "alwaysOnline": False,
            "readMessages": False,
            "syncFullHistory": False,
        }

        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "byEvents": False,
                "base64": True,
                "events": [
                    "QRCODE_UPDATED",
                    "CONNECTION_UPDATE",
                    "MESSAGES_UPSERT",
                ]
            }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            instance_id = data.get('hash', '') or data.get('instance', {}).get('instanceId', '')
            return {'success': True, 'data': data, 'instance_id': instance_id}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def obter_qrcode(self, nome_instancia):
        """Obtém o QR Code para conectar o WhatsApp"""
        url = f"{self.base_url}/instance/connect/{nome_instancia}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'data': data}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def verificar_conexao(self, nome_instancia):
        """Verifica o status da conexão da instância"""
        url = f"{self.base_url}/instance/connectionState/{nome_instancia}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'data': data}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def obter_info_instancia(self, nome_instancia):
        """Obtém informações completas da instância (incluindo número conectado)"""
        url = f"{self.base_url}/instance/fetchInstances?instanceName={nome_instancia}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'data': data}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def desconectar(self, nome_instancia):
        """Desconecta a instância do WhatsApp"""
        url = f"{self.base_url}/instance/logout/{nome_instancia}"

        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def deletar_instancia(self, nome_instancia):
        """Deleta a instância"""
        url = f"{self.base_url}/instance/delete/{nome_instancia}"

        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def verificar_numero_whatsapp(self, nome_instancia, numero):
        """Verifica se um número tem WhatsApp"""
        url = f"{self.base_url}/chat/whatsappNumbers/{nome_instancia}"
        payload = {
            "numbers": [self._formatar_numero(numero)]
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'data': data}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def enviar_mensagem_texto(self, nome_instancia, numero, mensagem):
        """Envia uma mensagem de texto"""
        url = f"{self.base_url}/message/sendText/{nome_instancia}"
        payload = {
            "number": self._formatar_numero(numero),
            "text": mensagem
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return {'success': True, 'data': data}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}

    def _formatar_numero(self, numero):
        """Formata o número para o padrão do WhatsApp (55XXXXXXXXXXX)"""
        # Remove tudo que não é número
        numero_limpo = re.sub(r'\D', '', numero)

        # Se não começar com 55, adiciona
        if not numero_limpo.startswith('55'):
            numero_limpo = '55' + numero_limpo

        return numero_limpo


class DisparoService:
    """Serviço de disparo de mensagens com proteções anti-bloqueio"""

    def __init__(self, usuario):
        self.usuario = usuario
        self.evolution = EvolutionAPIService()
        self._carregar_configuracoes()

    def _carregar_configuracoes(self):
        """Carrega as configurações de disparo do usuário"""
        from .models import ConfiguracaoDisparo
        config, created = ConfiguracaoDisparo.objects.get_or_create(
            usuario=self.usuario,
            defaults={
                'idade_numero': 'novo',
                'limite_diario': 50,
                'delay_minimo': 15,
                'delay_maximo': 60,
                'pausa_apos_mensagens': 20,
                'duracao_pausa': 300,
            }
        )
        self.config = config

    def pode_enviar_hoje(self):
        """Verifica se ainda pode enviar mensagens hoje"""
        from .models import EstatisticaDiaria
        hoje = date.today()

        estatistica, created = EstatisticaDiaria.objects.get_or_create(
            usuario=self.usuario,
            data=hoje,
            defaults={'mensagens_enviadas': 0}
        )

        return estatistica.mensagens_enviadas < self.config.limite_diario

    def mensagens_restantes_hoje(self):
        """Retorna quantas mensagens ainda podem ser enviadas hoje"""
        from .models import EstatisticaDiaria
        hoje = date.today()

        estatistica, created = EstatisticaDiaria.objects.get_or_create(
            usuario=self.usuario,
            data=hoje,
            defaults={'mensagens_enviadas': 0}
        )

        return max(0, self.config.limite_diario - estatistica.mensagens_enviadas)

    def esta_no_horario_permitido(self):
        """Verifica se está dentro do horário permitido para envio"""
        agora = timezone.localtime().time()
        return self.config.horario_inicio <= agora <= self.config.horario_fim

    def e_dia_util(self):
        """Verifica se hoje é dia útil"""
        return date.today().weekday() < 5  # 0-4 = Segunda a Sexta

    def numero_esta_bloqueado(self, numero):
        """Verifica se o número está na lista de bloqueados"""
        from .models import ContatoBloqueado
        numero_formatado = self._formatar_numero(numero)
        return ContatoBloqueado.objects.filter(
            usuario=self.usuario,
            numero=numero_formatado
        ).exists()

    def calcular_delay_aleatorio(self):
        """Calcula um delay aleatório entre mensagens"""
        return random.randint(self.config.delay_minimo, self.config.delay_maximo)

    def personalizar_mensagem(self, mensagem, nome_cliente, usar_nome=True):
        """Personaliza a mensagem com o nome do cliente"""
        if usar_nome and nome_cliente:
            # Pega apenas o primeiro nome
            primeiro_nome = nome_cliente.split()[0].title()
            # Substitui variáveis na mensagem
            mensagem = mensagem.replace('{nome}', primeiro_nome)
            mensagem = mensagem.replace('{NOME}', primeiro_nome.upper())
            # Se não tiver variável, adiciona no início
            if '{nome}' not in mensagem.lower() and not mensagem.startswith(primeiro_nome):
                mensagem = f"Olá {primeiro_nome}! {mensagem}"
        return mensagem

    def registrar_envio(self, sucesso=True):
        """Registra o envio nas estatísticas diárias"""
        from .models import EstatisticaDiaria
        hoje = date.today()

        estatistica, created = EstatisticaDiaria.objects.get_or_create(
            usuario=self.usuario,
            data=hoje,
            defaults={'mensagens_enviadas': 0}
        )

        if sucesso:
            estatistica.mensagens_enviadas += 1
            estatistica.mensagens_entregues += 1
        else:
            estatistica.mensagens_falha += 1

        estatistica.save()

    def _formatar_numero(self, numero):
        """Formata o número para o padrão do WhatsApp"""
        numero_limpo = re.sub(r'\D', '', numero)
        if not numero_limpo.startswith('55'):
            numero_limpo = '55' + numero_limpo
        return numero_limpo

    def validar_numero(self, numero):
        """Valida se o número tem formato válido"""
        numero_limpo = re.sub(r'\D', '', numero)
        # Número brasileiro: 10 ou 11 dígitos (com DDD)
        # Com código do país: 12 ou 13 dígitos
        return len(numero_limpo) >= 10 and len(numero_limpo) <= 13

    def executar_disparo(self, campanha, callback_progresso=None):
        """
        Executa o disparo de uma campanha com todas as proteções anti-bloqueio
        """
        from .models import LogEnvio, CampanhaDisparo

        # Verificações iniciais
        if self.config.enviar_apenas_dias_uteis and not self.e_dia_util():
            return {'success': False, 'error': 'Envio apenas em dias úteis'}

        if not self.esta_no_horario_permitido():
            return {'success': False, 'error': 'Fora do horário permitido'}

        # Buscar contatos pendentes
        logs_pendentes = LogEnvio.objects.filter(
            campanha=campanha,
            status='pendente'
        )

        enviados = 0
        falhas = 0
        mensagens_desde_pausa = 0

        for log in logs_pendentes:
            # Verificar limite diário
            if not self.pode_enviar_hoje():
                campanha.status = 'pausada'
                campanha.save()
                return {
                    'success': True,
                    'message': 'Limite diário atingido. Campanha pausada.',
                    'enviados': enviados,
                    'falhas': falhas
                }

            # Verificar horário
            if not self.esta_no_horario_permitido():
                campanha.status = 'pausada'
                campanha.save()
                return {
                    'success': True,
                    'message': 'Fora do horário permitido. Campanha pausada.',
                    'enviados': enviados,
                    'falhas': falhas
                }

            # Verificar se número está bloqueado
            if self.numero_esta_bloqueado(log.numero):
                log.status = 'bloqueado'
                log.save()
                continue

            # Pausa após X mensagens
            if mensagens_desde_pausa >= self.config.pausa_apos_mensagens:
                time.sleep(self.config.duracao_pausa)
                mensagens_desde_pausa = 0

            # Enviar mensagem
            log.status = 'enviando'
            log.tentativas += 1
            log.save()

            resultado = self.evolution.enviar_mensagem_texto(
                campanha.instancia.nome,
                log.numero,
                log.mensagem_enviada
            )

            if resultado['success']:
                log.status = 'enviado'
                log.data_envio = timezone.now()
                log.save()
                self.registrar_envio(sucesso=True)
                enviados += 1
                campanha.enviados += 1
            else:
                log.status = 'falha'
                log.erro = resultado.get('error', 'Erro desconhecido')
                log.save()
                self.registrar_envio(sucesso=False)
                falhas += 1
                campanha.falhas += 1

            campanha.save()
            mensagens_desde_pausa += 1

            # Callback de progresso
            if callback_progresso:
                callback_progresso(enviados, falhas, logs_pendentes.count())

            # Delay aleatório entre mensagens
            delay = self.calcular_delay_aleatorio()
            time.sleep(delay)

        # Verificar se campanha foi concluída
        pendentes_restantes = LogEnvio.objects.filter(
            campanha=campanha,
            status='pendente'
        ).count()

        if pendentes_restantes == 0:
            campanha.status = 'concluida'
            campanha.data_conclusao = timezone.now()
            campanha.save()

        return {
            'success': True,
            'message': 'Disparo finalizado',
            'enviados': enviados,
            'falhas': falhas
        }
