import os
import redis
from redis.exceptions import ConnectionError, RedisError
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RedisClient:
    _instance: Optional['RedisClient'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self.connect()

    def connect(self):
        try:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))

            self._client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=5,  # Evita travar no Windows
                socket_timeout=5
            )

            self._client.ping()
            logger.info(f"Conectado ao Redis em {redis_host}:{redis_port}")

        except ConnectionError as e:
            logger.error(f"Erro de conexão com Redis: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar no Redis: {e}")
            raise

    def get_client(self) -> redis.Redis:
        if self._client is None:
            self.connect()
        return self._client

    def get_saldo(self, motorista: str) -> float:
        try:
            key = f"saldo:{motorista.lower()}"
            saldo = self._client.get(key)

            if saldo is None:
                self._client.set(key, "0.0")
                return 0.0

            return float(saldo)

        except RedisError as e:
            logger.error(f"Erro ao obter saldo: {e}")
            raise

    def set_saldo(self, motorista: str, valor: float) -> bool:
        try:
            key = f"saldo:{motorista.lower()}"
            self._client.set(key, str(valor))
            logger.info(f"Saldo de {motorista} definido para R$ {valor:.2f}")
            return True

        except RedisError as e:
            logger.error(f"Erro ao definir saldo: {e}")
            raise

    def incrementar_saldo(self, motorista: str, valor: float) -> float:
        try:
            key = f"saldo:{motorista.lower()}"
            pipe = self._client.pipeline()
            max_tentativas = 10

            for tentativa in range(max_tentativas):
                try:
                    pipe.watch(key)

                    saldo_atual = pipe.get(key)
                    saldo_atual = float(saldo_atual) if saldo_atual else 0.0

                    novo_saldo = saldo_atual + valor

                    pipe.multi()
                    pipe.set(key, str(novo_saldo))
                    pipe.execute()

                    logger.info(
                        f"Saldo de {motorista} atualizado: "
                        f"R$ {saldo_atual:.2f} → R$ {novo_saldo:.2f} "
                        f"(+R$ {valor:.2f})"
                    )

                    return novo_saldo

                except redis.WatchError:
                    logger.warning(
                        f"Tentativa {tentativa + 1}/{max_tentativas}: conflito ao atualizar saldo"
                    )
                    continue

                finally:
                    pipe.reset()

            raise Exception(
                f"Falha ao atualizar saldo após {max_tentativas} tentativas"
            )

        except RedisError as e:
            logger.error(f"Erro ao incrementar saldo: {e}")
            raise

    def close(self):
        if self._client:
            try:
                self._client.close()
                logger.info("Conexão Redis fechada")
            except Exception:
                pass

redis_client = RedisClient()

def get_redis_client() -> redis.Redis:
    return redis_client.get_client()
