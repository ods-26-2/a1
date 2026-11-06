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
