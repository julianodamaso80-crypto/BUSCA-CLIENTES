from apify_client import ApifyClient
from django.conf import settings
from .models import BuscaCliente, ClienteEncontrado, Estado, Cidade


class GoogleMapsService:
    def __init__(self):
        self.client = ApifyClient(settings.APIFY_API_TOKEN)
        self.actor_id = settings.APIFY_GOOGLE_MAPS_ACTOR

    def buscar_clientes(self, busca: BuscaCliente) -> list:
        """
        Executa a busca no Google Maps usando o Apify
        """
        # Monta a localização para busca
        cidade = busca.cidade.nome if busca.cidade else ''
        estado = busca.estado.sigla if busca.estado else ''
        localizacao = f"{cidade}, {estado}, Brasil"

        # Configuração do actor
        run_input = {
            "searchStringsArray": [busca.termo_busca],
            "locationQuery": localizacao,
            "maxCrawledPlacesPerSearch": 50,
            "language": "pt-BR",
            "skipClosedPlaces": True,
        }

        # Executa o actor
        run = self.client.actor(self.actor_id).call(run_input=run_input)

        # Obtém os resultados
        resultados = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            resultados.append(item)

        # Salva os clientes encontrados
        clientes_salvos = self._salvar_clientes(busca, resultados)

        # Atualiza o total de resultados
        busca.total_resultados = len(clientes_salvos)
        busca.save()

        return clientes_salvos

    def _salvar_clientes(self, busca: BuscaCliente, resultados: list) -> list:
        """
        Salva os clientes encontrados no banco de dados
        """
        clientes_salvos = []

        for item in resultados:
            # Aplica filtros
            telefone = item.get('phone') or item.get('phoneUnformatted')
            email = self._extrair_email(item)
            endereco = item.get('address')

            # Verifica filtros
            if busca.apenas_whatsapp and not telefone:
                continue
            if busca.apenas_email and not email:
                continue
            if busca.apenas_endereco and not endereco:
                continue

            # Cria o cliente
            cliente = ClienteEncontrado.objects.create(
                busca=busca,
                nome=item.get('title', 'Sem nome'),
                telefone=item.get('phone'),
                whatsapp=item.get('phoneUnformatted'),
                email=email,
                endereco=endereco,
                cidade=item.get('city'),
                estado=item.get('state'),
                website=item.get('website'),
                avaliacao=item.get('totalScore'),
                total_avaliacoes=item.get('reviewsCount'),
                categoria=', '.join(item.get('categories', [])) if item.get('categories') else None,
            )
            clientes_salvos.append(cliente)

        return clientes_salvos

    def _extrair_email(self, item: dict) -> str:
        """
        Tenta extrair email dos dados disponíveis
        """
        # O Google Maps geralmente não retorna email diretamente
        # Mas alguns actors podem extrair do website
        return item.get('email') or None
