"""Runtime settings of the A1 backend, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_CORS_ORIGINS = ("http://localhost:5500", "http://127.0.0.1:5500")


@dataclass(frozen=True)
class Settings:
    database_url: str
    search_path: str | None = None
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("DATABASE_URL não definida para o backend A1")
        origins = os.environ.get("A1_CORS_ORIGINS")
        return cls(
            database_url=database_url,
            cors_origins=(
                tuple(item.strip() for item in origins.split(",") if item.strip())
                if origins is not None
                else DEFAULT_CORS_ORIGINS
            ),
        )
