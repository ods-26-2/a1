"""Activity 29: regression evidence must fail closed."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = spec_from_file_location("consolidar_regressao", ROOT / "fechamento-sprint3/consolidar_regressao.py")
assert SPEC is not None and SPEC.loader is not None
consolidator = module_from_spec(SPEC)
SPEC.loader.exec_module(consolidator)


def write_junit(path: Path, *, failures: int = 0) -> None:
    path.write_text(
        f'<testsuites><testsuite tests="5" failures="{failures}" errors="0" skipped="1"/></testsuites>',
        encoding="utf-8",
    )


def composition() -> dict:
    phase = {
        "status": "aprovado",
        "database_totals": {"inspections": 4, "commands": 4},
        "offsets": {"committed": 8},
        "frontend_real_api_proxy": True,
    }
    return {"status": "composicao-local-aprovada", "phases": {
        "envio": {**phase, "offsets": {"committed": 4}},
        "reenvio": phase,
        "reinicio": phase,
    }}


def test_junit_totals_are_exact(tmp_path: Path) -> None:
    report = tmp_path / "regressao.xml"
    write_junit(report)
    assert consolidator.junit_totals(report) == {
        "tests": 5, "failures": 0, "errors": 0, "skipped": 1, "passed": 4,
    }


def test_missing_frontend_proof_is_not_approved() -> None:
    value = composition()
    value["phases"]["reinicio"]["frontend_real_api_proxy"] = False
    assert not all(phase.get("frontend_real_api_proxy") is True for phase in value["phases"].values())


def test_failed_junit_is_not_approved(tmp_path: Path) -> None:
    report = tmp_path / "regressao.xml"
    write_junit(report, failures=1)
    totals = consolidator.junit_totals(report)
    assert totals["failures"] == 1
    assert totals["passed"] == 3
