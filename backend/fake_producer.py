"""Fake 6c producer: sends ods.i8.piece_analysis events via MQTT.

Replaces the I8 publisher and the B3 transport until they are integrated.

    python -m backend.fake_producer              # 4 eventos válidos
    python -m backend.fake_producer --fresh      # novas inspeções
"""

from __future__ import annotations

import argparse
import copy
import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import paho.mqtt.publish as publish

ROOT = Path(__file__).resolve().parents[1]
MOCKS_6C = ROOT / "shared" / "mocks" / "6c"
RESULT_ORDER = ("CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN")

def load_events(paths: list[Path]) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]

def default_events(include_invalid: bool) -> list[dict[str, Any]]:
    valid = load_events(sorted((MOCKS_6C / "valid").glob("*.json")))
    valid.sort(key=lambda event: RESULT_ORDER.index(event["payload"]["result"]))
    if include_invalid:
        valid += load_events(sorted((MOCKS_6C / "invalid").glob("*.json")))
    return valid

def refresh(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    session_id = str(uuid4())
    start = time.time()
    fresh = []
    for index, event in enumerate(events):
        event = copy.deepcopy(event)
        event["message_id"] = str(uuid4())
        event["session_id"] = session_id
        event["sequence"] = index
        fresh.append(event)
    return fresh

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="eventos 6c em JSON")
    parser.add_argument("--fresh", action="store_true", help="gera novas inspeções")
    parser.add_argument("--invalid", action="store_true", help="inclui fixtures inválidas")
    parser.add_argument("--interval", type=float, default=0.0, help="segundos entre eventos")
    parser.add_argument("--broker", type=str, default="127.0.0.1", help="Endereço do broker MQTT")
    args = parser.parse_args(argv)

    events = load_events(args.files) if args.files else default_events(args.invalid)
    if args.fresh:
        events = refresh(events)

    print(f"A iniciar publicação de {len(events)} eventos MQTT para {args.broker}:1883...")
    
    for index, event in enumerate(events):
        if index and args.interval:
            time.sleep(args.interval)
        
        # Publica no broker com QoS 1
        publish.single(
            topic="ods/i8/piece_analysis",
            payload=json.dumps(event).encode("utf-8"),
            hostname=args.broker,
            port=1883,
            qos=1
        )
        print(f"Publicado MQTT: {event.get('payload', {}).get('result', 'INVALID'):<15} ID: {event.get('message_id')}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())