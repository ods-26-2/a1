"""Validation at the versioned I8 -> A1 contract boundary.

The A1 consumer supports the legacy ``ods.i8.piece_analysis`` 1.0 contract
during migration and the final ``ods.industria.defeito_classificado`` 2.0
contract. Publication validation remains strict for both interfaces.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas" / "6c"
LEGACY_PAYLOAD_FIELDS = frozenset(
    {"piece_id", "classification", "evidence", "status", "consequence", "image_url"}
)
LEGACY_CONTRACT = ("ods.i8.piece_analysis", "1.0")
FINAL_CONTRACT = ("ods.industria.defeito_classificado", "2.0")


class ContractValidationError(ValueError):
    """Raised when a message cannot cross the I8 -> A1 boundary."""


def _load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def _format_error(error: Any) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "$"
    return f"{location}: {error.message}"


def _validate_uuid4(value: str, field: str) -> None:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ContractValidationError(f"{field}: UUID inválido") from exc
    if parsed.version != 4:
        raise ContractValidationError(f"{field}: deve ser UUID v4")


def validate_piece_analysis(
    event: Mapping[str, Any], *, strict_publisher: bool = False
) -> dict[str, Any]:
    """Validate one of the two explicitly supported I8 -> A1 interfaces."""

    if not isinstance(event, Mapping):
        raise ContractValidationError("$: evento deve ser um objeto")
    contract = (event.get("schema"), event.get("schema_version"))
    if contract == LEGACY_CONTRACT:
        schema_name = (
            "i8-piece-analysis.publish.schema.json"
            if strict_publisher
            else "i8-piece-analysis.consume.schema.json"
        )
    elif contract == FINAL_CONTRACT:
        schema_name = "i8-defeito-classificado.publish.2.0.schema.json"
    else:
        raise ContractValidationError(
            "schema/schema_version: contrato não suportado; use "
            "ods.i8.piece_analysis 1.0 ou "
            "ods.industria.defeito_classificado 2.0"
        )
    validator = Draft202012Validator(
        _load_schema(schema_name), format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(event), key=lambda item: list(item.path))
    if errors:
        raise ContractValidationError(_format_error(errors[0]))

    # JSON Schema date-time checking can be unavailable without optional extras.
    # Keep impossible dates and non-finite Python numbers out of the runtime gate.
    for field in ("captured_at", "published_at", "occurred_at"):
        if field in event:
            try:
                datetime.strptime(event[field], "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError as exc:
                raise ContractValidationError(f"{field}: data/hora inválida") from exc
    for field in ("confidence", "similarity"):
        if not math.isfinite(event["payload"][field]):
            raise ContractValidationError(f"payload.{field}: deve ser finito")

    _validate_uuid4(str(event["message_id"]), "message_id")
    _validate_uuid4(str(event["session_id"]), "session_id")
    if "correlation_id" in event:
        _validate_uuid4(str(event["correlation_id"]), "correlation_id")

    payload = event["payload"]
    legacy = LEGACY_PAYLOAD_FIELDS.intersection(payload)
    if legacy:
        raise ContractValidationError(
            "payload: campos legados proibidos: " + ", ".join(sorted(legacy))
        )

    x_min, y_min, x_max, y_max = payload["bbox"]
    if x_min >= x_max or y_min >= y_max:
        raise ContractValidationError("payload.bbox: a caixa deve ter área positiva")

    return dict(event)

