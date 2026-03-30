from django.db import models
from django.contrib.auth.models import User


class Estado(models.Model):
    nome = models.CharField(max_length=100)
    sigla = models.CharField(max_length=2)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Estado'
        verbose_name_plural = 'Estados'

    def __str__(self):
        return f"{self.nome} ({self.sigla})"


class Cidade(models.Model):
    nome = models.CharField(max_length=200)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, related_name='cidades')

    class Meta:
        ordering = ['nome']
        verbose_name = 'Cidade'
        verbose_name_plural = 'Cidades'

    def __str__(self):
        return f"{self.nome} - {self.estado.sigla}"


class BuscaCliente(models.Model):
    FONTE_CHOICES = [
        ('google_maps', 'Google Maps'),
        ('linkedin', 'LinkedIn'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buscas')
    termo_busca = models.CharField(max_length=255, verbose_name='Termo de busca')
    fonte = models.CharField(max_length=20, choices=FONTE_CHOICES, default='google_maps')
    estado = models.ForeignKey(Estado, on_delete=models.SET_NULL, null=True, blank=True)
    cidade = models.ForeignKey(Cidade, on_delete=models.SET_NULL, null=True, blank=True)
    apenas_whatsapp = models.BooleanField(default=False, verbose_name='Apenas com WhatsApp')
    apenas_email = models.BooleanField(default=False, verbose_name='Apenas com Email')
    apenas_endereco = models.BooleanField(default=False, verbose_name='Apenas com Endereço')
    max_resultados = models.IntegerField(default=50, verbose_name='Max. Resultados')
    data_busca = models.DateTimeField(auto_now_add=True)
    total_resultados = models.IntegerField(default=0)

    # === CAMPOS DE ENRIQUECIMENTO ===
    enriquecida = models.BooleanField(default=False)
    data_enriquecimento = models.DateTimeField(blank=True, null=True)
    total_qualificados = models.IntegerField(default=0)

    class Meta:
        ordering = ['-data_busca']
        verbose_name = 'Busca de Cliente'
        verbose_name_plural = 'Buscas de Clientes'

    def __str__(self):
        return f"{self.termo_busca} - {self.data_busca.strftime('%d/%m/%Y %H:%M')}"


class ClienteEncontrado(models.Model):
    busca = models.ForeignKey(BuscaCliente, on_delete=models.CASCADE, related_name='clientes')
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=50, blank=True, null=True)
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    cidade = models.CharField(max_length=200, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    avaliacao = models.DecimalField(max_digits=2, decimal_places=1, blank=True, null=True)
    total_avaliacoes = models.IntegerField(blank=True, null=True)
    categoria = models.CharField(max_length=255, blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    # === CAMPOS DE ENRIQUECIMENTO CNPJ ===
    cnpj = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    razao_social = models.CharField(max_length=255, blank=True, null=True)
    nome_fantasia = models.CharField(max_length=255, blank=True, null=True)
    situacao_cadastral = models.CharField(max_length=50, blank=True, null=True)
    cnae_principal = models.CharField(max_length=10, blank=True, null=True)
    cnae_descricao = models.CharField(max_length=255, blank=True, null=True)
    porte = models.CharField(max_length=50, blank=True, null=True)
    capital_social = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    data_abertura = models.DateField(blank=True, null=True)
    natureza_juridica = models.CharField(max_length=255, blank=True, null=True)

    # === CAMPOS DE QUALIFICACAO ===
    lead_score = models.IntegerField(default=0, db_index=True)
    score_detalhes = models.JSONField(default=dict, blank=True)
    classificacao = models.CharField(
        max_length=20,
        choices=[
            ('quente', 'Lead Quente'),
            ('morno', 'Lead Morno'),
            ('frio', 'Lead Frio'),
            ('descartado', 'Descartado'),
        ],
        default='frio',
        db_index=True,
    )

    # === CAMPOS DE VALIDACAO ===
    whatsapp_validado = models.BooleanField(default=False)
    whatsapp_existe = models.BooleanField(null=True, blank=True)
    tem_website = models.BooleanField(null=True, blank=True)
    tem_redes_sociais = models.BooleanField(null=True, blank=True)

    # === STATUS DE ENRIQUECIMENTO ===
    enriquecido = models.BooleanField(default=False)
    data_enriquecimento = models.DateTimeField(blank=True, null=True)
    erro_enriquecimento = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Cliente Encontrado'
        verbose_name_plural = 'Clientes Encontrados'

    def __str__(self):
        return self.nome
