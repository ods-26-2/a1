"""Consolida latência, memória de containers e ambiente da atividade 30."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


UNITS = {"B": 1, "kB": 1000, "KB": 1000, "KiB": 1024, "MB": 1000**2,
         "MiB": 1024**2, "GB": 1000**3, "GiB": 1024**3}


def memory_mib(value: str) -> float:
    used = value.split("/", 1)[0].strip()
    match = re.fullmatch(r"([0-9.]+)\s*([A-Za-z]+)", used)
    if not match or match.group(2) not in UNITS:
        raise ValueError(f"memória Docker inválida: {value!r}")
    return round(float(match.group(1)) * UNITS[match.group(2)] / 1024**2, 3)


def key_values(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            result[key] = value
    return result


def json_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        value = json.loads(line)
        records.extend(value if isinstance(value, list) else [value])
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latency", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    latency = json.loads(args.latency.read_text(encoding="utf-8"))
    stats = json_records(args.stats)
    if len(stats) < 4:
        raise ValueError("snapshot deve conter db, Kafka, backend e frontend")
    containers = [{
        "name": item["Name"],
        "memory_used_mib": memory_mib(item["MemUsage"]),
        "memory_percent": item.get("MemPerc"),
        "cpu_percent_snapshot": item.get("CPUPerc"),
        "pids": int(item["PIDs"]) if str(item.get("PIDs", "")).isdigit() else item.get("PIDs"),
    } for item in sorted(stats, key=lambda item: item["Name"])]
    environment = key_values(args.environment)
    result = {
        "activity": 30,
        "status": "MEDICAO_LOCAL_REGISTRADA",
        "recorded_at": environment["recorded_at"],
        "a1_commit": environment["a1_commit"],
        "i8_commit": environment["i8_commit"],
        "latency": latency,
        "resources": {
            "snapshot": "após regressão, reinício e 30 leituras da API",
            "containers": containers,
            "total_memory_used_mib": round(sum(item["memory_used_mib"] for item in containers), 3),
        },
        "environment": environment,
        "images": json_records(args.images),
        "limits": [
            "Medição local sintética; inferência real da atividade 18 permanece bloqueada.",
            "Memória e CPU são um snapshot, não pico nem teste de carga.",
            "Runner GitHub compartilhado e quatro eventos não representam hardware industrial."
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
