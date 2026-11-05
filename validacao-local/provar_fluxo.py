"""Finite fake/Kafka/A1/PostgreSQL proof. No I8 inference or shared broker."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import urlopen

from confluent_kafka import Consumer, TopicPartition
import psycopg

from backend.fake_producer import default_events, publish_events, refresh

REPORT = Path('/evidencias/resultado.json')
BROKER = os.environ['KAFKA_BROKER_URL']
TOPIC = os.environ['KAFKA_TOPIC']
GROUP = os.environ['KAFKA_GROUP_ID']
API = os.environ['API_URL']


def wait_for(operation, timeout=45):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        try:
            value = operation()
            if value:
                return value
        except Exception as exc:
            last = exc
        time.sleep(.5)
    raise RuntimeError(f'Condição não atingida no prazo: {last}')


def request(path):
    with urlopen(API + path, timeout=5) as response:
        return json.load(response)


def database_counts(ids):
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        rows = conn.execute('SELECT inspection_id, message_id::text FROM inspections '
                            'WHERE message_id::text = ANY(%s)', (ids,)).fetchall()
        inspection_ids = [row[0] for row in rows]
        commands = conn.execute('SELECT count(*) FROM commands WHERE inspection_id = ANY(%s)',
                                (inspection_ids,)).fetchone()[0]
        ingested = conn.execute("SELECT count(*) FROM audit_events WHERE event_type = 'INGESTED' "
                               'AND inspection_id = ANY(%s)', (inspection_ids,)).fetchone()[0]
        return {'inspections': len(rows), 'commands': commands, 'ingested': ingested}


def offsets():
    reader = Consumer({'bootstrap.servers': BROKER, 'group.id': GROUP,
                       'enable.auto.commit': False, 'enable.auto.offset.store': False})
    try:
        partition = TopicPartition(TOPIC, 0)
        low, high = reader.get_watermark_offsets(partition, timeout=10)
        committed = reader.committed([partition], timeout=10)[0]
        if committed.error:
            raise RuntimeError(str(committed.error))
        return {'low': low, 'high': high, 'committed': committed.offset}
    finally:
        # This reader never subscribes, consumes or commits; it only observes offsets.
        reader.close()


def assert_rows(ids):
    expected = {'inspections': len(ids), 'commands': len(ids), 'ingested': len(ids)}
    return wait_for(lambda: (counts if (counts := database_counts(ids)) == expected else None))


def assert_committed():
    return wait_for(lambda: (value if (value := offsets())['high'] > 0
                            and value['committed'] >= value['high'] else None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recheck', action='store_true', help='verify persisted IDs after backend restart')
    args = parser.parse_args()
    wait_for(lambda: request('/health')['status'] == 'ONLINE')
    if args.recheck:
        report = json.loads(REPORT.read_text())
        report['after_backend_restart'] = assert_rows(report['message_ids'])
        report['offsets_after_restart'] = assert_committed()
    else:
        # Synthetic observations, with fresh IDs/session; no real inference is claimed.
        first = refresh(default_events(False, '2.0'))
        ids = [event['message_id'] for event in first]
        publish_events(first, broker=BROKER, topic=TOPIC, timeout=15)
        initial = assert_rows(ids)
        assert_committed()
        publish_events(first, broker=BROKER, topic=TOPIC, timeout=15)
        after_replay = assert_rows(ids)
        replay_offsets = assert_committed()
        second = refresh(default_events(False, '1.0'))
        publish_events(second, broker=BROKER, topic=TOPIC, timeout=15)
        ids += [event['message_id'] for event in second]
        final = assert_rows(ids)
        final_offsets = assert_committed()
        for message_id in ids:
            detail = request('/inspections/INSP-' + message_id)
            assert detail['origin']['message_id'] == message_id
        report = {
            'status': 'passed-local-real-kafka',
            'scope': 'synthetic events; real Kafka, A1 API and PostgreSQL; no I8 model inference',
            'broker': BROKER, 'topic': TOPIC, 'group': GROUP,
            'message_ids': ids, 'final_2_0': initial,
            'same_ids_replayed': after_replay, 'offsets_after_replay': replay_offsets,
            'including_fresh_1_0': final, 'offsets_final': final_offsets,
            'api_reads': len(ids), 'events_published': 12,
        }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
