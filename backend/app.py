"""HTTP API v1 of the A1 backend (docs/contratos/a1-api.md).

Run with: uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Callable, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, StringConstraints

from .config import Settings
from .db import apply_schema, open_pool, to_iso, utc_now
from .services import Services, build_services
from .kafka_client import A1KafkaConsumer


API_PREFIX = "/api/v1"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["CONFIRM", "SEND_TO_REVIEW"]
    operator: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], datetime] = utc_now
) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = open_pool(settings)
        kafka_consumer = None
        kafka_thread = None
        try:
            apply_schema(pool)
            
            app.state.services = build_services(pool, clock)
            
            # Instancia o consumidor passando o serviço do banco de dados já existente
            kafka_consumer = A1KafkaConsumer(ingestion_service=app.state.services.ingestion)
            
            # Executa o consumidor Kafka em uma thread separada para não bloquear o Uvicorn/FastAPI
            kafka_thread = threading.Thread(target=kafka_consumer.comecar_a_consumir, daemon=True)
            kafka_thread.start()
            
            yield
        finally:
            # Encerramento limpo e fecho da BD
            if kafka_consumer:
                kafka_consumer.parar() # Pode chamar o shutdown do Kafka aqui
            pool.close()

    app = FastAPI(title="A1 — API de inspeção", version="1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def services(request: Request) -> Services:
        return request.app.state.services

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(PoolTimeout)
    async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": "Banco de dados do A1 indisponível."}, status_code=503)

    @app.get(f"{API_PREFIX}/health")
    def health(request: Request) -> dict:
        try:
            services(request).repository.ping()
            database = {"name": "database", "status": "UP", "detail": "PostgreSQL acessível."}
        except (psycopg.Error, PoolTimeout) as exc:
            database = {
                "name": "database",
                "status": "DOWN",
                "detail": f"PostgreSQL inacessível: {type(exc).__name__}.",
            }
        return {
            "status": "ONLINE" if database["status"] == "UP" else "DEGRADED",
            "mode": "REAL",
            "checked_at": to_iso(clock()),
            "components": [
                {"name": "api-a1", "status": "UP", "detail": "Backend A1."},
                database,
                {
                    "name": "i8-subscriber",
                    "status": "UP",
                    "detail": "Cliente Kafka A1 ligado e à escuta no tópico ods.industria.defeito_classificado.",
                },
                {
                    "name": "s4",
                    "status": "DOWN",
                    "detail": "Adaptador S4 não implementado (S3-09); pedidos ficam pendentes.",
                },
            ],
        }   

    @app.get(f"{API_PREFIX}/inspections/current")
    def current_inspection(request: Request):
        view = services(request).inspections.current()
        if view is None:
            return Response(status_code=204)
        return view

    @app.get(f"{API_PREFIX}/inspections/{{inspection_id}}")
    def get_inspection(inspection_id: str, request: Request) -> dict:
        view = services(request).inspections.get(inspection_id)
        if view is None:
            raise HTTPException(404, f"Inspeção {inspection_id} não encontrada.")
        return view

    @app.get(f"{API_PREFIX}/inspections/{{inspection_id}}/history")
    def inspection_history(inspection_id: str, request: Request) -> dict:
        history = services(request).inspections.history(inspection_id)
        if history is None:
            raise HTTPException(404, f"Inspeção {inspection_id} não encontrada.")
        return history

    @app.post(f"{API_PREFIX}/inspections/{{inspection_id}}/reviews", status_code=201)
    def submit_review(inspection_id: str, body: ReviewRequest, request: Request) -> dict:
        receipt = services(request).reviews.submit(
            inspection_id, action=body.action, operator=body.operator
        )
        if receipt is None:
            raise HTTPException(404, f"Inspeção {inspection_id} não encontrada.")
        return receipt

    return app