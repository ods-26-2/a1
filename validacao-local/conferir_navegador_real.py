"""Observa API e banco após o roteiro manual de navegador com eventos sintéticos.

Não cria inspeções, revisões ou causas. Execute no backend do laboratório,
antes de encerrar seu volume, passando a inspeção escolhida no navegador.
"""
import argparse
import json
import os
from urllib.parse import quote
from urllib.request import urlopen

import psycopg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inspection_id")
    args = parser.parse_args()
    base = "http://127.0.0.1:8000/api/v1"

    def read(path):
        with urlopen(base + path, timeout=5) as response:
            assert response.status == 200
            return json.load(response)

    report = read("/inspections/" + quote(args.inspection_id, safe="") + "/report")
    view = report["inspection"]
    assert view["inspection_id"] == args.inspection_id
    assert view["analysis"]["result"] == "NON_CONFORMING"
    assert view["analysis"]["defect"]["defect_class"] == "AMASSADO"
    assert view["triage"]["status"] == "REVIEW"
    assert view["final_decision"]["status"] == "REVIEW"
    assert view["final_decision"]["defect_class"] == "FURADO"
    assert [r["action"] for r in report["history"]["reviews"]] == ["CORRECT", "SEND_TO_REVIEW"]
    assert len(report["causes"]) == 1
    assert report["causes"][0]["cause"] == "Hipótese sintética para validar persistência"
    assert view["versions"]["model"] == "synthetic-transport-proof"

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        counts = {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("inspections", "commands", "reviews", "inspection_causes")}
        assert counts == {"inspections": 4, "commands": 4, "reviews": 2, "inspection_causes": 1}
        raw, original_class = conn.execute(
            "SELECT raw_event, defect_class FROM inspections WHERE inspection_id=%s",
            (args.inspection_id,),
        ).fetchone()
        assert original_class == raw["payload"]["defect_class"] == "AMASSADO"
        audits = dict(conn.execute(
            "SELECT event_type, count(*) FROM audit_events WHERE inspection_id=%s GROUP BY event_type",
            (args.inspection_id,),
        ).fetchall())
        assert audits.get("REVIEW_RECORDED") == 2 and audits.get("CAUSE_RECORDED") == 1
        assert audits.get("INGESTED") == 1

    queue = read("/inspections/review-queue?limit=100&offset=0")
    assert queue["total"] == 4
    assert any(item["inspection_id"] == args.inspection_id for item in queue["items"])
    filtered = read("/inspections?result=NON_CONFORMING&source_id=cam-linha1&defect_class=AMASSADO")
    assert filtered["total"] == 1 and filtered["items"][0]["inspection_id"] == args.inspection_id
    assert read("/inspections?defect_class=FURADO")["total"] == 0
    print(json.dumps({"status": "PASS", "scope": "API real e PostgreSQL após roteiro do navegador",
                      "inspection_id": args.inspection_id, "synthetic_events": True,
                      "real_inference": False, "database_counts": counts,
                      "audit_counts_for_inspection": audits, "original_event_preserved": True,
                      "review_queue_total": queue["total"], "final_report": report},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
