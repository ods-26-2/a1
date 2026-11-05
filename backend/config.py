"""Runtime settings of the A1 backend, read from environment variables."""

from __future__ import annotations

import os
import math
from dataclasses import dataclass


DEFAULT_CORS_ORIGINS = ("http://localhost:5500", "http://127.0.0.1:5500")


@dataclass(frozen=True)
class KafkaSettings:
    broker_url: str = "localhost:9092"
    topic: str = "ods.industria.defeito_classificado"
    group_id: str = "VER-1-A1-Consumer"
    poll_timeout: float = 1.0
    retry_attempts: int = 5
    retry_initial: float = 0.25
    retry_max: float = 4.0
    health_interval: float = 10.0
    health_timeout: float = 2.0
    shutdown_timeout: float = 15.0

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.broker_url, self.topic, self.group_id)):
            raise ValueError("Broker, tópico e grupo Kafka devem ser preenchidos")
        if type(self.retry_attempts) is not int or not 1 <= self.retry_attempts <= 10:
            raise ValueError("KAFKA_RETRY_ATTEMPTS deve estar entre 1 e 10")
        for value in (self.poll_timeout, self.retry_initial, self.retry_max,
                      self.health_interval, self.health_timeout, self.shutdown_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("Tempos Kafka devem ser positivos e finitos")
        if self.retry_initial > self.retry_max or self.retry_max > 10:
            raise ValueError("Retry Kafka deve satisfazer initial <= max <= 10 segundos")

    @classmethod
    def from_env(cls):
        return cls(
            broker_url=os.getenv("KAFKA_BROKER_URL", cls.broker_url).strip(),
            topic=os.getenv("KAFKA_TOPIC", cls.topic).strip(),
            group_id=os.getenv("KAFKA_GROUP_ID", cls.group_id).strip(),
            retry_attempts=int(os.getenv("KAFKA_RETRY_ATTEMPTS", cls.retry_attempts)),
            retry_initial=float(os.getenv("KAFKA_RETRY_INITIAL", cls.retry_initial)),
            retry_max=float(os.getenv("KAFKA_RETRY_MAX", cls.retry_max)),
            shutdown_timeout=float(os.getenv("KAFKA_SHUTDOWN_TIMEOUT", cls.shutdown_timeout)),
        )


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
