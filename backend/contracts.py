"""Validation at the I8 -> A1 contract boundary.

The publisher schema is deliberately strict for schema version 1.0.  The
consumer schema accepts additive fields from future 1.x versions while still
rejecting fields from the pre-6c contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "shared" / "schemas" / "6c"
LEGACY_PAYLOAD_FIELDS = frozenset(
    {"piece_id", "classification", "evidence", "status", "consequence", "image_url"}
)


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
    """Validate an ``ods.i8.piece_analysis`` event received by A1.

    ``strict_publisher=True`` applies the exact producer contract for version
    1.0.  The default is the A1 consumer gate: it accepts additive 1.x changes
    but never accepts the old ``ods.ver1`` payload vocabulary.
    """

    schema_name = (
        "i8-piece-analysis.publish.schema.json"
        if strict_publisher
        else "i8-piece-analysis.consume.schema.json"
    )
    validator = Draft202012Validator(
        _load_schema(schema_name), format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(event), key=lambda item: list(item.path))
    if errors:
        raise ContractValidationError(_format_error(errors[0]))

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

