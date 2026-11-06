"""S3-10: HTTP validation, parameterized queries and real PostgreSQL history."""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.config import Settings
from backend.inspection_search import InspectionSearch
from backend.inspections import InspectionService
from backend.repository import InspectionRepository
from conftest import api_validator, valid_events


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"result": "APPROVED"},
    {"captured_from": "2026-11-06"}, {"captured_from": "2026-11-06T12:00:00"},
    {"captured_from": "1730000000"}, {"captured_to": "bad"},
    {"captured_from": "2026-11-06T12:00:00Z", "captured_to": "2026-11-06T09:00:00-03:00"},
    {"source_id": " "}, {"source_id": "bad\x00id"}, {"source_id": "a" * 257},
    {"defect_class": "amassado"}, {"defect_class": "a' OR true--"}, {"unexpected": "1"},
])
def test_invalid_http_filters_do_not_query_repository(params):
    app = create_app(Settings(database_url="postgresql://unused"))
    def forbidden(_):
        pytest.fail("invalid query reached service")
    app.state.services = SimpleNamespace(inspections=SimpleNamespace(search=forbidden))
    response = TestClient(app).get("/api/v1/inspections", params=params)
    assert response.status_code == 422


def test_http_normalizes_timezone_and_passes_all_filters():
    calls = []
    def search(filters):
        calls.append(filters)
        return {"items": [], "total": 0, "limit": filters.limit, "offset": filters.offset}
    app = create_app(Settings(database_url="postgresql://unused"))
    app.state.services = SimpleNamespace(inspections=SimpleNamespace(search=search))
    response = TestClient(app).get("/api/v1/inspections", params={
        "captured_from": "2026-11-06T09:00:00-03:00", "captured_to": "2026-11-07T00:00:00Z",
        "result": "NON_CONFORMING", "source_id": "cam 1&x", "defect_class": "AMASSADO", "limit": 5, "offset": 10,
    })
    assert response.status_code == 200
    assert calls[0].captured_from == datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    assert calls[0].source_id == "cam 1&x"
    assert list(api_validator("inspection-list.schema.json").iter_errors(response.json())) == []


def test_repository_binds_values_and_orders_with_stable_tiebreaker():
    calls = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, query, params=()):
            calls.append((query, params))
            return SimpleNamespace(fetchone=lambda: {"total": 7}, fetchall=lambda: [])
    repository = InspectionRepository(SimpleNamespace(connection=lambda: Connection()))
    hostile = "cam' OR true--"
    filters = InspectionSearch(source_id=hostile, result="ANOMALY", limit=2, offset=20)
    assert repository.search(filters) == ([], 7)
    assert calls[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert all(hostile not in query for query, _ in calls)
    assert calls[1][1] == ("ANOMALY", hostile)
    assert calls[2][1] == ("ANOMALY", hostile, 2, 20)
    assert "ORDER BY i.captured_at DESC, i.inspection_id DESC LIMIT %s OFFSET %s" in calls[2][0]


def test_period_predicate_is_inclusive_then_exclusive_and_service_projects_views():
    filters = InspectionSearch(captured_from="2026-11-06T12:00:00Z", captured_to="2026-11-07T00:00:00Z", defect_class="FURADO")
    sql, params = filters.predicate()
    assert sql == " WHERE i.captured_at >= %s AND i.captured_at < %s AND i.defect_class = %s"
    assert params[-1] == "FURADO"
    service = InspectionService(SimpleNamespace(search=lambda value: ([{"id": 1}], 1)), None)
    service.view = lambda row: {"projected": row["id"]}
    assert service.search(filters) == {"items": [{"projected": 1}], "total": 1, "limit": 50, "offset": 0}


def test_list_schema_rejects_wrong_page_and_invalid_view():
    validator = api_validator("inspection-list.schema.json")
    for value in ({"items": [], "total": -1, "limit": 20, "offset": 0},
                  {"items": [{}], "total": 1, "limit": 20, "offset": 0}):
        assert list(validator.iter_errors(value))


def seed_history(ingest):
    ids = []
    for index, (result, event) in enumerate(valid_events().items()):
        event = deepcopy(event)
        event["captured_at"] = "2026-01-01T12:00:00.000Z" if index < 2 else "2026-01-02T12:00:00.000Z"
        event["source_id"] = "camera-A" if index < 3 else "camera-B"
        outcome = ingest(event)
        assert outcome.status.value == "ACCEPTED", outcome.reason
        ids.append((result, outcome.inspection_id, event))
    return ids


def test_postgres_combined_filters_boundaries_and_empty_pages(client, ingest):
    rows = seed_history(ingest)
    response = client.get("/api/v1/inspections", params={"captured_from": "2026-01-01T12:00:00Z", "captured_to": "2026-01-02T12:00:00Z"})
    assert response.status_code == 200
    assert response.json()["total"] == 2
    target = next(entry for entry in rows if entry[0] == "NON_CONFORMING")
    filters = {"captured_from": target[2]["captured_at"], "result": "NON_CONFORMING", "source_id": target[2]["source_id"], "defect_class": "AMASSADO"}
    page = client.get("/api/v1/inspections", params=filters).json()
    assert page["total"] == 1 and page["items"][0]["inspection_id"] == target[1]
    assert list(api_validator("inspection-list.schema.json").iter_errors(page)) == []
    assert client.get("/api/v1/inspections", params={**filters, "source_id": "missing"}).json()["total"] == 0
    beyond = client.get("/api/v1/inspections", params={**filters, "offset": 50}).json()
    assert beyond["total"] == 1 and beyond["items"] == []


def test_postgres_stable_pages_original_analysis_and_audit_preserved(client, ingest, sql):
    seed_history(ingest)
    all_items = client.get("/api/v1/inspections").json()["items"]
    keys = [(item["times"]["captured_at"], item["inspection_id"]) for item in all_items]
    assert keys == sorted(keys, reverse=True)
    paged = [client.get("/api/v1/inspections", params={"limit": 1, "offset": index}).json()["items"][0]["inspection_id"] for index in range(4)]
    assert paged == [item["inspection_id"] for item in all_items]
    target = next(item for item in all_items if item["analysis"]["result"] == "NON_CONFORMING")
    assert client.post(f"/api/v1/inspections/{target['inspection_id']}/reviews", json={"action": "CORRECT", "operator": "op", "reason": "Conferido", "status": "REJECTED", "defect_class": "FURADO"}).status_code == 201
    before = sql("SELECT count(*) FROM audit_events")[0][0]
    page = client.get("/api/v1/inspections", params={"defect_class": "AMASSADO"}).json()
    assert page["items"][0]["analysis"]["defect"]["defect_class"] == "AMASSADO"
    assert page["items"][0]["final_decision"]["defect_class"] == "FURADO"
    assert client.get("/api/v1/inspections", params={"defect_class": "FURADO"}).json()["total"] == 0
    assert sql("SELECT count(*) FROM audit_events")[0][0] == before
    assert client.get(f"/api/v1/inspections/{target['inspection_id']}/history").status_code == 200
