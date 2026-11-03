"""PostgreSQL connection pool and schema bootstrap."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import Settings


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
# Serializa a criação do esquema quando mais de um processo inicia junto.
SCHEMA_LOCK_ID = 7_301_007


def open_pool(settings: Settings, *, timeout: float = 30.0) -> ConnectionPool:
    kwargs: dict = {"row_factory": dict_row}
    if settings.search_path:
        kwargs["options"] = f"-c search_path={settings.search_path}"
    pool = ConnectionPool(
        settings.database_url, kwargs=kwargs, min_size=1, max_size=5, open=True
    )
    pool.wait(timeout=timeout)
    return pool


def apply_schema(pool: ConnectionPool) -> None:
    with pool.connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))
        conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime) -> str:
    """Format timestamps like the 6c contract: UTC with milliseconds and Z."""

    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
