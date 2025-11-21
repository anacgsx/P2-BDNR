from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
import uuid
from datetime import datetime
import logging

from src.models.corrida_model import CorridaCreate, CorridaResponse
from src.database.mongo_client import get_corridas_collection
from src.producer import get_producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TransFlow",
    description=(
        "Gerenciamento de corridas urbanas com MongoDB, Redis "
        "e mensageria assíncrona via RabbitMQ."
    ),
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    logger.info("Inicializando TransFlow")

    try:
        await get_producer()
        inicializar_saldos_exemplo()
        logger.info("TransFlow iniciada com sucesso")
    except Exception as e:
        logger.error(f"Erro ao iniciar serviços: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Encerrando TransFlow")
    try:
        producer = await get_producer()
        await producer.close()
    except Exception as e:
        logger.error(f"Erro ao encerrar producer: {e}")

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "TransFlow está funcionando!",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "corridas": "/corridas",
            "saldo": "/saldo/{motorista}"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }

    try:
        collection = get_corridas_collection()
        collection.find_one()
        health_status["services"]["mongodb"] = "healthy"
    except Exception as e:
        health_status["services"]["mongodb"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    try:
        redis_client.get_client().ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    try:
        producer = await get_producer()
        if producer.broker and getattr(producer.broker, "_connection", None):
            health_status["services"]["rabbitmq"] = "healthy"
        else:
            health_status["services"]["rabbitmq"] = "unhealthy: not connected"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["rabbitmq"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.post(
    "/corridas",
    response_model=CorridaResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Corridas"]
)
async def cadastrar_corrida(corrida: CorridaCreate):
    try:
        id_corrida = str(uuid.uuid4())[:8]
        data_criacao = datetime.now()

        corrida_data = corrida.model_dump()
        corrida_data["id_corrida"] = id_corrida
        corrida_data["data_criacao"] = data_criacao

        producer = await get_producer()
        await producer.publicar_corrida_finalizada(corrida_data)

        logger.info(
            f"Corrida {id_corrida} cadastrada - "
            f"Motorista: {corrida.motorista.nome} - "
            f"Valor: R$ {float(corrida.valor_corrida):.2f}"
        )

        return CorridaResponse(**corrida_data)

    except Exception as e:
        logger.error(f"Erro ao cadastrar corrida: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao cadastrar corrida: {str(e)}"
        )

@app.get(
    "/corridas",
    response_model=List[CorridaResponse],
    tags=["Corridas"]
)
async def listar_corridas():
    try:
        collection = get_corridas_collection()
        corridas = list(collection.find({}, {"_id": 0}))

        logger.info(f"Listando {len(corridas)} corridas")
        return corridas

    except Exception as e:
        logger.error(f"Erro ao listar corridas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar corridas: {str(e)}"
        )

@app.get(
    "/corridas/{forma_pagamento}",
    response_model=List[CorridaResponse],
    tags=["Corridas"]
)
async def filtrar_corridas_por_pagamento(forma_pagamento: str):
    try:
        collection = get_corridas_collection()
        corridas = list(
            collection.find(
                {"forma_pagamento": {"$regex": f"^{forma_pagamento}$", "$options": "i"}},
                {"_id": 0}
            )
        )

        logger.info(
            f"{len(corridas)} corridas com pagamento '{forma_pagamento}' retornadas"
        )
        return corridas

    except Exception as e:
        logger.error(f"Erro ao filtrar corridas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao filtrar corridas: {str(e)}"
        )

@app.get("/saldo/{motorista}", tags=["Saldo"])
async def consultar_saldo(motorista: str):
    try:
        saldo = redis_client.get_saldo(motorista)

        logger.info(f"Saldo de {motorista}: R$ {float(saldo):.2f}")

        return {
            "motorista": motorista,
            "saldo": saldo,
            "moeda": "BRL"
        }

    except Exception as e:
        logger.error(f"Erro ao consultar saldo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar saldo: {str(e)}"
        )

@app.put("/saldo/{motorista}", tags=["Saldo"])
async def definir_saldo(motorista: str, valor: float):
    try:
        if valor < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O saldo não pode ser negativo"
            )

        redis_client.set_saldo(motorista, valor)

        logger.info(f"Saldo de {motorista} definido para R$ {float(valor):.2f}")

        return {
            "motorista": motorista,
            "saldo": valor,
            "moeda": "BRL",
            "mensagem": "Saldo atualizado com sucesso"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao definir saldo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao definir saldo: {str(e)}"
        )

@app.delete("/corridas/{id_corrida}", tags=["Corridas"])
async def deletar_corrida(id_corrida: str):
    try:
        collection = get_corridas_collection()
        resultado = collection.delete_one({"id_corrida": id_corrida})

        if resultado.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Corrida {id_corrida} não encontrada"
            )

        logger.info(f"Corrida {id_corrida} deletada com sucesso")

        return {"mensagem": f"Corrida {id_corrida} deletada com sucesso"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar corrida: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar corrida: {str(e)}"
        )