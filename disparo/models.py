from django.db import models
from django.contrib.auth.models import User
from clientes.models import BuscaCliente


class InstanciaWhatsApp(models.Model):
    """Instância de conexão com WhatsApp via Evolution API"""
    STATUS_CHOICES = [
        ('disconnected', 'Desconectado'),
        ('connecting', 'Conectando'),
        ('connected', 'Conectado'),
        ('qr_code', 'Aguardando QR Code'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='instancias_whatsapp')
    nome = models.CharField(max_length=100, verbose_name='Nome da Instância')
    instance_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    numero_conectado = models.CharField(max_length=20, blank=True, null=True, verbose_name='Número Conectado')
    data_criacao = models.DateTimeField(auto_now_add=True)
    ultima_conexao = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Instância WhatsApp'
        verbose_name_plural = 'Instâncias WhatsApp'

    def __str__(self):
        return f"{self.nome} - {self.get_status_display()}"


class ConfiguracaoDisparo(models.Model):
    """Configurações de segurança anti-bloqueio"""
    IDADE_NUMERO_CHOICES = [
        ('novo', 'Novo (até 2 meses) - 40-50 msg/dia'),
        ('recente', 'Recente (2-6 meses) - 100-200 msg/dia'),
        ('medio', 'Médio (6-12 meses) - 200-300 msg/dia'),
        ('antigo', 'Antigo (+2 anos) - 400-500 msg/dia'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='config_disparo')

    # Limites baseados na idade do número
    idade_numero = models.CharField(
        max_length=20,
        choices=IDADE_NUMERO_CHOICES,
        default='novo',
        verbose_name='Idade do Número'
    )
    limite_diario = models.IntegerField(default=50, verbose_name='Limite Diário de Mensagens')

    # Intervalos entre mensagens (anti-ban)
    delay_minimo = models.IntegerField(default=15, verbose_name='Delay Mínimo (segundos)')
    delay_maximo = models.IntegerField(default=60, verbose_name='Delay Máximo (segundos)')

    # Pausas longas para simular comportamento humano
    pausa_apos_mensagens = models.IntegerField(default=20, verbose_name='Pausar após X mensagens')
    duracao_pausa = models.IntegerField(default=300, verbose_name='Duração da pausa (segundos)')

    # Horário de envio
    horario_inicio = models.TimeField(default='08:00', verbose_name='Horário de Início')
    horario_fim = models.TimeField(default='20:00', verbose_name='Horário de Fim')

    # Outras configurações
    enviar_apenas_dias_uteis = models.BooleanField(default=False)
    max_tentativas_por_contato = models.IntegerField(default=3, verbose_name='Máx. tentativas por contato')

    class Meta:
        verbose_name = 'Configuração de Disparo'
        verbose_name_plural = 'Configurações de Disparo'

    def __str__(self):
        return f"Config. de {self.usuario.username}"

    def get_limite_por_idade(self):
        """Retorna o limite recomendado baseado na idade do número"""
        limites = {
            'novo': 50,
            'recente': 150,
            'medio': 250,
            'antigo': 450,
        }
        return limites.get(self.idade_numero, 50)


class CampanhaDisparo(models.Model):
    """Campanha de disparo de mensagens"""
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('agendada', 'Agendada'),
        ('em_andamento', 'Em Andamento'),
        ('pausada', 'Pausada'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campanhas')
    instancia = models.ForeignKey(InstanciaWhatsApp, on_delete=models.CASCADE, related_name='campanhas')
    busca = models.ForeignKey(BuscaCliente, on_delete=models.CASCADE, related_name='campanhas', verbose_name='Lista de Clientes')

    nome = models.CharField(max_length=200, verbose_name='Nome da Campanha')
    mensagem = models.TextField(verbose_name='Mensagem')

    # Personalização
    usar_nome_cliente = models.BooleanField(default=True, verbose_name='Chamar cliente pelo nome')

    # Estatísticas
    total_contatos = models.IntegerField(default=0)
    enviados = models.IntegerField(default=0)
    entregues = models.IntegerField(default=0)
    lidos = models.IntegerField(default=0)
    respondidos = models.IntegerField(default=0)
    falhas = models.IntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_inicio = models.DateTimeField(blank=True, null=True)
    data_conclusao = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = 'Campanha de Disparo'
        verbose_name_plural = 'Campanhas de Disparo'

    def __str__(self):
        return f"{self.nome} - {self.get_status_display()}"

    @property
    def taxa_entrega(self):
        if self.enviados == 0:
            return 0
        return round((self.entregues / self.enviados) * 100, 1)

    @property
    def taxa_leitura(self):
        if self.entregues == 0:
            return 0
        return round((self.lidos / self.entregues) * 100, 1)

    @property
    def taxa_resposta(self):
        if self.entregues == 0:
            return 0
        return round((self.respondidos / self.entregues) * 100, 1)


class LogEnvio(models.Model):
    """Log detalhado de cada envio"""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('entregue', 'Entregue'),
        ('lido', 'Lido'),
        ('respondido', 'Respondido'),
        ('falha', 'Falha'),
        ('bloqueado', 'Número Bloqueado'),
        ('invalido', 'Número Inválido'),
    ]

    campanha = models.ForeignKey(CampanhaDisparo, on_delete=models.CASCADE, related_name='logs')

    # Dados do contato
    nome_contato = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)

    # Mensagem enviada (pode ser personalizada)
    mensagem_enviada = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    erro = models.TextField(blank=True, null=True)

    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(blank=True, null=True)
    data_entrega = models.DateTimeField(blank=True, null=True)
    data_leitura = models.DateTimeField(blank=True, null=True)
    data_resposta = models.DateTimeField(blank=True, null=True)

    # Tentativas
    tentativas = models.IntegerField(default=0)

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = 'Log de Envio'
        verbose_name_plural = 'Logs de Envio'

    def __str__(self):
        return f"{self.nome_contato} - {self.get_status_display()}"


class ContatoBloqueado(models.Model):
    """Contatos que pediram para sair ou foram bloqueados"""
    MOTIVO_CHOICES = [
        ('opt_out', 'Pediu para sair'),
        ('bloqueou', 'Bloqueou o número'),
        ('invalido', 'Número inválido'),
        ('sem_whatsapp', 'Não tem WhatsApp'),
        ('manual', 'Removido manualmente'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contatos_bloqueados')
    numero = models.CharField(max_length=20)
    motivo = models.CharField(max_length=20, choices=MOTIVO_CHOICES)
    data_bloqueio = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['usuario', 'numero']
        verbose_name = 'Contato Bloqueado'
        verbose_name_plural = 'Contatos Bloqueados'

    def __str__(self):
        return f"{self.numero} - {self.get_motivo_display()}"


class EstatisticaDiaria(models.Model):
    """Controle de mensagens enviadas por dia (para respeitar limites)"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='estatisticas_diarias')
    data = models.DateField()
    mensagens_enviadas = models.IntegerField(default=0)
    mensagens_entregues = models.IntegerField(default=0)
    mensagens_falha = models.IntegerField(default=0)

    class Meta:
        unique_together = ['usuario', 'data']
        verbose_name = 'Estatística Diária'
        verbose_name_plural = 'Estatísticas Diárias'

    def __str__(self):
        return f"{self.data} - {self.mensagens_enviadas} enviadas"
