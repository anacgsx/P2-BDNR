import os
import json
import logging
from datetime import datetime
from faststream.rabbit import RabbitBroker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CorridaProducer:
    def __init__(self):
        self.broker = None
        self.queue_name = os.getenv("RABBITMQ_QUEUE", "finished_drives")

    async def connect(self):
        try:
            rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
            rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
            rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
            rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")

            rabbitmq_url = (
                f"amqp://{rabbitmq_user}:{rabbitmq_password}"
                f"@{rabbitmq_host}:{rabbitmq_port}/"
            )

            self.broker = RabbitBroker(rabbitmq_url)
            await self.broker.connect()

            logger.info(f"Producer conectado a {rabbitmq_host}:{rabbitmq_port}")

        except Exception as e:
            logger.error(f"Erro ao conectar producer: {e}")
            raise

    async def publicar_corrida_finalizada(self, corrida_data: dict):
        try:
            if self.broker is None:
                await self.connect()

            if "data_criacao" in corrida_data:
                if isinstance(corrida_data["data_criacao"], datetime):
                    corrida_data["data_criacao"] = corrida_data["data_criacao"].isoformat()
                elif corrida_data["data_criacao"]:
                    corrida_data["data_criacao"] = str(corrida_data["data_criacao"])

            message = json.dumps(corrida_data, ensure_ascii=False)

            await self.broker.publish(
                message=message,
                queue=self.queue_name
            )

            logger.info(
                f"Evento publicado: corrida {corrida_data.get('id_corrida')} "
                f"- Motorista: {corrida_data.get('motorista', {}).get('nome')} "
                f"- Valor: R$ {float(corrida_data.get('valor_corrida', 0)):.2f}"
            )

        except Exception as e:
            logger.error(f"Erro ao publicar evento: {e}")
            raise

    async def close(self):
        if self.broker:
            await self.broker.close()
            logger.info("Producer desconectado")

producer = CorridaProducer()

async def get_producer() -> CorridaProducer:
    if producer.broker is None:
        await producer.connect()
    return producer
