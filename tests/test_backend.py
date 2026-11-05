"""Backend A1 com PostgreSQL (S3-07): API, deduplicação, reinício e auditoria.

Critérios: reinício preserva dados; mensagem repetida não duplica registro; API
responde detalhe/histórico; trilha da inspeção e da revisão.
"""

from __future__ import annotations

import copy
from uuid import uuid4

import pytest

from conftest import OfflineSubscriber, api_validator, invalid_events, valid_events


EXPECTED_STATUS = {
    "CONFORMING": "REVIEW",
    "NON_CONFORMING": "REVIEW",
    "ANOMALY": "REVIEW",
    "UNCERTAIN": "REVIEW",
}


def _ingest_all(ingest) -> dict[str, str]:
    ids = {}
    for result, event in valid_events().items():
        outcome = ingest(event)
        assert outcome.status.value == "ACCEPTED", outcome.reason
        ids[result] = outcome.inspection_id
    return ids


def test_health_is_real_and_online(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert list(api_validator("health.schema.json").iter_errors(body)) == []
    assert body["mode"] == "REAL"
    assert body["status"] == "ONLINE"
    assert {"name": "database", "status": "UP", "detail": "PostgreSQL acessível."} in body[
        "components"
    ]


def test_current_without_inspections_is_204(client):
    assert client.get("/api/v1/inspections/current").status_code == 204


def test_four_results_are_stored_and_served(client, ingest):
    ids = _ingest_all(ingest)
    validator = api_validator("inspection-view.schema.json")

    for result, inspection_id in ids.items():
        response = client.get(f"/api/v1/inspections/{inspection_id}")
        assert response.status_code == 200
        view = response.json()
        assert list(validator.iter_errors(view)) == []
        event = valid_events()[result]
        assert view["origin"]["message_id"] == event["message_id"]
        assert view["times"]["captured_at"] == event["captured_at"]
        assert view["analysis"]["result"] == result
        assert view["triage"]["status"] == EXPECTED_STATUS[result]
        assert view["triage"]["decided_by"] == "AUTO"
        assert view["final_decision"] is None
        assert view["evidence"]["state"] == "PENDING"
        assert view["evidence"]["url"] is None

    defect = client.get(f"/api/v1/inspections/{ids['NON_CONFORMING']}").json()["analysis"][
        "defect"
    ]
    assert defect["name"] == "Amassado"


def test_inspection_id_preserves_complete_message_identity(ingest):
    event = valid_events()["NON_CONFORMING"]
    outcome = ingest(event)

    assert outcome.inspection_id == f"INSP-{event['message_id']}"


def test_session_prefix_collision_cannot_reuse_inspection_id():
    from backend.ingestion import inspection_id_for

    first = copy.deepcopy(valid_events()["CONFORMING"])
    second = copy.deepcopy(first)
    second["message_id"] = str(uuid4())
    second["session_id"] = first["session_id"][:8] + "-0000-4000-8000-000000000001"

    assert inspection_id_for(first) != inspection_id_for(second)


@pytest.mark.parametrize("context_change", ["session_prefix", "source"])
def test_distinct_observation_contexts_do_not_collide(ingest, sql, context_change):
    first = copy.deepcopy(valid_events()["CONFORMING"])
    second = copy.deepcopy(first)
    second["message_id"] = str(uuid4())
    if context_change == "session_prefix":
        # Different valid UUIDs with the same first eight characters.
        second["session_id"] = first["session_id"][:8] + "-0000-4000-8000-000000000001"
    else:
        second["source_id"] = "cam-linha2"

    left, right = ingest(first), ingest(second)

    assert left.status.value == right.status.value == "ACCEPTED"
    assert left.inspection_id != right.inspection_id
    assert sql("SELECT count(*) FROM inspections")[0][0] == 2


def test_repeated_message_is_not_duplicated(ingest, sql):
    event = valid_events()["CONFORMING"]

    first = ingest(event)
    second = ingest(copy.deepcopy(event))

    assert first.status.value == "ACCEPTED"
    assert second.status.value == "DUPLICATE"
    assert second.inspection_id == first.inspection_id
    assert sql("SELECT count(*) FROM inspections")[0][0] == 1
    assert sql("SELECT count(*) FROM audit_events WHERE event_type = 'INGESTED'")[0][0] == 1
    assert sql("SELECT count(*) FROM commands")[0][0] == 1


def test_invalid_events_are_rejected_and_logged(ingest, sql):
    for event in invalid_events():
        assert ingest(event).status.value == "REJECTED"
    assert ingest("não é JSON de objeto").status.value == "REJECTED"

    assert sql("SELECT count(*) FROM inspections")[0][0] == 0
    assert sql("SELECT count(*) FROM ingestion_failures")[0][0] == len(invalid_events()) + 1


def test_unknown_class_is_rejected(ingest, sql):
    event = copy.deepcopy(valid_events()["NON_CONFORMING"])
    event["payload"]["defect_class"] = "RISCO"

    outcome = ingest(event)

    assert outcome.status.value == "REJECTED"
    assert "RISCO" in outcome.reason
    assert sql("SELECT reason FROM ingestion_failures")[0][0] == outcome.reason


def test_same_detection_from_another_message_is_rejected(ingest):
    event = valid_events()["CONFORMING"]
    ingest(event)
    other = dict(copy.deepcopy(event), message_id=str(uuid4()))

    outcome = ingest(other)

    assert outcome.status.value == "REJECTED"
    assert "outra mensagem" in outcome.reason


def test_current_is_the_latest_received(client, ingest):
    ids = _ingest_all(ingest)
    last = list(ids.values())[-1]

    assert client.get("/api/v1/inspections/current").json()["inspection_id"] == last


def test_review_keeps_automatic_decision_and_history(client, ingest):
    inspection_id = ingest(valid_events()["NON_CONFORMING"]).inspection_id
    url = f"/api/v1/inspections/{inspection_id}/reviews"

    sent = client.post(url, json={"action": "SEND_TO_REVIEW", "operator": "op-samuel", "reason": "Conferir peça."})
    confirmed = client.post(url, json={"action": "CONFIRM", "operator": "op-icaro", "reason": "Dúvida mantida."})

    assert sent.status_code == 201
    receipt = confirmed.json()
    assert list(api_validator("review-receipt.schema.json").iter_errors(receipt)) == []
    assert receipt["persisted"] is True
    view = receipt["inspection"]
    assert view["triage"]["status"] == "REVIEW"
    assert view["final_decision"]["status"] == "REVIEW"
    assert view["final_decision"]["decided_by"] == "op-icaro"

    history = client.get(f"/api/v1/inspections/{inspection_id}/history").json()
    assert list(api_validator("inspection-history.schema.json").iter_errors(history)) == []
    assert history["triage"]["status"] == "REVIEW"
    assert [review["action"] for review in history["reviews"]] == ["SEND_TO_REVIEW", "CONFIRM"]
    assert [event["event_type"] for event in history["events"]] == [
        "INGESTED",
        "TRIAGED",
        "EVIDENCE_REQUESTED",
        "REVIEW_RECORDED",
        "REVIEW_RECORDED",
    ]
    assert history["events"][3]["details"]["previous_status"] == "REVIEW"


@pytest.mark.parametrize(
    "body",
    [
        {"action": "APPROVE", "operator": "op-samuel"},
        {"action": "CONFIRM", "operator": "   "},
        {"action": "CONFIRM"},
        {"action": "CONFIRM", "operator": "op-samuel", "status": "APPROVED"},
    ],
)
def test_invalid_review_is_refused(client, ingest, body):
    inspection_id = ingest(valid_events()["CONFORMING"]).inspection_id

    response = client.post(f"/api/v1/inspections/{inspection_id}/reviews", json=body)

    assert response.status_code == 422


def test_unknown_inspection_is_404(client):
    assert client.get("/api/v1/inspections/INSP-x-0-0").status_code == 404
    assert client.get("/api/v1/inspections/INSP-x-0-0/history").status_code == 404
    response = client.post(
        "/api/v1/inspections/INSP-x-0-0/reviews",
        json={"action": "CONFIRM", "operator": "op-samuel", "reason": "Conferido."},
    )
    assert response.status_code == 404


def test_data_survives_restart(settings, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app import create_app
    monkeypatch.setattr("backend.app.A1KafkaConsumer", OfflineSubscriber)

    with TestClient(create_app(settings)) as first:
        inspection_id = first.app.state.services.ingestion.ingest(
            valid_events()["UNCERTAIN"]
        ).inspection_id
        first.post(
            f"/api/v1/inspections/{inspection_id}/reviews",
            json={"action": "CONFIRM", "operator": "op-samuel", "reason": "Conferido."},
        )

    with TestClient(create_app(settings)) as second:
        view = second.get(f"/api/v1/inspections/{inspection_id}").json()
        repeated = second.app.state.services.ingestion.ingest(valid_events()["UNCERTAIN"])

    assert view["triage"]["status"] == "REVIEW"
    assert view["final_decision"]["decided_by"] == "op-samuel"
    assert repeated.status.value == "DUPLICATE"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE inspections SET triage_status = 'APPROVED'",
        "DELETE FROM inspections",
        "UPDATE reviews SET status = 'APPROVED'",
        "DELETE FROM audit_events",
        "TRUNCATE inspections CASCADE",
    ],
)
def test_audit_records_are_immutable(client, ingest, sql, statement):
    import psycopg

    inspection_id = ingest(valid_events()["NON_CONFORMING"]).inspection_id
    client.post(
        f"/api/v1/inspections/{inspection_id}/reviews",
        json={"action": "CONFIRM", "operator": "op-samuel", "reason": "Conferido."},
    )

    with pytest.raises(psycopg.errors.RaiseException, match="imutável"):
        sql(statement)
    assert sql("SELECT triage_status FROM inspections")[0][0] == "REVIEW"


def test_correction_updates_queue_without_mutating_original(client, ingest, sql):
    inspection_id = ingest(valid_events()["NON_CONFORMING"]).inspection_id
    assert client.get("/api/v1/inspections/review-queue").json()["total"] == 1
    options = client.get(f"/api/v1/inspections/{inspection_id}/review-options").json()
    assert options["taxonomy_version"] == "defects-a1-1.0.0"
    assert any(item["defect_class"] == "FURADO" for item in options["classes"])
    receipt = client.post(f"/api/v1/inspections/{inspection_id}/reviews", json={
        "action": "CORRECT", "operator": "op-1", "reason": "Furo confirmado manualmente.",
        "status": "REJECTED", "defect_class": "FURADO",
    })
    assert receipt.status_code == 201, receipt.text
    assert list(api_validator("review-receipt.schema.json").iter_errors(receipt.json())) == []
    view = client.get(f"/api/v1/inspections/{inspection_id}").json()
    assert view["analysis"]["defect"]["defect_class"] == "AMASSADO"
    assert view["triage"]["status"] == "REVIEW"
    assert view["final_decision"]["status"] == "REJECTED"
    assert view["final_decision"]["defect_class"] == "FURADO"
    queue = client.get("/api/v1/inspections/review-queue").json()
    assert list(api_validator("review-queue.schema.json").iter_errors(queue)) == []
    assert queue["total"] == 0
    client.post(f"/api/v1/inspections/{inspection_id}/reviews", json={
        "action": "SEND_TO_REVIEW", "operator": "op-2", "reason": "Solicitar segunda avaliação.",
    })
    assert client.get("/api/v1/inspections/review-queue").json()["total"] == 1
    assert sql("SELECT defect_class FROM inspections")[0][0] == "AMASSADO"
    history = client.get(f"/api/v1/inspections/{inspection_id}/history").json()
    assert list(api_validator("inspection-history.schema.json").iter_errors(history)) == []
    assert history["reviews"][0]["reason"] == "Furo confirmado manualmente."
    assert history["events"][-1]["details"]["previous_defect_class"] == "FURADO"


@pytest.mark.parametrize("review", [
    {"action": "CORRECT", "status": "REJECTED", "defect_class": "UNKNOWN"},
    {"action": "CORRECT", "status": "REJECTED"},
    {"action": "CORRECT", "status": "APPROVED", "defect_class": "FURADO"},
    {"action": "CORRECT"},
    {"action": "CONFIRM", "status": "APPROVED"},
])
def test_inconsistent_correction_is_rejected(client, ingest, review):
    inspection_id = ingest(valid_events()["UNCERTAIN"]).inspection_id
    response = client.post(f"/api/v1/inspections/{inspection_id}/reviews", json={
        "operator": "op", "reason": "Análise manual.", **review,
    })
    assert response.status_code == 422
