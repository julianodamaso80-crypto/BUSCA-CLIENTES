---
title: Integracao Evolution API
domain: integrations
tags: [evolution-api, whatsapp, api]
---

# Integracao com Evolution API

## O que e a Evolution API?

Evolution API e uma API REST para integracao com WhatsApp baseada no Baileys (biblioteca JavaScript nao-oficial).

## Instalacao

### Docker Compose (Recomendado)

```yaml
version: '3.8'
services:
  evolution_api:
    image: atendai/evolution-api:latest
    ports:
      - "8080:8080"
    environment:
      - AUTHENTICATION_API_KEY=sua-chave-secreta
```

Para iniciar:
```bash
docker-compose up -d
```

### Docker Direto

```bash
docker run -d \
  --name evolution_api \
  -p 8080:8080 \
  -e AUTHENTICATION_API_KEY=sua-chave-secreta \
  atendai/evolution-api:latest
```

## Configuracao no Django

No arquivo `core/settings.py`:

```python
# Evolution API
EVOLUTION_API_URL = 'http://localhost:8080'
EVOLUTION_API_KEY = 'sua-chave-secreta'  # Mesma do Docker
```

## Endpoints Principais

### Criar Instancia

```http
POST /instance/create
Content-Type: application/json
apikey: sua-chave

{
    "instanceName": "minha-instancia",
    "qrcode": true
}
```

### Obter QR Code

```http
GET /instance/qrcode/{instanceName}
apikey: sua-chave
```

Retorna imagem do QR Code em base64.

### Verificar Conexao

```http
GET /instance/connectionState/{instanceName}
apikey: sua-chave
```

Respostas possiveis:
- `open`: Conectado
- `close`: Desconectado
- `connecting`: Conectando

### Enviar Mensagem de Texto

```http
POST /message/sendText/{instanceName}
Content-Type: application/json
apikey: sua-chave

{
    "number": "5511999999999",
    "textMessage": {
        "text": "Sua mensagem aqui"
    }
}
```

### Desconectar Instancia

```http
DELETE /instance/logout/{instanceName}
apikey: sua-chave
```

### Deletar Instancia

```http
DELETE /instance/delete/{instanceName}
apikey: sua-chave
```

## Implementacao no Django

### Service de Integracao

```python
# disparo/services.py

import requests
from django.conf import settings

class EvolutionAPIService:
    def __init__(self):
        self.base_url = settings.EVOLUTION_API_URL
        self.api_key = settings.EVOLUTION_API_KEY
        self.headers = {'apikey': self.api_key}

    def create_instance(self, name):
        response = requests.post(
            f"{self.base_url}/instance/create",
            json={"instanceName": name, "qrcode": True},
            headers=self.headers
        )
        return response.json()

    def send_message(self, instance, number, text):
        response = requests.post(
            f"{self.base_url}/message/sendText/{instance}",
            json={
                "number": number,
                "textMessage": {"text": text}
            },
            headers=self.headers
        )
        return response.json()
```

## Tratamento de Erros

### Erros Comuns

| Codigo | Descricao | Solucao |
|--------|-----------|---------|
| 401 | API Key invalida | Verificar EVOLUTION_API_KEY |
| 404 | Instancia nao encontrada | Criar nova instancia |
| 400 | Numero invalido | Verificar formato do numero |

### Formato de Numero

O numero deve estar no formato internacional sem caracteres especiais:
- Correto: `5511999999999`
- Incorreto: `+55 (11) 99999-9999`

## Webhooks (Opcional)

A Evolution API pode enviar webhooks para eventos:

```yaml
WEBHOOK_URL: "https://seu-dominio.com/webhook/evolution"
WEBHOOK_EVENTS: "messages,connection"
```

## Limites e Consideracoes

1. **Nao e API oficial**: Pode sofrer alteracoes do WhatsApp
2. **Risco de bloqueio**: Seguir boas praticas anti-spam
3. **Persistencia**: Use volumes Docker para persistir sessoes
4. **Atualizacoes**: Manter a API atualizada
