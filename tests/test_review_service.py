"""S3-08 review invariants, independent of transport and PostgreSQL availability."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.inspections import ReviewService
from backend.taxonomy import TaxonomyCatalog


class ReviewRepositoryDouble:
    def __init__(self):
        self.original = {"taxonomy_version": "defects-a1-1.0.0", "triage_status": "REVIEW", "defect_class": "AMASSADO"}
        self.entries = []

    def find(self, inspection_id):
        return deepcopy(self.original) if inspection_id == "one" else None

    def add_review(self, inspection_id, *, action, operator, recorded_at, reason, decide):
        prior = self.entries[-1] if self.entries else {"status": "REVIEW", "defect_class": "AMASSADO"}
        status, defect_class = decide(prior["status"], prior["defect_class"])
        entry = {"review_id": uuid4(), "action": action, "operator": operator, "recorded_at": recorded_at,
                 "reason": reason, "status": status, "defect_class": defect_class}
        self.entries.append(entry)
        return entry


@pytest.fixture
def service():
    repository = ReviewRepositoryDouble()
    inspections = SimpleNamespace(taxonomy=TaxonomyCatalog(), get=lambda _: {"original": deepcopy(repository.original), "final_decision": repository.entries[-1]})
    return ReviewService(repository, inspections, lambda: datetime.now(timezone.utc))


def test_correct_confirm_and_reopen_preserve_original_and_final_class(service):
    original = deepcopy(service.repository.original)
    service.submit("one", action="CORRECT", operator=" op ", reason=" Furo verificado ", status="REJECTED", defect_class="FURADO")
    confirmed = service.submit("one", action="CONFIRM", operator="second", reason="Conferido")
    assert confirmed["inspection"]["final_decision"]["defect_class"] == "FURADO"
    assert confirmed["inspection"]["final_decision"]["status"] == "REJECTED"
    service.submit("one", action="SEND_TO_REVIEW", operator="third", reason="Nova avaliação")
    assert service.repository.entries[-1]["status"] == "REVIEW"
    assert service.repository.entries[0]["reason"] == "Furo verificado"
    assert service.repository.entries[0]["operator"] == "op"
    assert service.repository.original == original


@pytest.mark.parametrize("payload", [
    {"action": "CONFIRM", "operator": "op", "reason": " "},
    {"action": "CONFIRM", "operator": " ", "reason": "Conferido"},
    {"action": "CORRECT", "operator": "op", "reason": "Conferido", "status": "REJECTED"},
    {"action": "CORRECT", "operator": "op", "reason": "Conferido", "status": "APPROVED", "defect_class": "FURADO"},
    {"action": "CORRECT", "operator": "op", "reason": "Conferido", "status": "REJECTED", "defect_class": "UNKNOWN"},
    {"action": "CONFIRM", "operator": "op", "reason": "Conferido", "status": "APPROVED"},
])
def test_invalid_review_never_appends(service, payload):
    with pytest.raises(ValueError):
        service.submit("one", **payload)
    assert service.repository.entries == []


def test_http_requires_reason_and_returns_validation_errors_without_transport(service):
    # No lifespan: this HTTP boundary test never starts MQTT or a database.
    app = create_app(Settings(database_url="postgresql://unused"))
    app.state.services = SimpleNamespace(reviews=service)
    client = TestClient(app)
    response = client.post("/api/v1/inspections/one/reviews", json={"action": "CONFIRM", "operator": "op"})
    assert response.status_code == 422
    response = client.post("/api/v1/inspections/one/reviews", json={"action": "CORRECT", "operator": "op", "reason": "Conferido", "status": "REJECTED"})
    assert response.status_code == 422
    assert service.repository.entries == []


def test_actual_view_keeps_analysis_and_exposes_corrected_class():
    from conftest import api_validator, valid_events
    from backend.ingestion import IngestionService
    from backend.inspections import InspectionService
    from backend.repository import SaveResult
    from backend.triage import PolicyCatalog, TriageService

    captured = {}
    def save(record, **kwargs):
        captured.update(record.__dict__)
        return SaveResult(record.inspection_id, True)
    taxonomy = TaxonomyCatalog()
    now = datetime.now(timezone.utc)
    ingestion = IngestionService(SimpleNamespace(save_ingested=save), TriageService(PolicyCatalog(), taxonomy), lambda: now)
    ingestion.ingest(valid_events()["NON_CONFORMING"])
    row = {**captured, "final_status": "REJECTED", "final_reason": "Furo confirmado", "final_operator": "op",
           "final_recorded_at": now, "final_defect_class": "FURADO", "evidence_state": "PENDING",
           "evidence_clip_id": None, "evidence_url": None, "evidence_expires_at": None, "evidence_detail": "Pendente"}
    view = InspectionService(None, taxonomy).view(row)
    assert list(api_validator("inspection-view.schema.json").iter_errors(view)) == []
    assert view["analysis"]["defect"]["defect_class"] == "AMASSADO"
    assert view["final_decision"]["defect_class"] == "FURADO"
    assert view["triage"]["status"] == "REVIEW"
