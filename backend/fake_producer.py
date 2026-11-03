"""Fake 6c producer: sends ods.i8.piece_analysis events into A1 ingestion.

Replaces the I8 publisher and the B3 transport until they are integrated.

    python -m backend.fake_producer              # 4 eventos válidos das fixtures
    python -m backend.fake_producer --fresh      # mesmos resultados, novas inspeções
    python -m backend.fake_producer --invalid    # inclui eventos que devem ser recusados
    python -m backend.fake_producer arquivo.json # eventos de arquivos próprios
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

from .config import Settings
from .db import apply_schema, open_pool, to_iso, utc_now
from .services import build_services


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
    """New message_id, session and timestamps: each run creates new inspections."""

    session_id = str(uuid4())
    start = utc_now()
    fresh = []
    for index, event in enumerate(events):
        event = copy.deepcopy(event)
        captured = start + timedelta(seconds=index)
        event["message_id"] = str(uuid4())
        event["session_id"] = session_id
        event["sequence"] = index
        event["captured_at"] = to_iso(captured)
        event["published_at"] = to_iso(captured + timedelta(milliseconds=120))
        if isinstance(event.get("payload"), dict):
            event["payload"]["frame_index"] = index
        fresh.append(event)
    return fresh


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="eventos 6c em JSON")
    parser.add_argument("--fresh", action="store_true", help="gera novas inspeções")
    parser.add_argument("--invalid", action="store_true", help="inclui fixtures inválidas")
    parser.add_argument("--interval", type=float, default=0.0, help="segundos entre eventos")
    args = parser.parse_args(argv)

    events = load_events(args.files) if args.files else default_events(args.invalid)
    if args.fresh:
        events = refresh(events)

    pool = open_pool(Settings.from_env())
    try:
        apply_schema(pool)
        ingestion = build_services(pool).ingestion
        for index, event in enumerate(events):
            if index and args.interval:
                time.sleep(args.interval)
            result = ingestion.ingest(event)
            label = result.inspection_id or result.reason
            print(f"{result.status.value:<9} {event.get('message_id')} {label}")
    finally:
        pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
