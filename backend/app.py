"""HTTP API v1 of the A1 backend (docs/contratos/a1-api.md).

Run with: uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Callable, Literal

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, StringConstraints

from .config import Settings
from .db import apply_schema, open_pool, to_iso, utc_now
from .services import Services, build_services
from .mqtt_client import A1IngestionClient


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
    settings: Settings | None = None, *, clock: Callable[[], datetime] = utc_now
) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = open_pool(settings)
        mqtt_client = None
        try:
            apply_schema(pool)
            
            # Inicializa os serviços que lidam com a regra de negócio e banco de dados
            app.state.services = build_services(pool, clock)
            
            # Configuração e arranque do cliente MQTT em background
            # Utiliza o host 'mqtt-broker' no Docker, ou '127.0.0.1' se corrido localmente
            broker_url = os.environ.get("MQTT_BROKER_URL", "mqtt-broker")
            mqtt_client = A1IngestionClient(
                broker_url=broker_url,
                ingestion_service=app.state.services.ingestion
            )
            mqtt_client.start()
            
            yield
        finally:
            #Encerramento para não deixar threads presas (Clean teardown)
            if mqtt_client:
                mqtt_client.stop()
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
                    "detail": "Cliente MQTT A1 ligado e à escuta no tópico ods/i8/piece_analysis.",
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
