---
title: Funcionalidade de Busca de Clientes
domain: features
tags: [busca, google-maps, clientes]
---

# Busca de Clientes

## Descricao

A funcionalidade de busca de clientes permite encontrar empresas e contatos atraves da integracao com o Google Maps via API Apify.

## Como Funciona

### Processo de Busca

1. Usuario seleciona o estado
2. Usuario seleciona a cidade (carregada via AJAX)
3. Usuario informa o segmento de busca (ex: "restaurantes", "oficinas mecanicas")
4. Sistema envia requisicao para Apify
5. Resultados sao processados e salvos no banco

### Informacoes Coletadas

Para cada empresa encontrada, coletamos:

- **Nome**: Nome comercial da empresa
- **Endereco**: Endereco completo
- **Telefone**: Numero de telefone (quando disponivel)
- **Website**: URL do site (quando disponivel)
- **Avaliacao**: Nota no Google Maps
- **Categoria**: Tipo de negocio

## Fluxo do Usuario

```
Dashboard -> Buscar Clientes -> Selecionar Local -> Informar Segmento -> Ver Resultados
```

### Pagina de Busca

A pagina de busca (`/dashboard/buscar/`) apresenta:
- Dropdown de estados (carregado do banco)
- Dropdown de cidades (carregado via AJAX ao selecionar estado)
- Campo de texto para segmento
- Botao de buscar

### Pagina de Resultados

A pagina de resultados (`/dashboard/resultados/<id>/`) exibe:
- Tabela com todos os clientes encontrados
- Opcao de exportar para CSV
- Botao para voltar e fazer nova busca

## Limites e Restricoes

- Cada busca pode retornar ate 100 resultados
- Buscas sao vinculadas ao usuario logado
- Historico de buscas fica disponivel no dashboard

## Integracao com Apify

### Actor Utilizado

Utilizamos o actor `compass/crawler-google-places` da Apify.

### Parametros Enviados

```python
{
    "searchStringsArray": ["segmento em cidade, estado"],
    "maxCrawledPlaces": 100,
    "language": "pt-BR",
    "maxImages": 0
}
```

### Tratamento de Erros

- Se a API falhar, exibimos mensagem de erro ao usuario
- Tentativas de retry automatico em caso de timeout
- Log de erros para analise posterior

## Exportacao CSV

O usuario pode exportar os resultados em formato CSV com as seguintes colunas:
- Nome
- Endereco
- Telefone
- Website
- Avaliacao
- Categoria

O arquivo e gerado dinamicamente e baixado pelo navegador.
