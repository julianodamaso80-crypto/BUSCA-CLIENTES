---
title: Disparo de Mensagens WhatsApp
domain: features
tags: [whatsapp, disparo, campanhas, evolution-api]
---

# Disparo de Mensagens WhatsApp

## Descricao

O modulo de disparo permite enviar mensagens em massa via WhatsApp utilizando a Evolution API, com protecoes integradas contra bloqueio do numero.

## Componentes do Sistema

### Instancia WhatsApp

Antes de enviar mensagens, o usuario precisa conectar seu WhatsApp:

1. Criar nova instancia na plataforma
2. Escanear QR Code com o celular
3. Aguardar confirmacao de conexao

### Campanhas de Disparo

Uma campanha contem:
- Nome da campanha
- Mensagem a ser enviada
- Lista de destinatarios
- Configuracoes de envio

## Protecoes Anti-Bloqueio

O sistema implementa 6 protecoes principais:

### 1. Limites por Idade do Numero

| Idade do Numero | Limite Diario |
|-----------------|---------------|
| < 1 semana      | 40 mensagens  |
| 1-4 semanas     | 100 mensagens |
| 1-3 meses       | 250 mensagens |
| > 3 meses       | 500 mensagens |

### 2. Delay Aleatorio

Entre cada mensagem, o sistema aguarda entre 15 e 60 segundos de forma aleatoria.

### 3. Pausas Periodicas

A cada 10-20 mensagens, o sistema faz uma pausa maior de 2-5 minutos.

### 4. Horario de Envio

Mensagens so sao enviadas dentro do horario configurado:
- Horario comercial padrao: 08:00 - 18:00
- Configuravel pelo usuario

### 5. Lista de Bloqueados

Numeros que pediram para nao receber mais mensagens sao automaticamente bloqueados.

### 6. Personalizacao

Cada mensagem pode ser personalizada com o nome do cliente, reduzindo a aparencia de spam.

## Fluxo de Criacao de Campanha

1. Acessar `/disparo/criar-campanha/`
2. Selecionar instancia WhatsApp conectada
3. Escolher uma busca como fonte de contatos
4. Escrever a mensagem (com variaveis de personalizacao)
5. Configurar horarios e limites
6. Iniciar campanha

## Variaveis de Personalizacao

Na mensagem, voce pode usar:
- `{nome}` - Nome do cliente
- `{empresa}` - Nome da empresa
- `{cidade}` - Cidade do cliente

Exemplo:
```
Ola {nome}! Vi que a {empresa} fica em {cidade}.
Gostaria de apresentar nossos servicos...
```

## Status da Campanha

Uma campanha pode ter os seguintes status:

- **Rascunho**: Campanha criada mas nao iniciada
- **Em andamento**: Enviando mensagens
- **Pausada**: Pausada pelo usuario
- **Concluida**: Todos os envios realizados
- **Cancelada**: Cancelada pelo usuario

## Monitoramento

O dashboard de campanha mostra:
- Total de mensagens a enviar
- Mensagens enviadas com sucesso
- Mensagens com erro
- Progresso em tempo real

## Integracao Evolution API

### Endpoints Utilizados

```
POST /instance/create - Criar instancia
GET  /instance/qrcode - Obter QR Code
GET  /instance/connectionState - Verificar conexao
POST /message/sendText - Enviar mensagem
DELETE /instance/delete - Deletar instancia
```

### Configuracao

No `settings.py`:
```python
EVOLUTION_API_URL = 'http://localhost:8080'
EVOLUTION_API_KEY = 'sua-chave-api'
```

## Boas Praticas

1. **Nao envie spam**: Use apenas para contatos relevantes
2. **Respeite o horario**: Evite mensagens fora do horario comercial
3. **Personalize**: Mensagens personalizadas tem melhor recepcao
4. **Monitore**: Acompanhe as metricas de entrega
5. **Respeite bloqueios**: Remova contatos que pedirem
