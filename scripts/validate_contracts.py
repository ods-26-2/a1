"""Validate the local S3-01/S3-02 package without starting the frontend."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.contracts import ContractValidationError, validate_piece_analysis
from backend.taxonomy import TaxonomyCatalog


def main() -> int:
    valid_dir = ROOT / "shared" / "mocks" / "6c" / "valid"
    invalid_dir = ROOT / "shared" / "mocks" / "6c" / "invalid"

    for path in sorted(valid_dir.glob("i8-piece-*.json")):
        validate_piece_analysis(json.loads(path.read_text(encoding="utf-8")))

    for path in sorted(invalid_dir.glob("i8-piece-*.json")):
        try:
            validate_piece_analysis(json.loads(path.read_text(encoding="utf-8")))
        except ContractValidationError:
            continue
        raise RuntimeError(f"fixture inválida foi aceita: {path.name}")

    taxonomy = TaxonomyCatalog().load("defects-a1-1.0.0")
    print(
        f"Contratos 6c válidos: 4 resultados; taxonomia {taxonomy.version}; "
        f"{len(taxonomy.classes)} classes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

