"""Mede o pipeline local da atividade 30 a partir de observações persistidas."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from statistics import median
import time
from urllib.request import urlopen

import psycopg


EVIDENCE = Path("/evidencias")


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999999) - 1))
    return ordered[index]


def summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("nenhuma amostra")
    return {
        "samples": len(values),
        "min": round(min(values), 3),
        "p50": round(median(values), 3),
        "p95_nearest_rank": round(nearest_rank(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-samples", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.api_samples <= 200:
        raise ValueError("api-samples deve ficar entre 1 e 200")

    invocation_ns = int((EVIDENCE / "envio-inicio-ns.txt").read_text().strip())
    completion_ns = int((EVIDENCE / "envio-fim-ns.txt").read_text().strip())
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        rows = connection.execute(
            "SELECT message_id::text, received_at, raw_event FROM inspections ORDER BY received_at, message_id"
        ).fetchall()
    if len(rows) != 4:
        raise ValueError(f"esperadas 4 inspeções; recebidas {len(rows)}")

    invocation_to_database = []
    marker_to_database = []
    observations = []
    for message_id, received_at, event in rows:
        observed_ms = (int(received_at.timestamp() * 1_000_000_000) - invocation_ns) / 1_000_000
        marker_ms = (received_at - iso(event["published_at"])).total_seconds() * 1000
        if observed_ms < 0 or marker_ms < 0:
            raise ValueError("relógios produziram latência negativa")
        invocation_to_database.append(observed_ms)
        marker_to_database.append(marker_ms)
        observations.append({
            "message_id": message_id,
            "result": event["payload"]["result"],
            "publisher_invocation_to_database_ms": round(observed_ms, 3),
            "synthetic_published_marker_to_database_ms": round(marker_ms, 3),
        })

    api_samples = []
    api_url = os.environ["API_URL"].rstrip("/") + "/inspections?limit=100&offset=0"
    for _ in range(args.api_samples):
        started = time.perf_counter_ns()
        with urlopen(api_url, timeout=5) as response:
            body = json.load(response)
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if response.status != 200 or body.get("total") != 4:
            raise ValueError("API não retornou as quatro inspeções")
        api_samples.append(elapsed)

    result = {
        "status": "MEDICAO_LOCAL_REGISTRADA",
        "pipeline": "início do comando publisher I8 -> persistência PostgreSQL pelo A1",
        "publisher_command_ms": round((completion_ns - invocation_ns) / 1_000_000, 3),
        "publisher_invocation_to_database_ms": summary(invocation_to_database),
        "synthetic_published_marker_to_database_ms": summary(marker_to_database),
        "api_history_request_ms": summary(api_samples),
        "observations": observations,
        "limits": [
            "Eventos sintéticos; tempo de inferência de imagem não incluído.",
            "Quatro eventos, uma partição Kafka e um runner compartilhado não representam carga industrial.",
            "O marcador published_at é sintético; a métrica principal usa o relógio observado no início do comando publisher."
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
