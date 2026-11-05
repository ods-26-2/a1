"""Fake 6c producer: sends contract-validated events via configurable Kafka.

Replaces the I8 publisher and the B3 transport until they are integrated.

    python -m backend.fake_producer              # 4 eventos válidos
    python -m backend.fake_producer --fresh      # novas inspeções
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Trocamos a biblioteca paho-mqtt pelo confluent-kafka
from confluent_kafka import Producer

from .config import KafkaSettings
from .contracts import validate_piece_analysis

ROOT = Path(__file__).resolve().parents[1]
MOCKS_6C = ROOT / "shared" / "mocks" / "6c"
CANDIDATE_MOCKS = ROOT / "shared" / "mocks" / "kafka-1.1-candidate"
RESULT_ORDER = ("CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN")


def load_events(paths: list[Path]) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def default_events(include_invalid: bool, schema_version="1.1") -> list[dict[str, Any]]:
    directory = CANDIDATE_MOCKS if schema_version == "1.1" else MOCKS_6C / "valid"
    valid = load_events(sorted(directory.glob("i8-piece-*.json")))
    valid.sort(key=lambda event: RESULT_ORDER.index(event["payload"]["result"]))
    if include_invalid:
        invalid = CANDIDATE_MOCKS / "invalid" if schema_version == "1.1" else MOCKS_6C / "invalid"
        valid += load_events(sorted(invalid.glob("*.json")))
    return valid


def refresh(events: list[dict[str, Any]], *, clock=None) -> list[dict[str, Any]]:
    """Regenerate synthetic observations, preserving their relative fixture timings."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    session_id = str(uuid4())
    fresh = []
    for index, event in enumerate(events):
        event = copy.deepcopy(event)
        event["message_id"] = str(uuid4())
        event["session_id"] = session_id
        event["sequence"] = index

        # O campo schema deve manter a identificação do contrato 6c:
        # Do not repair invalid schemas/producers or missing times under --invalid.
        try:
            previous = datetime.fromisoformat(event["published_at"].replace("Z", "+00:00"))
            shift = clock().astimezone(timezone.utc) - previous
        except (KeyError, TypeError, AttributeError, ValueError):
            shift = None
        if shift is not None:
            for field in ("captured_at", "occurred_at", "published_at"):
                if field not in event:
                    continue
                try:
                    value = datetime.fromisoformat(event[field].replace("Z", "+00:00")) + shift
                    event[field] = value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                except (TypeError, AttributeError, ValueError):
                    pass
        fresh.append(event)
    return fresh


def publish_events(events, *, broker, topic, timeout=10.0, interval=0.0,
                   producer_factory=Producer, monotonic=time.monotonic):
    """Return only confirmed deliveries; queueing is not a delivery acknowledgment."""
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(interval) or interval < 0:
        raise ValueError("Timeout deve ser positivo; intervalo deve ser não negativo e finito")
    encoded = [json.dumps(event, allow_nan=False).encode("utf-8") for event in events]
    delivered = 0
    failures = []

    def delivery(error, message):
        nonlocal delivered
        if error is not None:
            failures.append(str(error))
        else:
            delivered += 1

    # Inicializa o produtor Kafka
    producer = producer_factory({
        'bootstrap.servers': broker,
        'message.timeout.ms': max(1, int(timeout * 1000)),
        'enable.idempotence': True,
    })
    try:
        for index, value in enumerate(encoded):
            if index and interval:
                time.sleep(interval)
            deadline = monotonic() + timeout
            while True:
                try:
                    # Publica no Kafka (assíncrono)
                    producer.produce(topic=topic, value=value, on_delivery=delivery)
                    break
                except BufferError:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise RuntimeError("Fila Kafka permaneceu cheia até o timeout")
                    producer.poll(min(0.1, remaining))
                    if failures:
                        raise RuntimeError("Falha de entrega Kafka: " + failures[0])
            # Força o envio imediato (poll)
            producer.poll(0)
            if failures:
                raise RuntimeError("Falha de entrega Kafka: " + failures[0])
    finally:
        # Garante que todas as mensagens saíram do buffer antes de encerrar o script
        remaining = producer.flush(timeout)
    if remaining or failures or delivered != len(events):
        raise RuntimeError(
            f"Entrega Kafka não confirmada: entregues={delivered}/{len(events)}, "
            f"pendentes={remaining}, erros={failures}"
        )
    return delivered


def main(argv: list[str] | None = None, *, producer_factory=Producer) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="eventos 6c em JSON")
    parser.add_argument("--fresh", action="store_true", help="gera novas inspeções sintéticas")
    parser.add_argument("--invalid", action="store_true", help="envia casos inválidos intencionalmente")
    parser.add_argument("--interval", type=float, default=0.0, help="segundos entre eventos")
    parser.add_argument("--schema-version", choices=("1.0", "1.1"), default="1.1")
    parser.add_argument("--delivery-timeout", type=float, default=10.0)

    # Atualizamos o default para apontar para o Kafka de testes B2
    # The environment selects B2; without it, the fallback is local only.
    parser.add_argument("--broker", default=os.getenv("KAFKA_BROKER_URL", KafkaSettings.broker_url))
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", KafkaSettings.topic))
    args = parser.parse_args(argv)
    try:
        events = load_events(args.files) if args.files else default_events(args.invalid, args.schema_version)
        if not events:
            raise ValueError("Nenhum evento encontrado para publicação")
        if args.fresh:
            events = refresh(events)
        if not args.invalid:
            for event in events:
                validate_piece_analysis(event, strict_publisher=True)
        if not args.broker.strip() or not args.topic.strip():
            raise ValueError("Broker e tópico devem ser preenchidos")
        print(f"A iniciar publicação de {len(events)} eventos Kafka para {args.broker}...")
        delivered = publish_events(events, broker=args.broker, topic=args.topic,
                                   timeout=args.delivery_timeout, interval=args.interval,
                                   producer_factory=producer_factory)
    except Exception as exc:
        print(f"Falha na publicação Kafka: {exc}", file=sys.stderr)
        return 1
    print(f"Entrega confirmada: {delivered} mensagens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
