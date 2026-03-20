---
title: Fluxo de Busca de Clientes
domain: flows
tags: [fluxo, busca, usuario]
---

# Fluxo de Busca de Clientes

## Visao Geral

Este documento descreve o fluxo completo que um usuario percorre para buscar clientes na plataforma.

## Diagrama do Fluxo

```
[Login]
    |
    v
[Dashboard] ---> [Buscar Clientes]
                       |
                       v
                 [Selecionar Estado]
                       |
                       v
                 [Selecionar Cidade] (AJAX)
                       |
                       v
                 [Informar Segmento]
                       |
                       v
                 [Clicar Buscar]
                       |
                       v
                 [Aguardar Processamento]
                       |
            +----------+-----------+
            |                      |
            v                      v
       [Sucesso]              [Erro]
            |                      |
            v                      v
    [Ver Resultados]        [Tentar Novamente]
            |
            v
    [Exportar CSV] (opcional)
```

## Etapas Detalhadas

### 1. Autenticacao

- **URL**: `/login/`
- **Acao**: Usuario informa credenciais
- **Resultado**: Redirecionamento para dashboard

### 2. Dashboard

- **URL**: `/dashboard/`
- **Visualizacao**: Estatisticas e buscas recentes
- **Acao**: Clicar em "Buscar Clientes"

### 3. Pagina de Busca

- **URL**: `/dashboard/buscar/`
- **Elementos**:
  - Dropdown de estados (pre-carregado)
  - Dropdown de cidades (vazio inicialmente)
  - Campo de segmento
  - Botao buscar

### 4. Selecao de Estado

- **Acao**: Usuario seleciona um estado
- **Trigger**: Evento `change` no dropdown
- **Resultado**: Requisicao AJAX para `/dashboard/get-cidades/`

### 5. Carregamento de Cidades

- **Endpoint**: `/dashboard/get-cidades/?estado_id=X`
- **Resposta**: JSON com lista de cidades
- **Acao**: Preencher dropdown de cidades

### 6. Informar Segmento

- **Campo**: Input de texto
- **Exemplos**: "restaurantes", "oficinas", "saloes de beleza"
- **Validacao**: Campo obrigatorio

### 7. Executar Busca

- **Acao**: Clicar no botao "Buscar"
- **Metodo**: POST
- **Dados**: estado_id, cidade_id, segmento

### 8. Processamento

- **Backend**:
  1. Cria registro de BuscaCliente
  2. Envia requisicao para Apify
  3. Processa resultados
  4. Salva ClienteEncontrado
- **Frontend**: Exibe indicador de carregamento

### 9. Visualizacao de Resultados

- **URL**: `/dashboard/resultados/<busca_id>/`
- **Exibicao**: Tabela com clientes encontrados
- **Dados**: Nome, endereco, telefone, etc.

### 10. Exportacao (Opcional)

- **URL**: `/dashboard/exportar/<busca_id>/`
- **Formato**: CSV
- **Download**: Automatico pelo navegador

## Pontos de Atencao

### Validacoes

1. Usuario deve estar autenticado
2. Todos os campos sao obrigatorios
3. Estado deve ter cidades cadastradas

### Tratamento de Erros

| Erro | Mensagem | Acao |
|------|----------|------|
| API indisponivel | "Servico temporariamente indisponivel" | Tentar novamente |
| Nenhum resultado | "Nenhum cliente encontrado" | Refinar busca |
| Timeout | "A busca demorou muito" | Tentar segmento mais especifico |

### Performance

- Timeout da API: 60 segundos
- Maximo de resultados: 100 por busca
- Cidades carregadas via AJAX para performance

## Dados Salvos

### Modelo BuscaCliente

```python
- usuario (FK)
- estado (FK)
- cidade (FK)
- segmento (texto)
- data_busca (datetime)
- quantidade_resultados (int)
```

### Modelo ClienteEncontrado

```python
- busca (FK)
- nome (texto)
- endereco (texto)
- telefone (texto)
- website (URL)
- avaliacao (decimal)
- categoria (texto)
```
