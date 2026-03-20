import requests
import random
import time
import json
from datetime import date, datetime, timedelta
from django.conf import settings
from django.utils import timezone

from disparo.services import EvolutionAPIService


class OpenRouterService:
    """Servico para gerar mensagens naturais usando LLM gratuita via OpenRouter"""

    def __init__(self):
        self.api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.model = getattr(settings, 'OPENROUTER_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')

    def _chamar_llm(self, messages, temperature=0.9, max_tokens=150):
        """Chama a LLM via OpenRouter"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens,
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"[OpenRouter ERROR] {e}")
            return None

    def gerar_tema_conversa(self):
        """Gera um tema aleatorio e natural para uma conversa"""
        messages = [
            {
                'role': 'system',
                'content': (
                    'Voce gera temas curtos para conversas casuais de WhatsApp entre amigos brasileiros. '
                    'Responda APENAS com o tema, nada mais. Maximo 5 palavras. '
                    'Exemplos: "churrasco no sabado", "jogo do Brasil ontem", "indicacao de serie", '
                    '"problema no trabalho", "viagem de ferias"'
                )
            },
            {'role': 'user', 'content': 'Gere um tema de conversa casual entre amigos.'}
        ]
        tema = self._chamar_llm(messages, temperature=1.0, max_tokens=20)
        return tema or random.choice([
            'churrasco no fim de semana',
            'jogo de ontem',
            'serie nova na netflix',
            'trabalho ta puxado',
            'viagem planejada',
            'comida nova que experimentei',
            'musica boa que descobri',
            'treino na academia',
        ])

    def gerar_mensagem_conversa(self, persona_remetente, persona_destinatario, tema, historico_msgs, tipo='privado'):
        """Gera a proxima mensagem natural de uma conversa"""
        contexto_tipo = 'conversa privada no WhatsApp' if tipo == 'privado' else 'grupo de WhatsApp entre amigos'

        # Montar historico formatado
        historico_fmt = ''
        for msg in historico_msgs[-10:]:  # Ultimas 10 msgs
            historico_fmt += f"{msg['nome']}: {msg['texto']}\n"

        system_prompt = (
            f'Voce esta simulando uma {contexto_tipo} entre brasileiros. '
            f'Voce esta escrevendo como "{persona_remetente["nome"]}" ({persona_remetente.get("descricao", "pessoa normal")}). '
            f'O tema geral e: "{tema}".\n\n'
            'REGRAS IMPORTANTES:\n'
            '- Escreva APENAS a mensagem, sem prefixo com nome\n'
            '- Escreva como brasileiro real no WhatsApp: informal, com girias, abreviacoes\n'
            '- Use "vc", "tb", "pq", "kk", "rs", "haha" quando natural\n'
            '- Mensagens CURTAS (1-2 frases no maximo)\n'
            '- Pode usar emoji mas com moderacao (0-2 por msg)\n'
            '- Varie: perguntas, respostas, opinioes, piadas\n'
            '- Pode mudar levemente de assunto como conversa real\n'
            '- NUNCA seja formal ou robotico\n'
            '- Pode cometer erros de digitacao leves de vez em quando\n'
        )

        messages = [{'role': 'system', 'content': system_prompt}]

        if historico_fmt:
            messages.append({
                'role': 'user',
                'content': f'Historico da conversa:\n{historico_fmt}\nAgora escreva a proxima mensagem como {persona_remetente["nome"]}:'
            })
        else:
            messages.append({
                'role': 'user',
                'content': f'Comece uma conversa sobre "{tema}" de forma natural. Escreva a primeira mensagem como {persona_remetente["nome"]}:'
            })

        resposta = self._chamar_llm(messages, temperature=0.95, max_tokens=100)

        if not resposta:
            # Fallback com mensagens pre-definidas
            return self._mensagem_fallback(tema, len(historico_msgs) == 0)

        # Limpar resposta (remover prefixos tipo "Nome: ")
        if ':' in resposta[:30]:
            resposta = resposta.split(':', 1)[1].strip()
        # Remover aspas envolventes
        resposta = resposta.strip('"').strip("'")

        return resposta

    def gerar_mensagem_grupo(self, persona_remetente, participantes, tema, historico_msgs):
        """Gera mensagem para grupo - pode mencionar outros participantes"""
        return self.gerar_mensagem_conversa(
            persona_remetente,
            {'nome': 'grupo', 'descricao': 'grupo de amigos'},
            tema,
            historico_msgs,
            tipo='grupo'
        )

    def _mensagem_fallback(self, tema, is_primeira):
        """Mensagens fallback caso a LLM falhe"""
        primeiras = [
            f'E ai galera, alguem viu sobre {tema}?',
            f'Cara, preciso falar sobre {tema} kk',
            f'Gente, voces nao vao acreditar... {tema}',
            f'Opa, tudo bem? To pensando sobre {tema}',
            f'Bom dia! Alguem ai afim de conversar sobre {tema}?',
        ]
        respostas = [
            'Pois e, eu tb tava pensando nisso',
            'Kkkk serio?? conta mais',
            'Eu vi sim, achei muito bom',
            'Nao acredito kkk',
            'Eita, sério isso?',
            'Haha sim mano, demais',
            'Ah mano, faz sentido',
            'Tbm acho, concordo total',
            'Puts, nem sabia disso',
            'Boa! Vamos combinar entao',
        ]
        return random.choice(primeiras) if is_primeira else random.choice(respostas)


class AquecimentoService:
    """Servico principal de aquecimento de chips"""

    def __init__(self, plano):
        self.plano = plano
        self.evolution = EvolutionAPIService()
        self.llm = OpenRouterService()

    def criar_grupo_aquecimento(self):
        """Cria um grupo no WhatsApp entre todos os chips do plano"""
        from .models import GrupoAquecimento

        chips_conectados = self.plano.chips.filter(status__in=['conectado', 'aquecendo'])
        if chips_conectados.count() < 2:
            return {'success': False, 'error': 'Precisa de pelo menos 2 chips conectados'}

        # Usar o primeiro chip para criar o grupo
        chip_criador = chips_conectados.first()
        numeros_participantes = [
            f'{c.numero}@s.whatsapp.net'
            for c in chips_conectados
            if c.id != chip_criador.id and c.numero
        ]

        nome_grupo = f"Amigos {random.choice(['do Fut', 'da Firma', 'do Churras', 'do Role', 'da Facul', 'do Bairro'])}"

        url = f"{self.evolution.base_url}/group/create/{chip_criador.instancia.nome}"
        payload = {
            'subject': nome_grupo,
            'participants': numeros_participantes,
        }

        try:
            response = requests.post(url, json=payload, headers=self.evolution.headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            group_jid = data.get('id') or data.get('gid') or data.get('groupId', '')

            grupo = GrupoAquecimento.objects.create(
                plano=self.plano,
                nome_grupo=nome_grupo,
                group_jid=group_jid,
                instancia_criadora=chip_criador.instancia,
            )

            return {'success': True, 'grupo': grupo}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def iniciar_conversa_privada(self, chip1, chip2):
        """Inicia uma conversa privada entre dois chips"""
        from .models import ConversaAquecimento

        tema = self.llm.gerar_tema_conversa()
        max_msgs = random.randint(4, 15)

        conversa = ConversaAquecimento.objects.create(
            plano=self.plano,
            tipo='privado',
            tema=tema,
            max_mensagens=max_msgs,
        )
        conversa.participantes.add(chip1, chip2)

        return conversa

    def iniciar_conversa_grupo(self, grupo):
        """Inicia uma conversa no grupo"""
        from .models import ConversaAquecimento

        tema = self.llm.gerar_tema_conversa()
        max_msgs = random.randint(8, 25)

        conversa = ConversaAquecimento.objects.create(
            plano=self.plano,
            tipo='grupo',
            grupo=grupo,
            tema=tema,
            max_mensagens=max_msgs,
        )

        chips = self.plano.chips.filter(status__in=['conectado', 'aquecendo'])
        conversa.participantes.set(chips)

        return conversa

    def enviar_proxima_mensagem(self, conversa):
        """Gera e envia a proxima mensagem de uma conversa"""
        from .models import MensagemAquecimento, LogDiarioAquecimento

        if not conversa.ativa:
            return None

        if conversa.total_mensagens >= conversa.max_mensagens:
            conversa.ativa = False
            conversa.save()
            return None

        participantes = list(conversa.participantes.filter(status__in=['conectado', 'aquecendo']))
        if len(participantes) < 2:
            return None

        # Decidir quem fala agora (alternar, com aleatoriedade)
        ultima_msg = conversa.mensagens.last()
        if ultima_msg:
            # Nao repetir o mesmo remetente (80% das vezes)
            outros = [p for p in participantes if p.id != ultima_msg.remetente_id]
            if outros and random.random() < 0.8:
                remetente = random.choice(outros)
            else:
                remetente = random.choice(participantes)
        else:
            remetente = random.choice(participantes)

        # Verificar limite diario do chip
        hoje = date.today()
        log_diario, _ = LogDiarioAquecimento.objects.get_or_create(
            chip=remetente,
            data=hoje,
            defaults={'meta_dia': self.plano.calcular_msgs_para_dia()}
        )

        if log_diario.msgs_enviadas >= log_diario.meta_dia:
            return None

        # Montar historico
        historico = []
        for msg in conversa.mensagens.order_by('-data_criacao')[:10]:
            historico.insert(0, {
                'nome': msg.remetente.apelido or f'Chip{msg.remetente.id}',
                'texto': msg.texto,
            })

        # Escolher destinatario para privado
        destinatario = None
        if conversa.tipo == 'privado':
            destinatario = [p for p in participantes if p.id != remetente.id][0]

        # Gerar mensagem com IA
        persona_rem = {
            'nome': remetente.apelido or f'Chip{remetente.id}',
            'descricao': remetente.persona or 'pessoa normal, informal'
        }

        if conversa.tipo == 'grupo':
            texto = self.llm.gerar_mensagem_grupo(
                persona_rem, participantes, conversa.tema, historico
            )
        else:
            persona_dest = {
                'nome': destinatario.apelido or f'Chip{destinatario.id}',
                'descricao': destinatario.persona or 'pessoa normal, informal'
            }
            texto = self.llm.gerar_mensagem_conversa(
                persona_rem, persona_dest, conversa.tema, historico
            )

        # Criar registro da mensagem
        mensagem = MensagemAquecimento.objects.create(
            conversa=conversa,
            remetente=remetente,
            destinatario=destinatario,
            texto=texto,
        )

        # Enviar via Evolution API
        sucesso = self._enviar_mensagem_evolution(remetente, destinatario, conversa, texto)

        if sucesso:
            mensagem.enviada = True
            mensagem.data_envio = timezone.now()
            mensagem.save()

            # Atualizar contadores
            remetente.msgs_enviadas_total += 1
            remetente.msgs_enviadas_hoje += 1
            remetente.ultimo_envio = timezone.now()
            remetente.erros_consecutivos = 0
            remetente.save()

            log_diario.msgs_enviadas += 1
            log_diario.save()

            conversa.total_mensagens += 1
            conversa.data_ultima_msg = timezone.now()
            conversa.save()
        else:
            mensagem.erro = 'Falha ao enviar'
            mensagem.save()

            remetente.erros_consecutivos += 1
            remetente.save()

            log_diario.erros += 1
            log_diario.save()

            # Se muitos erros, pausar o chip (possivel ban)
            if remetente.erros_consecutivos >= 3:
                remetente.status = 'pausado'
                remetente.save()

        return mensagem

    def _enviar_mensagem_evolution(self, remetente, destinatario, conversa, texto):
        """Envia mensagem via Evolution API"""
        instancia_nome = remetente.instancia.nome

        if conversa.tipo == 'grupo' and conversa.grupo and conversa.grupo.group_jid:
            # Enviar no grupo
            url = f"{self.evolution.base_url}/message/sendText/{instancia_nome}"
            payload = {
                'number': conversa.grupo.group_jid,
                'text': texto,
            }
        else:
            # Enviar privado
            if not destinatario or not destinatario.numero:
                return False
            numero = self.evolution._formatar_numero(destinatario.numero)
            url = f"{self.evolution.base_url}/message/sendText/{instancia_nome}"
            payload = {
                'number': numero,
                'text': texto,
            }

        try:
            response = requests.post(url, json=payload, headers=self.evolution.headers, timeout=30)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[Aquecimento ERRO] Envio falhou: {e}")
            return False

    def executar_ciclo(self):
        """
        Executa um ciclo de aquecimento.
        Deve ser chamado periodicamente (ex: a cada 1-5 minutos).
        Gerencia conversas ativas, cria novas, e respeita limites.
        """
        from .models import ConversaAquecimento, LogDiarioAquecimento

        if self.plano.status != 'ativo':
            return {'status': 'inativo'}

        # Verificar horario
        agora = timezone.localtime()
        hora_atual = agora.time()
        if not (self.plano.horario_inicio <= hora_atual <= self.plano.horario_fim):
            return {'status': 'fora_horario'}

        chips_ativos = list(self.plano.chips.filter(status__in=['conectado', 'aquecendo']))
        if len(chips_ativos) < 2:
            return {'status': 'chips_insuficientes'}

        # Atualizar dia do aquecimento
        if self.plano.data_inicio:
            dias_passados = (agora.date() - self.plano.data_inicio.date()).days + 1
            if dias_passados != self.plano.dia_atual:
                self.plano.dia_atual = dias_passados
                self.plano.save()
                # Resetar contadores diarios dos chips
                for chip in chips_ativos:
                    chip.msgs_enviadas_hoje = 0
                    chip.save()

        meta_dia = self.plano.calcular_msgs_para_dia()
        hoje = date.today()

        # Verificar se todos os chips ja bateram a meta
        todos_bateram_meta = True
        for chip in chips_ativos:
            log, _ = LogDiarioAquecimento.objects.get_or_create(
                chip=chip, data=hoje,
                defaults={'meta_dia': meta_dia}
            )
            if log.msgs_enviadas < log.meta_dia:
                todos_bateram_meta = False
                break

        if todos_bateram_meta:
            return {'status': 'meta_atingida', 'meta': meta_dia}

        # Buscar conversas ativas ou criar novas
        conversas_ativas = ConversaAquecimento.objects.filter(
            plano=self.plano, ativa=True
        )

        if not conversas_ativas.exists():
            # Criar novas conversas
            if self.plano.habilitar_privado and len(chips_ativos) >= 2:
                # Sortear dupla para conversa privada
                dupla = random.sample(chips_ativos, 2)
                self.iniciar_conversa_privada(dupla[0], dupla[1])

            if self.plano.habilitar_grupo:
                grupos = self.plano.grupos.filter(ativo=True)
                if grupos.exists():
                    self.iniciar_conversa_grupo(grupos.first())

        # Enviar mensagem na conversa ativa
        conversas = ConversaAquecimento.objects.filter(plano=self.plano, ativa=True)
        mensagem_enviada = None
        for conversa in conversas:
            mensagem_enviada = self.enviar_proxima_mensagem(conversa)
            if mensagem_enviada:
                break

        return {
            'status': 'mensagem_enviada' if mensagem_enviada else 'aguardando',
            'meta_dia': meta_dia,
            'dia': self.plano.dia_atual,
        }

    def verificar_status_chips(self):
        """Verifica status de conexao de todos os chips"""
        resultados = []
        for chip in self.plano.chips.all():
            result = self.evolution.verificar_conexao(chip.instancia.nome)
            if result['success']:
                data = result['data']
                state = data.get('instance', {}).get('state') or data.get('state')
                if state == 'open':
                    if chip.status == 'aguardando':
                        chip.status = 'conectado'
                    chip.instancia.status = 'connected'
                elif state == 'close':
                    chip.status = 'pausado'
                    chip.instancia.status = 'disconnected'
                chip.instancia.save()
                chip.save()
                resultados.append({'chip': chip.apelido, 'status': state})
            else:
                resultados.append({'chip': chip.apelido, 'status': 'erro'})

        return resultados
