"""Offline acceptance of the provisional stage-16 policy; no activation or DB."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from backend.taxonomy import TaxonomyCatalog, TaxonomyError
from backend.triage import PolicyCatalog, TriageError, TriageService
from conftest import valid_events


ROOT = Path(__file__).resolve().parents[1]
VERSION = "triage-a1-1.2.0-candidate"
CANDIDATE = ROOT / "shared/policies/triage/candidates" / VERSION


def candidate_service(path=CANDIDATE):
    return TriageService(PolicyCatalog.from_candidate(path), TaxonomyCatalog())


@pytest.mark.parametrize("result,status", [
    ("CONFORMING", "REVIEW"), ("NON_CONFORMING", "REJECTED"),
    ("ANOMALY", "REVIEW"), ("UNCERTAIN", "REVIEW"),
])
def test_candidate_four_results(result, status):
    decision = candidate_service().decide(valid_events()[result]["payload"])
    assert decision.status == status
    assert decision.policy_version == VERSION
    assert decision.reason


@pytest.mark.parametrize("confidence,status", [
    (0.799999, "REVIEW"), (0.8, "REJECTED"), (1.0, "REJECTED"),
])
def test_provisional_known_confidence_is_inclusive(confidence, status):
    payload = dict(valid_events()["NON_CONFORMING"]["payload"], confidence=confidence)
    assert candidate_service().decide(payload).status == status


def test_similarity_threshold_is_never_used_as_conforming_confidence():
    source = json.loads((CANDIDATE / "source-i8-policy.json").read_text())
    assert source["parameters"]["conforming_similarity"] != source["parameters"]["known_confidence"]
    payload = dict(valid_events()["CONFORMING"]["payload"], confidence=1.0)
    decision = candidate_service().decide(payload)
    assert decision.status == "REVIEW"
    assert "não calibrado" in decision.reason


@pytest.mark.parametrize("result", ["CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"])
def test_default_and_rollback_keep_previous_policy(result):
    payload = valid_events()[result]["payload"]
    before = TriageService(PolicyCatalog(), TaxonomyCatalog()).decide(payload)
    candidate_service().decide(payload)
    rollback = TriageService(PolicyCatalog(), TaxonomyCatalog()).decide(payload)
    assert before == rollback
    assert rollback.status == "REVIEW"
    assert rollback.policy_version == "triage-a1-1.1.0"


@pytest.mark.parametrize("defect_class", ["AMASSADO", "FURADO", "FURADO_AMASSADO"])
def test_candidate_reuses_existing_consequences(defect_class):
    payload = dict(valid_events()["NON_CONFORMING"]["payload"], defect_class=defect_class, confidence=0.8)
    assert candidate_service().decide(payload).status == "REJECTED"


def test_candidate_rejects_unknown_class():
    payload = dict(valid_events()["NON_CONFORMING"]["payload"], defect_class="UNKNOWN")
    with pytest.raises(TaxonomyError):
        candidate_service().decide(payload)


@pytest.mark.parametrize("filename", ["policy/content.json", "source-i8-policy.json"])
def test_hash_mismatch_cannot_load_candidate(tmp_path, filename):
    copy = tmp_path / "candidate"
    shutil.copytree(CANDIDATE, copy)
    path = copy / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(TriageError, match="hash SHA-256"):
        PolicyCatalog.from_candidate(copy)


@pytest.mark.parametrize("field,value", [
    ("commit", "origin/main"), ("product_id", "other-product"),
    ("repository", "https://example.com/unrelated"),
])
def test_origin_must_be_fixed_and_match_snapshot(tmp_path, field, value):
    copy = tmp_path / "candidate"
    shutil.copytree(CANDIDATE, copy)
    path = copy / "descriptor.json"
    descriptor = json.loads(path.read_text())
    descriptor["source"][field] = value
    path.write_text(json.dumps(descriptor))
    with pytest.raises(TriageError):
        PolicyCatalog.from_candidate(copy)


def test_candidate_cannot_relabel_similarity_as_confidence(tmp_path):
    copy = tmp_path / "candidate"
    shutil.copytree(CANDIDATE, copy)
    content_path = copy / "policy/content.json"
    content = json.loads(content_path.read_text())
    content["minimum_confidence"]["CONFORMING"] = 0.2354041860284747
    content_path.write_text(json.dumps(content))
    descriptor_path = copy / "descriptor.json"
    descriptor = json.loads(descriptor_path.read_text())
    descriptor["hash_sha256"] = hashlib.sha256(content_path.read_bytes()).hexdigest()
    descriptor_path.write_text(json.dumps(descriptor))
    with pytest.raises(TriageError, match="mapeamento"):
        PolicyCatalog.from_candidate(copy)


def test_missing_manifest_is_not_silently_loaded(tmp_path):
    with pytest.raises(TriageError, match="candidata inválida"):
        PolicyCatalog.from_candidate(tmp_path)
