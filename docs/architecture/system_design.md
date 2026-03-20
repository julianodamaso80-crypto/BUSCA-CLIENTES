---
title: Arquitetura do Sistema
domain: architecture
tags: [arquitetura, django, sistema]
---

# Arquitetura do Sistema

## Visao Geral

O BUSCA CLIENTES e uma aplicacao Django modular que segue o padrao MVT (Model-View-Template).

## Diagrama de Arquitetura

```
                    +------------------+
                    |    USUARIO       |
                    |    (Browser)     |
                    +--------+---------+
                             |
                             | HTTPS
                             v
+-----------------------------------------------------------+
|                     DJANGO APPLICATION                     |
|-----------------------------------------------------------|
|                                                           |
|  +-------------+  +-------------+  +-------------+        |
|  |  accounts   |  |  clientes   |  |  disparo    |        |
|  |  (Auth)     |  |  (Search)   |  |  (WhatsApp) |        |
|  +------+------+  +------+------+  +------+------+        |
|         |                |                |               |
|         +----------------+----------------+               |
|                          |                                |
|                    +-----+-----+                          |
|                    |   core    |                          |
|                    | (Config)  |                          |
|                    +-----------+                          |
|                                                           |
+-----------------------------------------------------------+
          |                    |                    |
          v                    v                    v
   +-----------+        +-----------+        +-----------+
   |  SQLite/  |        |  Apify    |        | Evolution |
   | PostgreSQL|        |   API     |        |    API    |
   +-----------+        +-----------+        +-----------+
```

## Componentes

### Apps Django

#### 1. core/
Configuracao central do projeto.
- `settings.py`: Configuracoes globais
- `urls.py`: Roteamento principal
- `wsgi.py`: Configuracao WSGI

#### 2. accounts/
Autenticacao e gerenciamento de usuarios.
- Login/Logout
- Isolamento de dados por usuario
- Sessoes e permissoes

#### 3. clientes/
Busca e gerenciamento de clientes.
- Models: Estado, Cidade, BuscaCliente, ClienteEncontrado
- Integracao com Apify
- Exportacao CSV

#### 4. disparo/
Campanhas de WhatsApp.
- Models: InstanciaWhatsApp, CampanhaDisparo, LogEnvio
- Integracao Evolution API
- Sistema anti-bloqueio

#### 5. context/ (Novo)
Sistema de contexto para IA.
- Ingestao de documentos
- Busca semantica
- Gerenciamento de conhecimento

### Servicos Externos

#### Apify (Google Maps)
- **Funcao**: Buscar dados de empresas
- **Actor**: `compass/crawler-google-places`
- **Autenticacao**: API Token

#### Evolution API (WhatsApp)
- **Funcao**: Enviar mensagens
- **Tecnologia**: Docker container
- **Autenticacao**: API Key

### Banco de Dados

#### Desenvolvimento
- SQLite (arquivo local)

#### Producao (Planejado)
- PostgreSQL

### Frontend

- HTML5 + Tailwind CSS
- JavaScript vanilla para interatividade
- AJAX para operacoes assincronas

## Fluxo de Dados

### Busca de Clientes

```
1. Usuario -> Django View
2. Django View -> Apify API
3. Apify API -> Google Maps
4. Resultados -> Django Models
5. Django Models -> Template
6. Template -> Usuario
```

### Disparo de WhatsApp

```
1. Usuario cria campanha
2. Sistema processa fila de mensagens
3. Para cada mensagem:
   a. Aplica delay
   b. Envia via Evolution API
   c. Registra log
4. Atualiza status da campanha
```

## Seguranca

### Autenticacao
- Django built-in auth
- Sessoes com cookie seguro
- CSRF protection

### Dados Sensiveis
- API keys em variaveis de ambiente
- Senhas hasheadas no banco
- HTTPS em producao

### Isolamento
- Dados filtrados por usuario logado
- Permissoes por view

## Escalabilidade

### Atual (MVP)
- Servidor unico
- SQLite
- Sincrono

### Futuro
- Load balancer
- PostgreSQL
- Celery para tarefas assincronas
- Redis para cache

## Monitoramento

### Logs
- Django logging
- Logs de ingestao de contexto
- Logs de envio de mensagens

### Metricas
- Buscas realizadas
- Mensagens enviadas
- Erros de API
