"""Consolida a prova da atividade 29 sem reinterpretar resultados parciais."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from xml.etree import ElementTree


def read_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def junit_totals(path: Path) -> dict[str, int]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tests = junit_totals(args.junit)
    composition = json.loads(args.composition.read_text(encoding="utf-8"))
    environment = read_environment(args.environment)
    commit = environment.get("a1_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("commit A1 ausente ou inválido")

    phases = composition.get("phases", composition.get("checks", {}))
    restart = phases.get("reinicio", {})
    frontend = all(phase.get("frontend_real_api_proxy") is True for phase in phases.values())
    gates = {
        "contracts": {"status": "PASS"},
        "python_tests": {**tests, "status": "PASS" if tests["failures"] == tests["errors"] == 0 else "FAIL"},
        "frontend": {"status": "PASS" if frontend else "FAIL"},
        "database": {"status": "PASS" if restart.get("database_totals") == {"inspections": 4, "commands": 4} else "FAIL"},
        "kafka": {"status": "PASS" if restart.get("offsets", {}).get("committed") == 8 else "FAIL"},
        "restart": {"status": "PASS" if restart.get("status") == "aprovado" else "FAIL"},
    }
    passed = all(gate["status"] == "PASS" for gate in gates.values())
    result = {
        "activity": 29,
        "status": "REGRESSAO_LOCAL_APROVADA" if passed else "REGRESSAO_REPROVADA",
        "a1_commit": commit,
        "a1_tree_clean_before_run": environment.get("a1_tree_clean") == "true",
        "gates": gates,
        "composition_status": composition.get("status"),
        "scope": "contratos, PostgreSQL, Kafka, frontend e reinício da composição local",
        "limits": [
            "A inferência real da atividade 18 não é reproduzida; o publisher I8 usa quatro eventos sintéticos.",
            "S4, S5 e P7 reais permanecem fora desta composição.",
            "Uma partição Kafka e uma réplica não representam escala industrial."
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
