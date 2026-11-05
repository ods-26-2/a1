"""Prova finita das etapas 07, 08 e 09 com Kafka e PostgreSQL reais."""

import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen

from confluent_kafka import Consumer, TopicPartition
import psycopg

from backend.fake_producer import default_events, publish_events, refresh


REPORT = Path("/evidencias/resultado.json")
PENDING = Path("/evidencias/falha-banco.json")
BROKER = os.environ["KAFKA_BROKER_URL"]
TOPIC = os.environ["KAFKA_TOPIC"]
GROUP = os.environ["KAFKA_GROUP_ID"]
API = os.environ["API_URL"]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wait_for(operation, timeout=45):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        try:
            value = operation()
            if value:
                return value
        except Exception as exc:
            last = exc
        time.sleep(0.5)
    raise RuntimeError(f"Condição não atingida no prazo: {last}")


def request(path, *, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    call = Request(API + path, data=data, headers=headers, method=method)
    with urlopen(call, timeout=5) as response:
        return json.load(response)


def database_counts(ids):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = conn.execute(
            "SELECT inspection_id, message_id::text FROM inspections "
            "WHERE message_id::text = ANY(%s)",
            (ids,),
        ).fetchall()
        inspection_ids = [row[0] for row in rows]
        commands = conn.execute(
            "SELECT count(*) FROM commands WHERE inspection_id = ANY(%s)",
            (inspection_ids,),
        ).fetchone()[0]
        ingested = conn.execute(
            "SELECT count(*) FROM audit_events WHERE event_type = 'INGESTED' "
            "AND inspection_id = ANY(%s)",
            (inspection_ids,),
        ).fetchone()[0]
        return {"inspections": len(rows), "commands": commands, "ingested": ingested}


def offsets():
    reader = Consumer(
        {
            "bootstrap.servers": BROKER,
            "group.id": GROUP,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    try:
        partition = TopicPartition(TOPIC, 0)
        low, high = reader.get_watermark_offsets(partition, timeout=10)
        committed = reader.committed([partition], timeout=10)[0]
        if committed.error:
            raise RuntimeError(str(committed.error))
        return {"low": low, "high": high, "committed": committed.offset}
    finally:
        # Este leitor apenas observa offsets. Ele não assina, consome nem confirma mensagens.
        reader.close()


def assert_rows(ids):
    expected = {"inspections": len(ids), "commands": len(ids), "ingested": len(ids)}
    return wait_for(lambda: (counts if (counts := database_counts(ids)) == expected else None))


def assert_committed():
    return wait_for(
        lambda: (
            value
            if (value := offsets())["high"] > 0 and value["committed"] >= value["high"]
            else None
        )
    )


def queue_ids():
    ids, offset, total = set(), 0, None
    while total is None or offset < total:
        queue = request(f"/inspections/review-queue?limit=100&offset={offset}")
        items = queue["items"]
        total = queue["total"]
        ids.update(item["inspection_id"] for item in items)
        if not items:
            break
        offset += len(items)
    return ids


def prove_s3_08(message_ids):
    candidates = []
    for message_id in message_ids:
        inspection_id = "INSP-" + message_id
        detail = request("/inspections/" + inspection_id)
        if detail["triage"]["status"] == "REVIEW":
            candidates.append((inspection_id, detail))
    if not candidates:
        raise AssertionError("Nenhuma inspeção sintética entrou na fila de revisão")

    inspection_id, original = candidates[0]
    if inspection_id not in queue_ids():
        raise AssertionError("Inspeção recém-ingerida não apareceu na fila de revisão")

    options = request(f"/inspections/{inspection_id}/review-options")
    original_class = (original["analysis"].get("defect") or {}).get("defect_class")
    classes = [item["defect_class"] for item in options["classes"]]
    selected_class = next((item for item in classes if item != original_class), classes[0])
    correction = request(
        f"/inspections/{inspection_id}/reviews",
        method="POST",
        body={
            "action": "CORRECT",
            "operator": "op-samuel",
            "reason": "Correção validada na prova Kafka da etapa 09.",
            "status": "REJECTED",
            "defect_class": selected_class,
        },
    )
    corrected = request("/inspections/" + inspection_id)
    assert corrected["analysis"] == original["analysis"]
    assert corrected["triage"] == original["triage"]
    assert corrected["final_decision"]["status"] == "REJECTED"
    assert corrected["final_decision"]["defect_class"] == selected_class
    assert inspection_id not in queue_ids()

    reopened = request(
        f"/inspections/{inspection_id}/reviews",
        method="POST",
        body={
            "action": "SEND_TO_REVIEW",
            "operator": "op-samuel",
            "reason": "Retorno à fila validado na prova Kafka da etapa 09.",
        },
    )
    history = request(f"/inspections/{inspection_id}/history")
    assert inspection_id in queue_ids()
    assert history["triage"] == original["triage"]
    assert history["final_decision"]["status"] == "REVIEW"
    assert [item["action"] for item in history["reviews"]][-2:] == [
        "CORRECT",
        "SEND_TO_REVIEW",
    ]
    event_types = [item["event_type"] for item in history["events"]]
    assert event_types.count("REVIEW_RECORDED") >= 2
    return {
        "inspection_id": inspection_id,
        "original_analysis": original["analysis"],
        "original_triage": original["triage"],
        "selected_class": selected_class,
        "correction_review_id": correction["review_id"],
        "reopen_review_id": reopened["review_id"],
        "actions": [item["action"] for item in history["reviews"]],
        "audit_events": event_types,
        "final_status": history["final_decision"]["status"],
        "queue_after_reopen": True,
    }


def recheck_s3_08(proof):
    inspection_id = proof["inspection_id"]
    detail = request("/inspections/" + inspection_id)
    history = request(f"/inspections/{inspection_id}/history")
    review_ids = {item["review_id"] for item in history["reviews"]}
    assert detail["analysis"] == proof["original_analysis"]
    assert detail["triage"] == proof["original_triage"]
    assert detail["final_decision"]["status"] == "REVIEW"
    assert proof["correction_review_id"] in review_ids
    assert proof["reopen_review_id"] in review_ids
    assert inspection_id in queue_ids()
    return {
        "inspection_id": inspection_id,
        "reviews": len(history["reviews"]),
        "audit_events": len(history["events"]),
        "original_preserved": True,
        "final_status": detail["final_decision"]["status"],
        "in_review_queue": True,
    }


def run_normal_proof():
    wait_for(lambda: request("/health")["status"] == "ONLINE")
    first = refresh(default_events(False, "2.0"))
    ids = [event["message_id"] for event in first]
    publish_events(first, broker=BROKER, topic=TOPIC, timeout=15)
    initial = assert_rows(ids)
    assert_committed()

    publish_events(first, broker=BROKER, topic=TOPIC, timeout=15)
    after_replay = assert_rows(ids)
    replay_offsets = assert_committed()

    second = refresh(default_events(False, "1.0"))
    publish_events(second, broker=BROKER, topic=TOPIC, timeout=15)
    ids += [event["message_id"] for event in second]
    final = assert_rows(ids)
    final_offsets = assert_committed()
    for message_id in ids:
        detail = request("/inspections/INSP-" + message_id)
        assert detail["origin"]["message_id"] == message_id

    return {
        "status": "fluxo-normal-aprovado",
        "scope": "eventos sintéticos; Kafka, API A1 e PostgreSQL reais; sem inferência I8",
        "broker": BROKER,
        "topic": TOPIC,
        "group": GROUP,
        "partitions_verified": [0],
        "message_ids": ids,
        "final_2_0": initial,
        "same_ids_replayed": after_replay,
        "offsets_after_replay": replay_offsets,
        "including_fresh_1_0": final,
        "offsets_final": final_offsets,
        "api_reads": len(ids),
        "events_published": 12,
        "s3_08": prove_s3_08(ids),
    }


def publish_during_database_failure():
    before = offsets()
    event = refresh(default_events(False, "2.0"))[0]
    proof = {
        "status": "preparado",
        "message_id": event["message_id"],
        "event": event,
        "offsets_before_publish": before,
    }
    write_json(PENDING, proof)
    publish_events([event], broker=BROKER, topic=TOPIC, timeout=15)
    wait_for(lambda: (value if (value := offsets())["high"] > before["high"] else None))

    def failed_persistence_health():
        health = request("/health")
        subscriber = next(
            component for component in health["components"] if component["name"] == "i8-subscriber"
        )
        if (
            health["status"] == "DEGRADED"
            and subscriber["status"] == "DOWN"
            and "Falha ao persistir mensagem" in subscriber["detail"]
        ):
            return health
        return None

    health = wait_for(failed_persistence_health, timeout=30)
    after = offsets()
    if after["committed"] >= after["high"]:
        raise AssertionError("Offset confirmado durante a falha; interrompa o PostgreSQL antes desta prova")
    proof.update(
        {
            "status": "publicado-sem-confirmacao",
            "offsets_before_recovery": after,
            "no_premature_commit": True,
            "health_during_failure": health,
        }
    )
    write_json(PENDING, proof)
    return proof


def verify_database_recovery():
    wait_for(lambda: request("/health")["status"] == "ONLINE")
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    message_id = pending["message_id"]
    counts = assert_rows([message_id])
    committed = assert_committed()
    detail = request("/inspections/INSP-" + message_id)
    assert detail["origin"]["message_id"] == message_id

    # Repetir a mesma mensagem depois da recuperação não pode criar nova inspeção.
    publish_events([pending["event"]], broker=BROKER, topic=TOPIC, timeout=15)
    after_replay = assert_rows([message_id])
    replay_offsets = assert_committed()
    result = {
        "message_id": message_id,
        "offsets_before_recovery": pending["offsets_before_recovery"],
        "no_premature_commit": pending["no_premature_commit"],
        "after_recovery": counts,
        "offsets_after_recovery": committed,
        "same_id_replayed_after_recovery": after_replay,
        "offsets_after_replay": replay_offsets,
        "event_lost": False,
        "duplicate_created": False,
    }
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["status"] = "aprovado-fase-2-kafka-real"
    report["database_failure_recovery"] = result
    write_json(REPORT, report)
    return result


def recheck_after_restart():
    wait_for(lambda: request("/health")["status"] == "ONLINE")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report["after_backend_restart"] = assert_rows(report["message_ids"])
    report["offsets_after_restart"] = assert_committed()
    report["s3_08_after_restart"] = recheck_s3_08(report["s3_08"])
    if "database_failure_recovery" in report:
        pending_id = report["database_failure_recovery"]["message_id"]
        report["database_failure_after_restart"] = assert_rows([pending_id])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--recheck", action="store_true", help="revalidar após reinício do backend")
    modes.add_argument(
        "--publish-pending",
        action="store_true",
        help="publicar uma mensagem enquanto o PostgreSQL estiver interrompido",
    )
    modes.add_argument(
        "--verify-pending",
        action="store_true",
        help="validar persistência após restaurar PostgreSQL e backend",
    )
    args = parser.parse_args()

    if args.publish_pending:
        result = publish_during_database_failure()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.verify_pending:
        result = verify_database_recovery()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    report = recheck_after_restart() if args.recheck else run_normal_proof()
    write_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
