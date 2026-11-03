"""Fixtures do backend A1 com PostgreSQL real (S3-07).

Os testes de banco rodam quando A1_TEST_DATABASE_URL aponta para um PostgreSQL
(no compose: docker compose run --rm tests). Cada teste usa um schema próprio,
removido no final, então o banco da aplicação não é tocado.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
API_SCHEMAS = ROOT / "shared" / "schemas" / "a1-api"
EVENTS_6C = ROOT / "shared" / "mocks" / "6c"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def api_validator(name: str) -> Draft202012Validator:
    schemas = {path.name: load_json(path) for path in API_SCHEMAS.glob("*.json")}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    return Draft202012Validator(
        schemas[name], registry=registry, format_checker=FormatChecker()
    )


def valid_events() -> dict[str, dict]:
    events = map(load_json, sorted((EVENTS_6C / "valid").glob("*.json")))
    return {event["payload"]["result"]: event for event in events}


def invalid_events() -> list[dict]:
    return [load_json(path) for path in sorted((EVENTS_6C / "invalid").glob("*.json"))]


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("A1_TEST_DATABASE_URL")
    if not url:
        pytest.skip("A1_TEST_DATABASE_URL não definida (rode no compose)")
    return url


@pytest.fixture
def settings(database_url):
    psycopg = pytest.importorskip("psycopg")
    from backend.config import Settings

    schema = f"test_{uuid4().hex[:12]}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
    try:
        yield Settings(database_url=database_url, search_path=schema)
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture
def client(settings):
    from fastapi.testclient import TestClient

    from backend.app import create_app

    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def ingest(client):
    return client.app.state.services.ingestion.ingest


@pytest.fixture
def sql(settings):
    """Executa SQL direto no schema do teste (verificação de persistência)."""

    import psycopg

    def run(query: str, params=()):
        with psycopg.connect(
            settings.database_url,
            autocommit=True,
            options=f"-c search_path={settings.search_path}",
        ) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall() if cursor.description else None

    return run
