"""Verifica hashes, formatos e resultado visual da atividade 31."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/evidencias/atividade-31/manifesto.json"))
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    if manifest.get("status") != "EVIDENCIAS_PUBLICADAS":
        raise ValueError("status da atividade 31 não aprovado")
    for entry in manifest["files"]:
        path = root / entry["path"]
        if path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError(f"evidência divergente: {entry['path']}")
        if path.suffix == ".png" and not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"PNG inválido: {entry['path']}")
        if path.suffix == ".mp4" and b"ftyp" not in path.read_bytes()[:64]:
            raise ValueError(f"MP4 inválido: {entry['path']}")
    browser = json.loads((root / "docs/evidencias/atividade-31/browser-check.json").read_text(encoding="utf-8"))
    if browser.get("browser_errors") or len(browser.get("checks", [])) < 6:
        raise ValueError("aceite visual incompleto")
    print(f"Atividade 31 válida: {len(manifest['files'])} arquivos com hash confirmado.")


if __name__ == "__main__":
    main()
