"""Gera o manifesto durável das evidências da atividade 31."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "docs/evidencias/atividade-31/manifesto.json"
FILES = [
    "docs/evidencias/atividade-31/browser-check.json",
    "docs/evidencias/atividade-31/capturas/01-historico-filtrado.png",
    "docs/evidencias/atividade-31/capturas/02-recorrencia.png",
    "docs/evidencias/atividade-31/capturas/03-inspecao-causa.png",
    "docs/evidencias/atividade-31/capturas/04-mobile-relatorio.png",
    "docs/evidencias/atividade-31/videos/demonstracao-frontend.mp4",
    "docs/evidencias/atividade-31/comandos.md",
    "docs/evidencias/atividade-29/resultado.json",
    "docs/evidencias/atividade-29/resumo.log",
    "docs/evidencias/atividade-30/resultado.json",
    "docs/evidencias/atividade-30/resumo.log",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    entries = []
    for name in FILES:
        path = ROOT / name
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(name)
        entries.append({"path": name, "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {
        "manifest_version": "1.0",
        "activity": 31,
        "recorded_on": "2026-11-06",
        "criterion": "Vídeos, capturas, logs e comandos publicados.",
        "criterion_source": {
            "filename": "plano_fechamento_sprint3_dependencias.pdf",
            "page": 5,
            "sha256": "883f4ad42f96d8bab38860e6bb288eb492ed28228aac407798b2d0527d12a460",
        },
        "status": "EVIDENCIAS_PUBLICADAS",
        "evidence_base_commit": "919ec22",
        "workflow_runs": {
            "regression": "https://github.com/ods-26-2/a1/actions/runs/42218589659",
            "metrics": "https://github.com/ods-26-2/a1/actions/runs/42219871217",
        },
        "files": entries,
        "limits": [
            "Vídeo e capturas usam API fake explícita e não persistente.",
            "Logs 29/30 provêm dos laboratórios Docker com PostgreSQL, Kafka, A1 e publisher I8 sintético.",
            "Inferência real, S4 real e P7 físico não são demonstrados."
        ],
    }
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
