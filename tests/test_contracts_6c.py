from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from backend.contracts import ContractValidationError, validate_piece_analysis


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "shared" / "schemas" / "6c"
VALID = ROOT / "shared" / "mocks" / "6c" / "valid"
INVALID = ROOT / "shared" / "mocks" / "6c" / "invalid"
ARTIFACT = (
    ROOT
    / "shared"
    / "artifacts"
    / "defect-taxonomy"
    / "defects-a1-1.0.0"
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", sorted(VALID.glob("i8-piece-*.json")))
def test_four_results_pass_publisher_and_consumer(path: Path):
    event = read_json(path)
    assert validate_piece_analysis(event, strict_publisher=True)["payload"]["result"]
    assert validate_piece_analysis(event)["payload"]["result"]


@pytest.mark.parametrize("path", sorted(INVALID.glob("i8-piece-*.json")))
def test_invalid_examples_are_rejected(path: Path):
    with pytest.raises(ContractValidationError):
        validate_piece_analysis(read_json(path))


def test_final_2_0_passes_publisher_and_consumer_gates():
    event = read_json(ROOT / "shared/mocks/kafka-2.0/i8-piece-conforming.json")
    assert validate_piece_analysis(event) == event
    assert validate_piece_analysis(event, strict_publisher=True) == event


@pytest.mark.parametrize(
    ("schema", "version"),
    [
        ("ods.i8.piece_analysis", "1.1"),
        ("ods.i8.piece_analysis", "2.0"),
        ("ods.industria.defeito_classificado", "1.0"),
        ("ods.industria.defeito_classificado", "2.1"),
    ],
)
def test_only_explicit_legacy_and_final_contract_pairs_are_accepted(schema, version):
    event = read_json(VALID / "i8-piece-conforming.json")
    event["schema"] = schema
    event["schema_version"] = version
    event["occurred_at"] = event["published_at"]
    with pytest.raises(ContractValidationError, match="contrato não suportado"):
        validate_piece_analysis(event)


def test_consumer_rejects_unknown_major_and_zero_area_bbox():
    event = read_json(VALID / "i8-piece-conforming.json")
    other_major = copy.deepcopy(event)
    other_major["schema_version"] = "3.0"
    with pytest.raises(ContractValidationError):
        validate_piece_analysis(other_major)

    event["payload"]["bbox"] = [10, 20, 10, 30]
    with pytest.raises(ContractValidationError, match="área positiva"):
        validate_piece_analysis(event)


@pytest.mark.parametrize(
    ("schema_file", "document_file"),
    [
        ("artifact-descriptor.schema.json", "descriptor.json"),
        ("artifact-published.schema.json", "published.json"),
    ],
)
def test_artifact_descriptor_and_announcement_validate(schema_file, document_file):
    schema = read_json(SCHEMAS / schema_file)
    document = read_json(ARTIFACT / document_file)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)


def test_announcement_payload_is_the_exact_descriptor():
    descriptor = read_json(ARTIFACT / "descriptor.json")
    published = read_json(ARTIFACT / "published.json")
    assert published["payload"] == descriptor

