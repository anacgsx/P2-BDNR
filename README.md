---
# TransFlow

Sistema de Gerenciamento de Corridas Urbanas com MongoDB, Redis e Mensageria Assíncrona

## Visão Geral

TransFlow é um sistema backend desenvolvido para gerenciar corridas urbanas utilizando uma arquitetura orientada a eventos. O projeto integra três componentes principais:

* **MongoDB** para armazenamento de dados das corridas.
* **Redis** para gerenciamento de saldos dos motoristas.
* **RabbitMQ** para mensageria assíncrona entre produtor e consumidor.

A aplicação é totalmente conteinerizada com **Docker Compose**, expondo APIs de cadastro, consulta, atualização e exclusão de corridas, além de endpoints para consulta e definição de saldo dos motoristas.

---

## Tecnologias Utilizadas

* **Python 3.11**
* **FastAPI**
* **MongoDB**
* **Redis**
* **RabbitMQ**
* **Docker e Docker Compose**
* **Uvicorn**
* **Motor (MongoDB Async)**
* **FastStream (RabbitMQ)**

---

## Arquitetura Geral

A arquitetura do TransFlow é composta por quatro serviços principais:

1. **API FastAPI (app)**

   * Expõe endpoints REST.
   * Publica mensagens no RabbitMQ sobre corridas cadastradas.

2. **Consumer (consumer.py)**

   * Escuta mensagens publicadas na fila RabbitMQ.
   * Atualiza saldos no Redis.
   * Atualiza ou cria registros de corridas no MongoDB.

3. **MongoDB**

   * Armazena dados completos das corridas.

4. **Redis**

   * Armazena os saldos acumulados dos motoristas.

---

## Estrutura de Pastas

```
Prova P2 - Banco de dados não relacional/
│
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
│
├─ src/
│  ├─ main.py
│  ├─ consumer.py
│  ├─ producer.py
│  ├─ models/
│  │   └─ corrida_model.py
│  └─ database/
│      └─ mongo_client.py
│
└─ README.md
```

---

## Serviços do Docker Compose

### MongoDB

* Porta exposta: `27018:27017`
* Persistência via volume: `mongo_data`
* Healthcheck configurado com `mongosh`.

### Redis

* Porta exposta: `6380:6379`
* Volume persistente: `redis_data`
* Healthcheck via `redis-cli ping`.

### RabbitMQ (com painel de administração)

* Porta AMQP: `5672`
* Painel: `15672`
* Credenciais padrão: `guest / guest`
* Persistência via volume `rabbitmq_data`

### Aplicação FastAPI

* Porta exposta: `8000:8000`
* Dependente da saúde dos outros três serviços.
* Inicializa:

  * o produtor RabbitMQ,
  * os saldos de exemplo em Redis,
  * o servidor FastAPI.

---

## Funcionalidades da Aplicação

### Cadastro de Corridas

`POST /corridas`

* Gera um ID único.
* Registra data de criação.
* Publica evento no RabbitMQ.

### Listagem de Corridas

`GET /corridas`

* Retorna todas as corridas registradas no MongoDB.

### Filtro por Forma de Pagamento

`GET /corridas/{forma_pagamento}`

* Filtra corridas por forma de pagamento usando regex case-insensitive.

### Consulta de Saldo

`GET /saldo/{motorista}`

* Retorna o saldo atual do motorista no Redis.

### Definição Manual de Saldo

`PUT /saldo/{motorista}`

* Atualiza saldo de um motorista, não permitindo valores negativos.

### Deleção de Corrida

`DELETE /corridas/{id_corrida}`

* Remove um registro de corrida no MongoDB.

### Health Check

`GET /health`

* Verifica o status de MongoDB, Redis e RabbitMQ.
* Retorna código 503 se algum estiver indisponível.

---

## Fluxo de Processamento da Corrida

1. A API recebe os dados da corrida.
2. O produtor publica o evento no RabbitMQ.
3. O consumidor lê a mensagem da fila.
4. O consumidor:

   * Atualiza saldo no Redis.
   * Valida e registra a corrida no MongoDB.

---

## Instruções para Execução

### Pré-requisitos

* Docker
* Docker Compose

### Inicialização

```bash
docker-compose up --build
```

A aplicação ficará disponível em:

```
http://localhost:8000
```

Documentação automática:

```
http://localhost:8000/docs
```

Painel do RabbitMQ:

```
http://localhost:15672
```

---

## Variáveis de Ambiente

As variáveis são configuradas automaticamente via Docker Compose:

### MongoDB

* `MONGO_HOST=mongo`
* `MONGO_PORT=27017`
* `MONGO_DB=transflow`

### Redis

* `REDIS_HOST=redis`
* `REDIS_PORT=6379`

### RabbitMQ

* `RABBITMQ_HOST=rabbitmq`
* `RABBITMQ_PORT=5672`
* `RABBITMQ_USER=guest`
* `RABBITMQ_PASSWORD=guest`
* `RABBITMQ_QUEUE=finished_drives`

---

## Testando a API

### Exemplo de Requisição para Cadastro

```json
POST /corridas
{
  "motorista": {
    "nome": "Carlos"
  },
  "valor_corrida": 32.5,
  "forma_pagamento": "cartao"
}
```

### Exemplo de Resposta

```json
{
  "id_corrida": "a1b2c3d4",
  "motorista": {
    "nome": "Carlos"
  },
  "valor_corrida": 32.5,
  "forma_pagamento": "cartao",
  "data_criacao": "2024-01-01T12:00:00.000Z"
}
```

---

## Logs e Monitoramento

* A aplicação utiliza `logging` com nível INFO.
* Tanto o produtor quanto o consumidor registram eventos relevantes:

  * Conexões
  * Erros
  * Atualizações de saldo
  * Upserts de corridas no MongoDB

---

## Encerramento

```bash
docker-compose down
```

Com remoção dos volumes:

```bash
docker-compose down -v
```

---
