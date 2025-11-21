# src/consumer.py
import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitBroker

from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis
from dateutil import parser as date_parser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consumer")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "finished_drives")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "transflow")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "corridas")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

rabbitmq_url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/"

broker = RabbitBroker(rabbitmq_url)
app = FastStream(broker)

mongo_client: AsyncIOMotorClient | None = None
mongo_collection = None
redis_client: aioredis.Redis | None = None


def _safe_parse_message(message: Any) -> dict:
    if isinstance(message, dict):
        return message
    if isinstance(message, bytes):
        text = message.decode("utf-8")
    else:
        text = str(message)

    return json.loads(text)

async def _ensure_datetime_field(data: dict):
    if "data_criacao" not in data or not data["data_criacao"]:
        data["data_criacao"] = datetime.utcnow()
        return

    val = data["data_criacao"]
    if isinstance(val, datetime):
        return
    try:
        data["data_criacao"] = date_parser.isoparse(str(val))
    except Exception:
        data["data_criacao"] = datetime.utcnow()

@app.subscriber(QUEUE_NAME)
async def processar_corrida_finalizada(message: Any):
    global mongo_collection, redis_client

    try:
        corrida_data = _safe_parse_message(message)
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar mensagem JSON: {e}")
        return
    except Exception as e:
        logger.error(f"Mensagem inválida: {e}")
        return

    id_corrida = corrida_data.get("id_corrida")
    motorista_nome = (corrida_data.get("motorista") or {}).get("nome")
    raw_valor = corrida_data.get("valor_corrida")

    if not id_corrida or not motorista_nome or raw_valor is None:
        logger.error("Mensagem incompleta: precisa de id_corrida, motorista.nome e valor_corrida.")
        return
    try:
        valor_corrida = float(raw_valor)
    except (ValueError, TypeError):
        logger.error(f"valor_corrida inválido: {raw_valor}")
        return

    logger.info(f"Processando corrida {id_corrida} - Motorista: {motorista_nome} - Valor: R$ {valor_corrida:.2f}")

    try:
        saldo_key = f"saldo:{motorista_nome}"
        novo_saldo = await redis_client.incrbyfloat(saldo_key, valor_corrida)
        novo_saldo = float(novo_saldo)
        logger.info(f"Saldo atualizado para {motorista_nome}: R$ {novo_saldo:.2f}")
    except Exception as e:
        logger.exception(f"Erro ao atualizar saldo no Redis: {e}")
    try:
        await _ensure_datetime_field(corrida_data)
        result = await mongo_collection.update_one(
            {"id_corrida": id_corrida},
            {"$set": corrida_data},
            upsert=True
        )
        if result.upserted_id:
            logger.info(f"Corrida {id_corrida} registrada (upsert).")
        else:
            logger.info(f"Corrida {id_corrida} atualizada.")
    except Exception as e:
        logger.exception(f"Erro ao registrar/atualizar corrida no MongoDB: {e}")
        return

    logger.info(f"Corrida {id_corrida} processada com sucesso.")

@app.on_startup
async def on_startup():
    global mongo_client, mongo_collection, redis_client
    logger.info("Inicializando consumer...")

    try:
        mongo_client = AsyncIOMotorClient(MONGO_URI)
        db = mongo_client[MONGO_DB]
        mongo_collection = db[MONGO_COLLECTION]
        await mongo_client.server_info()
        logger.info(f"Conectado ao MongoDB em {MONGO_URI}, DB: {MONGO_DB}, coll: {MONGO_COLLECTION}")
    except Exception as e:
        logger.exception(f"Erro ao conectar no MongoDB: {e}")
        raise

    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info(f"Conectado ao Redis em {REDIS_URL}")
    except Exception as e:
        logger.exception(f"Erro ao conectar no Redis: {e}")
        raise

    logger.info(f"Consumer pronto e escutando fila: {QUEUE_NAME}")

@app.on_shutdown
async def on_shutdown():
    global mongo_client, redis_client
    logger.info("Encerrando consumer...")

    try:
        if redis_client:
            await redis_client.close()
            logger.info("Conexão Redis fechada.")
    except Exception:
        logger.exception("Erro ao fechar conexão Redis.")

    try:
        if mongo_client:
            mongo_client.close()
            logger.info("Conexão MongoDB fechada.")
    except Exception:
        logger.exception("Erro ao fechar conexão MongoDB.")

    logger.info("Consumer encerrado.")

if __name__ == "__main__":
    asyncio.run(app.run())
