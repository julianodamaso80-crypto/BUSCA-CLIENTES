from django.core.management.base import BaseCommand
from clientes.models import Estado, Cidade


class Command(BaseCommand):
    help = 'Popula o banco de dados com estados e cidades do Brasil'

    def handle(self, *args, **options):
        self.stdout.write('Populando estados e cidades do Brasil...')

        # Dados dos estados e suas principais cidades
        dados = {
            'AC': {
                'nome': 'Acre',
                'cidades': ['Rio Branco', 'Cruzeiro do Sul', 'Sena Madureira', 'Tarauacá', 'Feijó']
            },
            'AL': {
                'nome': 'Alagoas',
                'cidades': ['Maceió', 'Arapiraca', 'Rio Largo', 'Palmeira dos Índios', 'União dos Palmares']
            },
            'AP': {
                'nome': 'Amapá',
                'cidades': ['Macapá', 'Santana', 'Laranjal do Jari', 'Oiapoque', 'Mazagão']
            },
            'AM': {
                'nome': 'Amazonas',
                'cidades': ['Manaus', 'Parintins', 'Itacoatiara', 'Manacapuru', 'Coari', 'Tefé']
            },
            'BA': {
                'nome': 'Bahia',
                'cidades': ['Salvador', 'Feira de Santana', 'Vitória da Conquista', 'Camaçari', 'Itabuna', 'Juazeiro', 'Lauro de Freitas', 'Ilhéus', 'Jequié', 'Barreiras']
            },
            'CE': {
                'nome': 'Ceará',
                'cidades': ['Fortaleza', 'Caucaia', 'Juazeiro do Norte', 'Maracanaú', 'Sobral', 'Crato', 'Itapipoca', 'Maranguape', 'Iguatu', 'Quixadá']
            },
            'DF': {
                'nome': 'Distrito Federal',
                'cidades': ['Brasília', 'Ceilândia', 'Taguatinga', 'Samambaia', 'Plano Piloto', 'Águas Claras', 'Gama', 'Guará']
            },
            'ES': {
                'nome': 'Espírito Santo',
                'cidades': ['Vitória', 'Vila Velha', 'Serra', 'Cariacica', 'Cachoeiro de Itapemirim', 'Linhares', 'São Mateus', 'Colatina']
            },
            'GO': {
                'nome': 'Goiás',
                'cidades': ['Goiânia', 'Aparecida de Goiânia', 'Anápolis', 'Rio Verde', 'Luziânia', 'Águas Lindas de Goiás', 'Valparaíso de Goiás', 'Trindade', 'Formosa', 'Novo Gama']
            },
            'MA': {
                'nome': 'Maranhão',
                'cidades': ['São Luís', 'Imperatriz', 'São José de Ribamar', 'Timon', 'Caxias', 'Codó', 'Paço do Lumiar', 'Açailândia', 'Bacabal']
            },
            'MT': {
                'nome': 'Mato Grosso',
                'cidades': ['Cuiabá', 'Várzea Grande', 'Rondonópolis', 'Sinop', 'Tangará da Serra', 'Cáceres', 'Sorriso', 'Lucas do Rio Verde', 'Primavera do Leste']
            },
            'MS': {
                'nome': 'Mato Grosso do Sul',
                'cidades': ['Campo Grande', 'Dourados', 'Três Lagoas', 'Corumbá', 'Ponta Porã', 'Naviraí', 'Nova Andradina', 'Aquidauana', 'Sidrolândia']
            },
            'MG': {
                'nome': 'Minas Gerais',
                'cidades': ['Belo Horizonte', 'Uberlândia', 'Contagem', 'Juiz de Fora', 'Betim', 'Montes Claros', 'Ribeirão das Neves', 'Uberaba', 'Governador Valadares', 'Ipatinga', 'Sete Lagoas', 'Divinópolis', 'Santa Luzia', 'Poços de Caldas', 'Patos de Minas']
            },
            'PA': {
                'nome': 'Pará',
                'cidades': ['Belém', 'Ananindeua', 'Santarém', 'Marabá', 'Parauapebas', 'Castanhal', 'Abaetetuba', 'Cametá', 'Bragança', 'Marituba']
            },
            'PB': {
                'nome': 'Paraíba',
                'cidades': ['João Pessoa', 'Campina Grande', 'Santa Rita', 'Patos', 'Bayeux', 'Sousa', 'Cajazeiras', 'Cabedelo', 'Guarabira']
            },
            'PR': {
                'nome': 'Paraná',
                'cidades': ['Curitiba', 'Londrina', 'Maringá', 'Ponta Grossa', 'Cascavel', 'São José dos Pinhais', 'Foz do Iguaçu', 'Colombo', 'Guarapuava', 'Paranaguá', 'Araucária', 'Toledo', 'Apucarana']
            },
            'PE': {
                'nome': 'Pernambuco',
                'cidades': ['Recife', 'Jaboatão dos Guararapes', 'Olinda', 'Caruaru', 'Petrolina', 'Paulista', 'Cabo de Santo Agostinho', 'Camaragibe', 'Garanhuns', 'Vitória de Santo Antão']
            },
            'PI': {
                'nome': 'Piauí',
                'cidades': ['Teresina', 'Parnaíba', 'Picos', 'Piripiri', 'Floriano', 'Campo Maior', 'Barras', 'União']
            },
            'RJ': {
                'nome': 'Rio de Janeiro',
                'cidades': ['Rio de Janeiro', 'São Gonçalo', 'Duque de Caxias', 'Nova Iguaçu', 'Niterói', 'Belford Roxo', 'São João de Meriti', 'Campos dos Goytacazes', 'Petrópolis', 'Volta Redonda', 'Magé', 'Itaboraí', 'Macaé', 'Cabo Frio', 'Angra dos Reis', 'Nova Friburgo', 'Barra Mansa', 'Teresópolis']
            },
            'RN': {
                'nome': 'Rio Grande do Norte',
                'cidades': ['Natal', 'Mossoró', 'Parnamirim', 'São Gonçalo do Amarante', 'Ceará-Mirim', 'Macaíba', 'Caicó', 'Açu', 'Currais Novos']
            },
            'RS': {
                'nome': 'Rio Grande do Sul',
                'cidades': ['Porto Alegre', 'Caxias do Sul', 'Pelotas', 'Canoas', 'Santa Maria', 'Gravataí', 'Viamão', 'Novo Hamburgo', 'São Leopoldo', 'Rio Grande', 'Alvorada', 'Passo Fundo', 'Sapucaia do Sul', 'Uruguaiana', 'Santa Cruz do Sul', 'Cachoeirinha', 'Bagé', 'Bento Gonçalves']
            },
            'RO': {
                'nome': 'Rondônia',
                'cidades': ['Porto Velho', 'Ji-Paraná', 'Ariquemes', 'Vilhena', 'Cacoal', 'Rolim de Moura', 'Jaru', 'Guajará-Mirim']
            },
            'RR': {
                'nome': 'Roraima',
                'cidades': ['Boa Vista', 'Rorainópolis', 'Caracaraí', 'Alto Alegre', 'Mucajaí', 'Cantá']
            },
            'SC': {
                'nome': 'Santa Catarina',
                'cidades': ['Joinville', 'Florianópolis', 'Blumenau', 'São José', 'Chapecó', 'Itajaí', 'Criciúma', 'Jaraguá do Sul', 'Palhoça', 'Lages', 'Balneário Camboriú', 'Brusque', 'Tubarão', 'São Bento do Sul', 'Caçador']
            },
            'SP': {
                'nome': 'São Paulo',
                'cidades': ['São Paulo', 'Guarulhos', 'Campinas', 'São Bernardo do Campo', 'Santo André', 'São José dos Campos', 'Osasco', 'Ribeirão Preto', 'Sorocaba', 'Mauá', 'São José do Rio Preto', 'Mogi das Cruzes', 'Santos', 'Diadema', 'Jundiaí', 'Piracicaba', 'Carapicuíba', 'Bauru', 'Itaquaquecetuba', 'São Vicente', 'Franca', 'Praia Grande', 'Guarujá', 'Taubaté', 'Limeira', 'Suzano', 'Taboão da Serra', 'Sumaré', 'Barueri', 'Embu das Artes', 'São Carlos', 'Indaiatuba', 'Cotia', 'Americana', 'Marília', 'Araraquara', 'Jacareí', 'Hortolândia', 'Presidente Prudente', 'Rio Claro']
            },
            'SE': {
                'nome': 'Sergipe',
                'cidades': ['Aracaju', 'Nossa Senhora do Socorro', 'Lagarto', 'Itabaiana', 'São Cristóvão', 'Estância', 'Tobias Barreto', 'Itabaianinha']
            },
            'TO': {
                'nome': 'Tocantins',
                'cidades': ['Palmas', 'Araguaína', 'Gurupi', 'Porto Nacional', 'Paraíso do Tocantins', 'Araguatins', 'Colinas do Tocantins', 'Guaraí']
            },
        }

        estados_criados = 0
        cidades_criadas = 0

        for sigla, info in dados.items():
            estado, created = Estado.objects.get_or_create(
                sigla=sigla,
                defaults={'nome': info['nome']}
            )
            if created:
                estados_criados += 1

            for cidade_nome in info['cidades']:
                cidade, created = Cidade.objects.get_or_create(
                    nome=cidade_nome,
                    estado=estado
                )
                if created:
                    cidades_criadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Concluído! {estados_criados} estados e {cidades_criadas} cidades criados.'
            )
        )
