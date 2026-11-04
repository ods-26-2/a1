"""Política mínima 7.2 aplicada na ingestão (sem banco)."""

from __future__ import annotations

import json

import pytest

from backend.taxonomy import TaxonomyCatalog, TaxonomyError
from backend.triage import PolicyCatalog, TriageError, TriageService

from conftest import valid_events


@pytest.fixture
def triage() -> TriageService:
    return TriageService(PolicyCatalog(), TaxonomyCatalog())


@pytest.mark.parametrize(
    ("result", "status"),
    [
        ("CONFORMING", "REVIEW"),
        ("NON_CONFORMING", "REVIEW"),
        ("ANOMALY", "REVIEW"),
        ("UNCERTAIN", "REVIEW"),
    ],
)
def test_four_results_follow_policy(triage, result, status):
    decision = triage.decide(valid_events()[result]["payload"])

    assert decision.status == status
    assert decision.policy_version == "triage-a1-1.1.0"
    assert decision.reason


def test_class_without_consequence_uses_default(tmp_path):
    policy = {
        "policy_version": "triage-teste",
        "taxonomy_version": "defects-a1-1.0.0",
        "default_status": "REVIEW",
        "minimum_confidence": {"CONFORMING": 0.7, "NON_CONFORMING": 0.7},
        "consequences": [{"defect_class": "FURADO", "status": "REJECTED"}],
    }
    (tmp_path / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    service = TriageService(PolicyCatalog(tmp_path), TaxonomyCatalog())

    decision = service.decide(valid_events()["NON_CONFORMING"]["payload"])

    assert decision.status == "REVIEW"
    assert "padrão REVIEW" in decision.reason


def test_unknown_class_is_rejected(triage):
    payload = dict(valid_events()["NON_CONFORMING"]["payload"], defect_class="RISCO")

    with pytest.raises(TaxonomyError):
        triage.decide(payload)


def test_unknown_taxonomy_version_is_rejected(triage):
    payload = dict(valid_events()["CONFORMING"]["payload"], taxonomy_version="defects-a1-9.9.9")

    with pytest.raises((TaxonomyError, TriageError)):
        triage.decide(payload)


@pytest.mark.parametrize("result", ["CONFORMING", "NON_CONFORMING"])
@pytest.mark.parametrize("confidence,expected", [(0.6999, "REVIEW"), (0.7, None), (1.0, None)])
def test_calibrated_policy_boundary_is_inclusive(tmp_path, result, confidence, expected):
    policy = {"policy_version": "test-calibration-only", "taxonomy_version": "defects-a1-1.0.0",
              "default_status": "REVIEW", "minimum_confidence": {"CONFORMING": 0.7, "NON_CONFORMING": 0.7},
              "consequences": [{"defect_class": "AMASSADO", "status": "REJECTED"}]}
    (tmp_path / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    service = TriageService(PolicyCatalog(tmp_path), TaxonomyCatalog())
    payload = dict(valid_events()[result]["payload"], confidence=confidence)
    decision = service.decide(payload)
    assert decision.status == (expected or ("APPROVED" if result == "CONFORMING" else "REJECTED"))
    assert "test-calibration-only" in decision.reason


def test_uncalibrated_policy_never_approves_silently(triage):
    decision = triage.decide(valid_events()["CONFORMING"]["payload"])
    assert decision.status == "REVIEW"
    assert "não calibrado" in decision.reason
