"""Activity 30: metric summaries and Docker units are deterministic."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str):
    spec = spec_from_file_location(name, ROOT / f"fechamento-sprint3/{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pipeline = load("medir_pipeline")
metrics = load("consolidar_metricas")


def test_nearest_rank_and_summary_do_not_interpolate_small_sample() -> None:
    assert pipeline.nearest_rank([4, 1, 3, 2], 0.95) == 4
    assert pipeline.summary([1, 2, 3, 4]) == {
        "samples": 4, "min": 1, "p50": 2.5, "p95_nearest_rank": 4, "max": 4,
    }


def test_docker_memory_units_are_normalized_to_mib() -> None:
    assert metrics.memory_mib("512KiB / 1GiB") == 0.5
    assert metrics.memory_mib("1.5GiB / 2GiB") == 1536.0
    assert metrics.memory_mib("100MB / 1GB") == 95.367


def test_json_records_accepts_compose_array_and_stats_lines(tmp_path: Path) -> None:
    report = tmp_path / "records.jsonl"
    report.write_text('[{"Name":"db"},{"Name":"kafka"}]\n{"Name":"backend"}\n', encoding="utf-8")
    assert [item["Name"] for item in metrics.json_records(report)] == ["db", "kafka", "backend"]


def test_pipeline_reports_arrival_without_claiming_database_commit(tmp_path, monkeypatch) -> None:
    """The stored received_at marks ingest entry, even when read after commit."""
    import json
    from datetime import datetime, timezone
    from types import SimpleNamespace

    start = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
    (tmp_path / "envio-inicio-ns.txt").write_text(str(int(start.timestamp()) * 10**9))
    (tmp_path / "envio-fim-ns.txt").write_text(str(int(start.timestamp()) * 10**9 + 2 * 10**9))
    arrival = start.replace(microsecond=500000)
    rows = [(str(index), arrival, {"published_at": start.isoformat(),
             "payload": {"result": "CONFORMING"}}) for index in range(4)]

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, *_): return SimpleNamespace(fetchall=lambda: rows)

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'{"total": 4}'

    monkeypatch.setattr(pipeline, "EVIDENCE", tmp_path)
    monkeypatch.setattr(pipeline.psycopg, "connect", lambda *_: Connection())
    monkeypatch.setattr(pipeline, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("API_URL", "http://test/api/v1")
    output = tmp_path / "latencia.json"
    monkeypatch.setattr("sys.argv", ["medir_pipeline.py", "--output", str(output), "--api-samples", "1"])
    pipeline.main()
    value = json.loads(output.read_text())
    assert value["publisher_invocation_to_a1_ingestion_ms"]["p50"] == 500.0
    assert value["synthetic_published_marker_to_a1_ingestion_ms"]["p50"] == 500.0
    assert value["persistence_latency_measured"] is False
    assert "publisher_invocation_to_database_ms" not in value
    assert "synthetic_published_marker_to_database_ms" not in value
    assert all(item["publisher_invocation_to_a1_ingestion_ms"] == 500.0
               for item in value["observations"])
