from django.db import models
from django.contrib.auth.models import User
from disparo.models import InstanciaWhatsApp


class PlanoAquecimento(models.Model):
    """Plano de aquecimento para um conjunto de chips"""
    STATUS_CHOICES = [
        ('configurando', 'Configurando'),
        ('ativo', 'Ativo'),
        ('pausado', 'Pausado'),
        ('concluido', 'Concluido'),
        ('cancelado', 'Cancelado'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='planos_aquecimento')
    nome = models.CharField(max_length=200, verbose_name='Nome do Plano')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='configurando')

    # Configuracoes de volume gradual
    msgs_dia_inicio = models.IntegerField(default=3, verbose_name='Msgs/dia no inicio')
    msgs_dia_meta = models.IntegerField(default=200, verbose_name='Meta msgs/dia ao final')
    dias_aquecimento = models.IntegerField(default=21, verbose_name='Dias de aquecimento')

    # Horarios permitidos (simular uso humano)
    horario_inicio = models.TimeField(default='08:00')
    horario_fim = models.TimeField(default='21:00')

    # Configuracoes de conversa
    habilitar_grupo = models.BooleanField(default=True, verbose_name='Criar grupo entre os chips')
    habilitar_privado = models.BooleanField(default=True, verbose_name='Conversas privadas entre chips')

    # Delays entre mensagens (mais conservador que disparo)
    delay_minimo = models.IntegerField(default=60, verbose_name='Delay minimo entre msgs (seg)')
    delay_maximo = models.IntegerField(default=300, verbose_name='Delay maximo entre msgs (seg)')

    # Pausa longa para simular que a pessoa saiu do celular
    pausa_min_minutos = models.IntegerField(default=15, verbose_name='Pausa minima (min)')
    pausa_max_minutos = models.IntegerField(default=60, verbose_name='Pausa maxima (min)')
    msgs_antes_pausa = models.IntegerField(default=8, verbose_name='Msgs antes de uma pausa longa')

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_inicio = models.DateTimeField(blank=True, null=True)
    dia_atual = models.IntegerField(default=0, verbose_name='Dia atual do aquecimento')

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = 'Plano de Aquecimento'
        verbose_name_plural = 'Planos de Aquecimento'

    def __str__(self):
        return f"{self.nome} - Dia {self.dia_atual}/{self.dias_aquecimento}"

    def calcular_msgs_para_dia(self, dia=None):
        """Calcula quantas msgs cada chip deve enviar no dia X (crescimento gradual)"""
        if dia is None:
            dia = self.dia_atual
        if dia <= 0:
            dia = 1
        if dia >= self.dias_aquecimento:
            return self.msgs_dia_meta

        import math
        ratio = dia / self.dias_aquecimento
        msgs = self.msgs_dia_inicio + (self.msgs_dia_meta - self.msgs_dia_inicio) * (
            (math.exp(3 * ratio) - 1) / (math.exp(3) - 1)
        )
        return max(self.msgs_dia_inicio, int(msgs))


class ChipAquecimento(models.Model):
    """Um chip/numero participando do aquecimento"""
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando Conexao'),
        ('conectado', 'Conectado'),
        ('aquecendo', 'Aquecendo'),
        ('pronto', 'Pronto para Uso'),
        ('banido', 'Banido'),
        ('pausado', 'Pausado'),
    ]

    plano = models.ForeignKey(PlanoAquecimento, on_delete=models.CASCADE, related_name='chips')
    instancia = models.ForeignKey(InstanciaWhatsApp, on_delete=models.CASCADE, related_name='aquecimento_chips')
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name='Numero WhatsApp')
    apelido = models.CharField(max_length=50, blank=True, verbose_name='Apelido (para IA conversar)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando')

    # Estatisticas
    msgs_enviadas_total = models.IntegerField(default=0)
    msgs_enviadas_hoje = models.IntegerField(default=0)
    msgs_recebidas_total = models.IntegerField(default=0)
    ultimo_envio = models.DateTimeField(blank=True, null=True)
    erros_consecutivos = models.IntegerField(default=0)

    # Persona para IA gerar mensagens naturais
    persona = models.TextField(
        blank=True,
        verbose_name='Persona do chip',
        help_text='Descricao da personalidade para a IA gerar msgs naturais'
    )

    data_entrada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chip em Aquecimento'
        verbose_name_plural = 'Chips em Aquecimento'

    def __str__(self):
        return f"{self.apelido or self.numero} - {self.get_status_display()}"


class GrupoAquecimento(models.Model):
    """Grupo do WhatsApp criado para aquecimento"""
    plano = models.ForeignKey(PlanoAquecimento, on_delete=models.CASCADE, related_name='grupos')
    nome_grupo = models.CharField(max_length=100)
    group_jid = models.CharField(max_length=255, blank=True, null=True, verbose_name='JID do Grupo')
    instancia_criadora = models.ForeignKey(
        InstanciaWhatsApp, on_delete=models.SET_NULL, null=True,
        verbose_name='Instancia que criou o grupo'
    )
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Grupo de Aquecimento'
        verbose_name_plural = 'Grupos de Aquecimento'

    def __str__(self):
        return self.nome_grupo


class ConversaAquecimento(models.Model):
    """Uma conversa (thread) entre chips"""
    TIPO_CHOICES = [
        ('privado', 'Conversa Privada'),
        ('grupo', 'Conversa no Grupo'),
    ]

    plano = models.ForeignKey(PlanoAquecimento, on_delete=models.CASCADE, related_name='conversas')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    grupo = models.ForeignKey(GrupoAquecimento, on_delete=models.CASCADE, null=True, blank=True)
    tema = models.CharField(max_length=200, verbose_name='Tema da conversa')
    participantes = models.ManyToManyField(ChipAquecimento, related_name='conversas')
    ativa = models.BooleanField(default=True)
    total_mensagens = models.IntegerField(default=0)
    max_mensagens = models.IntegerField(default=15, verbose_name='Max msgs nesta conversa')
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_ultima_msg = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-data_ultima_msg']
        verbose_name = 'Conversa de Aquecimento'
        verbose_name_plural = 'Conversas de Aquecimento'

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.tema}"


class MensagemAquecimento(models.Model):
    """Mensagem individual trocada no aquecimento"""
    conversa = models.ForeignKey(ConversaAquecimento, on_delete=models.CASCADE, related_name='mensagens')
    remetente = models.ForeignKey(ChipAquecimento, on_delete=models.CASCADE, related_name='msgs_enviadas_aquecimento')
    destinatario = models.ForeignKey(
        ChipAquecimento, on_delete=models.CASCADE, null=True, blank=True,
        related_name='msgs_recebidas_aquecimento',
        help_text='Null se for mensagem no grupo'
    )
    texto = models.TextField()
    enviada = models.BooleanField(default=False)
    erro = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['data_criacao']
        verbose_name = 'Mensagem de Aquecimento'
        verbose_name_plural = 'Mensagens de Aquecimento'

    def __str__(self):
        return f"{self.remetente} -> {self.texto[:50]}"


class LogDiarioAquecimento(models.Model):
    """Registro diario por chip para controle de volume"""
    chip = models.ForeignKey(ChipAquecimento, on_delete=models.CASCADE, related_name='logs_diarios')
    data = models.DateField()
    msgs_enviadas = models.IntegerField(default=0)
    msgs_recebidas = models.IntegerField(default=0)
    erros = models.IntegerField(default=0)
    meta_dia = models.IntegerField(default=0, verbose_name='Meta de msgs para o dia')

    class Meta:
        unique_together = ['chip', 'data']
        verbose_name = 'Log Diario Aquecimento'
        verbose_name_plural = 'Logs Diarios Aquecimento'

    def __str__(self):
        return f"{self.chip} - {self.data}: {self.msgs_enviadas}/{self.meta_dia}"
