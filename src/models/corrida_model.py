from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Passageiro(BaseModel):
    nome: str
    telefone: str

class Motorista(BaseModel):
    nome: str
    nota: float = Field(..., ge=0, le=5)

class CorridaBase(BaseModel):
    passageiro: Passageiro
    motorista: Motorista
    origem: str
    destino: str
    valor_corrida: float = Field(..., gt=0)
    forma_pagamento: str

class CorridaCreate(CorridaBase):
    pass

class Corrida(CorridaBase):
    id_corrida: str
    data_criacao: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id_corrida": "abc123",
                "passageiro": {
                    "nome": "João",
                    "telefone": "99999-1111"
                },
                "motorista": {
                    "nome": "Carla",
                    "nota": 4.8
                },
                "origem": "Centro",
                "destino": "Inoã",
                "valor_corrida": 35.50,
                "forma_pagamento": "DigitalCoin",
                "data_criacao": "2025-11-16T10:30:00"
            }
        }

class CorridaResponse(Corrida):
    pass
