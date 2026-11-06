"""HTTP API v1 of the A1 backend (docs/contratos/a1-api.md).

Run with: uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import asyncio
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Callable, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, StringConstraints

from .config import KafkaSettings, Settings
from .db import apply_schema, open_pool, to_iso, utc_now
from .services import Services, build_services
from .kafka_client import A1KafkaConsumer
from .s4_kafka import S4KafkaWorker


API_PREFIX = "/api/v1"


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["CONFIRM", "SEND_TO_REVIEW", "CORRECT"]
    operator: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
    ]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    status: Literal["APPROVED", "REJECTED", "REVIEW"] | None = None
    defect_class: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], datetime] = utc_now,
    consumer_factory=None, s4_factory=None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    kafka_settings = KafkaSettings.from_env()
    s4_flag = os.getenv("S4_ENABLED", "0").strip().lower()
    if s4_flag not in {"0", "1", "false", "true"}:
        raise ValueError("S4_ENABLED deve ser 0/1/false/true")
    s4_enabled = s4_flag in {"1", "true"}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = open_pool(settings)
        kafka_consumer = None
        kafka_thread = None
        kafka_started = False
        s4_worker = s4_thread = None
        try:
            apply_schema(pool)
            
            app.state.services = build_services(pool, clock)
            
            # Instancia o consumidor passando o serviço do banco de dados já existente
            kafka_consumer = (consumer_factory or A1KafkaConsumer)(
                ingestion_service=app.state.services.ingestion,
                settings=kafka_settings,
            )
            app.state.kafka_consumer = kafka_consumer
            
            # Executa o consumidor Kafka em uma thread separada para não bloquear o Uvicorn/FastAPI
            kafka_thread = threading.Thread(target=kafka_consumer.comecar_a_consumir, daemon=True)
            kafka_thread.start()
            kafka_started = True
            
            if s4_enabled:
                s4_worker = (s4_factory or S4KafkaWorker)(app.state.services.s4, kafka_settings.broker_url)
                s4_thread = threading.Thread(target=s4_worker.run, daemon=True)
                app.state.s4_worker = s4_worker
                s4_thread.start()
            yield
        finally:
            # Encerramento limpo e fecho da BD
            if s4_worker:
                s4_worker.parar()
            if kafka_consumer:
                kafka_consumer.parar() # Pode chamar o shutdown do Kafka aqui
            if s4_thread:
                await asyncio.to_thread(s4_thread.join, kafka_settings.shutdown_timeout)
                if s4_thread.is_alive():
                    raise RuntimeError("Adaptador S4 não encerrou; pool mantido aberto para persistência em andamento.")
            if kafka_started:
                await asyncio.to_thread(
                    kafka_thread.join, kafka_settings.shutdown_timeout
                )
                if kafka_thread.is_alive():
                    raise RuntimeError(
                        "Consumidor Kafka não encerrou no prazo; pool mantido aberto "
                        "para não interromper persistência em andamento."
                    )
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
        subscriber = request.app.state.kafka_consumer.health_snapshot()
        s4 = (request.app.state.s4_worker.health_snapshot() if s4_enabled else {
            "name": "s4", "status": "DOWN",
            "detail": "Adaptador S4 desativado; habilitação explícita por S4_ENABLED=1.",
        })
        return {
            "status": "ONLINE" if database["status"] == "UP" and subscriber["status"] == "UP" and (not s4_enabled or s4["status"] == "UP") else "DEGRADED",
            "mode": "REAL",
            "checked_at": to_iso(clock()),
            "components": [
                {"name": "api-a1", "status": "UP", "detail": "Backend A1."},
                database,
                subscriber,
                s4,
            ],
        }   

    @app.get(f"{API_PREFIX}/inspections/current")
    def current_inspection(request: Request):
        view = services(request).inspections.current()
        if view is None:
            return Response(status_code=204)
        return view

    @app.get(f"{API_PREFIX}/inspections/review-queue")
    def review_queue(request: Request, limit: Annotated[int, Query(ge=1, le=100)] = 50,
                     offset: Annotated[int, Query(ge=0)] = 0) -> dict:
        return services(request).inspections.queue(limit=limit, offset=offset)

    @app.get(f"{API_PREFIX}/inspections/{{inspection_id}}/review-options")
    def review_options(inspection_id: str, request: Request) -> dict:
        options = services(request).inspections.review_options(inspection_id)
        if options is None:
            raise HTTPException(404, "Inspeção não encontrada.")
        return options

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
        try:
            receipt = services(request).reviews.submit(inspection_id, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if receipt is None:
            raise HTTPException(404, f"Inspeção {inspection_id} não encontrada.")
        return receipt

    return app
