import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBClient:
    _instance: Optional['MongoDBClient'] = None
    _client: Optional[MongoClient] = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self.connect()

    def connect(self):
        try:
            mongo_host = os.getenv("MONGO_HOST", "localhost")
            mongo_port = int(os.getenv("MONGO_PORT", "27017"))
            mongo_db = os.getenv("MONGO_DB", "transflow")

            connection_string = f"mongodb://{mongo_host}:{mongo_port}/"

            self._client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000
            )

            self._client.admin.command("ping")

            self._db = self._client[mongo_db]

            logger.info(f"MongoDB conectado: {mongo_host}:{mongo_port}/{mongo_db}")

        except ConnectionFailure as e:
            logger.error(f"Falha ao conectar ao MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao conectar ao MongoDB: {e}")
            raise

    def get_database(self):
        if self._db is None:
            self.connect()
        return self._db

    def get_collection(self, collection_name: str):
        db = self.get_database()
        return db[collection_name]

    def close(self):
        if self._client:
            self._client.close()
            logger.info("Conexão com MongoDB encerrada.")

mongo_client = MongoDBClient()

def get_mongo_db():
    return mongo_client.get_database()

def get_corridas_collection():
    return mongo_client.get_collection("corridas")
