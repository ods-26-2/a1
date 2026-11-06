"""Activity 22: bounded deterministic reports, explicit causes, safe exports."""
import csv
import io
import json
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import create_app
from backend.config import Settings
from backend.reports import (CauseRequest, ReportQuery, ReportService, ReportLimitExceeded,
                             aggregate_report, csv_cell, render_report, MAX_RECORDS)
from conftest import api_validator, valid_events

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
PERIOD = {"captured_from": "2026-01-01T00:00:00Z", "captured_to": "2026-01-03T00:00:00Z"}


def base_rows():
    return [
        {"source_id": "A", "taxonomy_version": "tax-1", "defect_class": "FURADO", "result": "NON_CONFORMING", "cause": None},
        {"source_id": "A", "taxonomy_version": "tax-1", "defect_class": "FURADO", "result": "NON_CONFORMING", "cause": "Alinhamento observado"},
        {"source_id": "B", "taxonomy_version": "tax-1", "defect_class": "FURADO", "result": "NON_CONFORMING", "cause": None},
        {"source_id": "A", "taxonomy_version": "tax-2", "defect_class": "FURADO", "result": "NON_CONFORMING", "cause": None},
        {"source_id": "A", "taxonomy_version": "tax-1", "defect_class": None, "result": "ANOMALY", "cause": None},
    ]


def test_recurrence_separates_source_taxonomy_and_never_infers_cause():
    rows, filters = base_rows(), ReportQuery(**PERIOD)
    report = aggregate_report("recurrence", rows, filters, NOW)
    assert report == aggregate_report("recurrence", list(reversed(rows)), filters, NOW)
    assert report["total_inspections"] == 5
    assert report["items"][0] == {"source_id": "A", "taxonomy_version": "tax-1", "defect_class": "FURADO", "count": 2, "rate": .4, "recurring": True}
    assert all(item["count"] == 1 and not item["recurring"] for item in report["items"][1:])
    causes = aggregate_report("causes", rows, filters, NOW)
    assert causes["items"] == [{"cause": None, "status": "NOT_RECORDED", "count": 4}, {"cause": "Alinhamento observado", "status": "OPERATOR_REPORTED", "count": 1}]
    for body in (report, causes, aggregate_report("recurrence", [], filters, NOW)):
        assert list(api_validator("report.schema.json").iter_errors(body)) == []


@pytest.mark.parametrize("params", [
    {}, {"captured_from": PERIOD["captured_from"]},
    {**PERIOD, "captured_to": "2026-03-01T00:00:00Z"},
    {**PERIOD, "captured_to": PERIOD["captured_from"]},
    {**PERIOD, "offset": 1}, {**PERIOD, "file_format": "html"},
])
def test_http_report_rejects_unbounded_unknown_or_invalid_filters(params):
    app = create_app(Settings(database_url="postgresql://unused"))
    app.state.services = SimpleNamespace(reports=SimpleNamespace(aggregate=lambda *_: pytest.fail("invalid query reached report")))
    assert TestClient(app).get("/api/v1/reports/recurrence", params=params).status_code == 422


@pytest.mark.parametrize("field,value", [("operator", " "), ("cause", ""), ("basis", " "), ("cause", "x"*201), ("basis", "bad\x00text"), ("basis", "bad\ud800")])
def test_cause_requires_explicit_valid_text(field, value):
    data = {"operator": "op", "cause": "Alinhamento observado", "basis": "Verificação manual"}
    with pytest.raises(ValidationError): CauseRequest(**{**data, field: value})


@pytest.mark.parametrize("text", ["=1+1", "+cmd", "-1", "@SUM(A1)", " \t=1", "\r\n+1", "\ufeff=1"])
def test_csv_formula_prefix_is_neutralized(text):
    assert csv_cell(text) == "'"+text


def test_json_and_csv_export_are_lossless_utf8_and_deterministic():
    report = aggregate_report("causes", [{**base_rows()[0], "cause": '=HYPERLINK("x")\nvírgula, aspas"'}], ReportQuery(**PERIOD), NOW)
    response = render_report(report, "csv")
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == 'attachment; filename="a1-causes.csv"'
    assert response.body.startswith(b"\xef\xbb\xbf")
    records = list(csv.reader(io.StringIO(response.body.decode("utf-8-sig"))))
    items = [json.loads(row[1]) for row in records[1:] if row[0] == "items"]
    assert items == report["items"]
    assert response.body == render_report(report, "csv").body
    assert json.loads(render_report(report, "json").body) == report


def test_export_size_limit_is_explicit(monkeypatch):
    monkeypatch.setattr("backend.reports.MAX_BYTES", 20)
    with pytest.raises(ReportLimitExceeded): render_report({"kind": "inspection", "data": "a"*100}, "json")


def test_service_bounds_rows_and_keeps_filter_values_parameterized():
    calls = []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, query, params=()):
            calls.append((query, params))
            return SimpleNamespace(fetchall=lambda: base_rows() * 1001)
    service = ReportService(SimpleNamespace(pool=SimpleNamespace(connection=Connection)), None)
    with pytest.raises(ReportLimitExceeded): service.aggregate("causes", ReportQuery(**PERIOD, source_id="A' OR true--"))
    assert calls[1][0] == "SET LOCAL statement_timeout = '5000ms'"
    assert "A' OR true--" not in calls[2][0]
    assert calls[2][1][-2:] == ("A' OR true--", MAX_RECORDS+1)


def test_http_report_timeout_limit_missing_and_success():
    import psycopg
    app = create_app(Settings(database_url="postgresql://unused"))
    def limited(*_): raise ReportLimitExceeded("reduza o período")
    app.state.services = SimpleNamespace(reports=SimpleNamespace(aggregate=limited, inspection=lambda _: None, record_cause=lambda *_: None))
    client = TestClient(app)
    assert client.get("/api/v1/reports/recurrence", params=PERIOD).status_code == 422
    assert client.get("/api/v1/inspections/missing/report").status_code == 404
    assert client.post("/api/v1/inspections/missing/causes", json={"operator": "op", "cause": "c", "basis": "b"}).status_code == 404
    def timeout(*_): raise psycopg.errors.QueryCanceled("statement timeout")
    app.state.services.reports.aggregate = timeout
    assert client.get("/api/v1/reports/recurrence", params=PERIOD).status_code == 503
    app.state.services.reports.aggregate = lambda kind, query: aggregate_report(kind, [], query, NOW)
    response = client.get("/api/v1/reports/recurrence", params=PERIOD)
    assert response.status_code == 200 and response.json()["total_inspections"] == 0


def seed_reports(ingest):
    ids = []
    for index in range(3):
        event = deepcopy(valid_events()["NON_CONFORMING"])
        event["message_id"] = str(uuid4())
        event["captured_at"] = "2026-01-02T12:00:00.000Z"
        event["source_id"] = "camera-A" if index < 2 else "camera-B"
        event["payload"]["frame_index"] += index
        outcome = ingest(event)
        assert outcome.status.value == "ACCEPTED", outcome.reason
        ids.append(outcome.inspection_id)
    return ids


def test_postgres_recurrence_cause_history_and_export(client, ingest, sql):
    ids = seed_reports(ingest)
    recurrence = client.get("/api/v1/reports/recurrence", params=PERIOD).json()
    assert recurrence["items"][0]["count"] == 2 and recurrence["items"][0]["recurring"]
    assert recurrence["total_inspections"] == 3
    assert client.get("/api/v1/reports/recurrence", params={**PERIOD, "source_id": "camera-B"}).json()["items"][0]["count"] == 1
    assert client.get("/api/v1/reports/recurrence", params={**PERIOD, "result": "ANOMALY"}).json()["items"] == []
    assert client.get("/api/v1/reports/causes", params=PERIOD).json()["items"] == [{"cause": None, "status": "NOT_RECORDED", "count": 3}]
    for cause in ("Primeira hipótese", "Alinhamento observado"):
        response = client.post(f"/api/v1/inspections/{ids[0]}/causes", json={"operator": "op", "cause": cause, "basis": "Observação da máquina"})
        assert response.status_code == 201
        assert list(api_validator("cause.schema.json").iter_errors(response.json())) == []
    causes = client.get("/api/v1/reports/causes", params=PERIOD).json()
    assert {item["cause"] for item in causes["items"]} == {None, "Alinhamento observado"}
    assert sql("SELECT count(*) FROM inspection_causes")[0][0] == 2
    assert sql("SELECT count(*) FROM audit_events WHERE event_type='CAUSE_RECORDED'")[0][0] == 2
    assert client.post(f"/api/v1/inspections/{ids[0]}/reviews", json={"action": "CORRECT", "operator": "op", "reason": "Furo confirmado", "status": "REJECTED", "defect_class": "FURADO"}).status_code == 201
    inspection = client.get(f"/api/v1/inspections/{ids[0]}/report").json()
    assert list(api_validator("report.schema.json").iter_errors(inspection)) == []
    assert inspection["inspection"]["analysis"]["defect"]["defect_class"] == "AMASSADO"
    assert inspection["inspection"]["final_decision"]["defect_class"] == "FURADO"
    assert inspection["inspection"]["evidence"]["state"] == "PENDING"
    assert inspection["history"]["triage"] == inspection["inspection"]["triage"]
    assert inspection["history"]["reviews"][0]["reason"] == "Furo confirmado"
    assert len(inspection["causes"]) == 2
    assert [event["event_type"] for event in inspection["history"]["events"]].count("CAUSE_RECORDED") == 2
    csv_response = client.get(f"/api/v1/inspections/{ids[0]}/report", params={"file_format": "csv"})
    assert csv_response.status_code == 200 and csv_response.content.startswith(b"\xef\xbb\xbf")
    assert client.get(f"/api/v1/inspections/{ids[0]}/history").status_code == 200


def test_postgres_causes_are_immutable_and_audit_failure_rolls_back(client, ingest, sql, monkeypatch):
    import psycopg
    ids = seed_reports(ingest)
    data = {"operator": "op", "cause": "Hipótese", "basis": "Observação manual"}
    assert client.post(f"/api/v1/inspections/{ids[0]}/causes", json=data).status_code == 201
    for query in ("UPDATE inspection_causes SET cause='changed'", "DELETE FROM inspection_causes", "TRUNCATE inspection_causes"):
        with pytest.raises(psycopg.Error): sql(query)
    original_count = sql("SELECT count(*) FROM inspection_causes")[0][0]
    def fail(*_): raise RuntimeError("audit failed")
    monkeypatch.setattr(client.app.state.services.repository, "_audit", fail)
    with pytest.raises(RuntimeError): client.post(f"/api/v1/inspections/{ids[1]}/causes", json=data)
    assert sql("SELECT count(*) FROM inspection_causes")[0][0] == original_count
