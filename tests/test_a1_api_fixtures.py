"""Consistência das fixtures da API A1 fake usadas pelo frontend (S3-03).

Cada InspectionView precisa ser válida pelo schema da API, derivar de um evento
6c válido, resolver rótulos pela versão de taxonomia registrada e seguir a
política mínima da seção 7.2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from backend.contracts import validate_piece_analysis
from backend.taxonomy import TaxonomyCatalog


ROOT = Path(__file__).resolve().parents[1]
API_SCHEMAS = ROOT / "shared" / "schemas" / "a1-api"
FIXTURES = ROOT / "shared" / "mocks" / "a1-api" / "inspections"
EVENTS_6C = ROOT / "shared" / "mocks" / "6c" / "valid"
POLICY_DIR = ROOT / "shared" / "policies" / "triage"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(name: str) -> Draft202012Validator:
    schemas = {path.name: _load(path) for path in API_SCHEMAS.glob("*.json")}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    return Draft202012Validator(
        schemas[name], registry=registry, format_checker=FormatChecker()
    )


FIXTURE_PATHS = sorted(FIXTURES.glob("*.json"))
EVENTS_BY_ID = {
    event["message_id"]: event for event in map(_load, EVENTS_6C.glob("*.json"))
}


def _policy(version: str) -> dict:
    for path in POLICY_DIR.glob("*.json"):
        policy = _load(path)
        if policy["policy_version"] == version:
            return policy
    raise AssertionError(f"política {version} não encontrada")


def _expected_status(view: dict) -> str:
    """Política mínima 7.2, usada como oráculo até o TriageService (S3-08)."""

    result = view["analysis"]["result"]
    if result == "CONFORMING":
        return "APPROVED"
    if result == "NON_CONFORMING":
        policy = _policy(view["versions"]["policy"])
        defect_class = view["analysis"]["defect"]["defect_class"]
        for consequence in policy["consequences"]:
            if consequence["defect_class"] == defect_class:
                return consequence["status"]
        return policy["default_status"]
    return "REVIEW"


def test_fixtures_cover_four_results_and_three_statuses():
    views = [_load(path) for path in FIXTURE_PATHS]

    assert sorted(view["analysis"]["result"] for view in views) == [
        "ANOMALY",
        "CONFORMING",
        "NON_CONFORMING",
        "UNCERTAIN",
    ]
    assert {view["triage"]["status"] for view in views} == {
        "APPROVED",
        "REJECTED",
        "REVIEW",
    }


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_fixture_matches_api_schema(path: Path):
    errors = list(_validator("inspection-view.schema.json").iter_errors(_load(path)))
    assert errors == []


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_fixture_derives_from_valid_6c_event(path: Path):
    view = _load(path)
    event = EVENTS_BY_ID[view["origin"]["message_id"]]
    validate_piece_analysis(event, strict_publisher=True)
    payload = event["payload"]
    origin = view["origin"]

    for field in ("schema", "schema_version", "producer", "source_id", "session_id", "sequence"):
        assert origin[field] == event[field]
    for field in ("frame_index", "detection_id", "bbox"):
        assert origin[field] == payload[field]
    assert view["times"]["captured_at"] == event["captured_at"]
    assert view["times"]["published_at"] == event["published_at"]
    assert view["versions"]["model"] == event["artifact_version"]
    assert view["versions"]["taxonomy"] == payload["taxonomy_version"]
    for field in ("result", "confidence", "similarity"):
        assert view["analysis"][field] == payload[field]


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_fixture_labels_and_decision_follow_versions(path: Path):
    view = _load(path)
    defect = view["analysis"]["defect"]

    if defect is not None:
        label = TaxonomyCatalog().resolve(view["versions"]["taxonomy"], defect["defect_class"])
        assert defect == label
    policy = _policy(view["versions"]["policy"])
    assert policy["taxonomy_version"] == view["versions"]["taxonomy"]
    assert view["triage"]["status"] == _expected_status(view)
    assert view["triage"]["decided_by"] == "AUTO"
    assert view["final_decision"] is None


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda path: path.stem)
def test_evidence_never_falls_back_to_another_piece(path: Path):
    evidence = _load(path)["evidence"]

    if evidence["state"] == "AVAILABLE":
        assert (ROOT / evidence["url"]).is_file()
    else:
        assert evidence["url"] is None


def test_review_receipt_embeds_inspection_view():
    view = _load(FIXTURES / "non-conforming.json")
    receipt = {
        "review_id": "rev-1",
        "action": "SEND_TO_REVIEW",
        "recorded_at": "2026-10-20T12:05:00.000Z",
        "persisted": True,
        "inspection": {
            **view,
            "final_decision": {
                "status": "REVIEW",
                "reason": "Encaminhada para revisão pelo operador.",
                "decided_by": "op-1",
                "decided_at": "2026-10-20T12:05:00.000Z",
            },
        },
    }

    assert list(_validator("review-receipt.schema.json").iter_errors(receipt)) == []
    receipt["inspection"]["analysis"]["result"] = "APPROVED"
    assert list(_validator("review-receipt.schema.json").iter_errors(receipt)) != []
