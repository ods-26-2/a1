"""Atividade 28: composição real com eventos sintéticos e publisher I8."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from urllib.request import urlopen

import psycopg

# Reuse the already-tested observational helpers; never call the A1 fake sender.
sys.path.insert(0, '/repos/a1/validacao-local')
from provar_fluxo import assert_committed, assert_rows, request, wait_for

DIRECTORY = Path('/evidencias')
EVENTS = DIRECTORY / 'eventos.jsonl'
REPORT = DIRECTORY / 'resultado.json'


def write_report(value):
    REPORT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare():
    session = str(uuid4())
    now = datetime.now(timezone.utc)
    timestamp = lambda moment: moment.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    events = []
    for sequence, path in enumerate(sorted(Path('/repos/i8/shared/mocks/kafka-2.0').glob('i8-piece-*.json'))):
        event = json.loads(path.read_text())
        event.update(message_id=str(uuid4()), session_id=session, sequence=sequence,
                     artifact_version='synthetic-transport-proof',
                     captured_at=timestamp(now - timedelta(milliseconds=120)),
                     occurred_at=timestamp(now - timedelta(milliseconds=40)),
                     published_at=timestamp(now))
        events.append(event)
    assert len(events) == 4
    assert {e['payload']['result'] for e in events} == {
        'CONFORMING', 'NON_CONFORMING', 'ANOMALY', 'UNCERTAIN'}
    EVENTS.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events), encoding='utf-8')
    report = {
        'status': 'preparado',
        'scope': 'real I8 publisher, Kafka, A1, PostgreSQL and API; synthetic events; no model inference',
        'synthetic_events': True, 'real_inference': False, 'shared_broker': False,
        'versions': {'a1': os.environ['A1_SHA'], 'i8': os.environ['I8_SHA']},
        'a1_working_tree_modified': os.environ['A1_DIRTY'] == 'true',
        'i8_source': 'main fixada; publisher de eventos, sem inferência',
        'events_sha256': hashlib.sha256(EVENTS.read_bytes()).hexdigest(),
        'message_ids': [e['message_id'] for e in events], 'phases': {},
        'limits': ['one partition and one replica', 'no real images/models or industrial performance',
                   'S4/S5/P7 reais não validados; S4 desativado', 'atividade 21 e regressão coletiva pendentes', 'shared broker not accessed'],
    }
    write_report(report)
    print(json.dumps({'prepared_events': 4, 'session_id': session}))


def verify(phase):
    report = json.loads(REPORT.read_text())
    assert hashlib.sha256(EVENTS.read_bytes()).hexdigest() == report['events_sha256']
    events = [json.loads(line) for line in EVENTS.read_text().splitlines()]
    if phase == 'reenvio':
        assert 'envio' in report['phases']
    if phase == 'reinicio':
        assert 'reenvio' in report['phases']
    receipt_phase = 'reenvio' if phase == 'reinicio' else phase
    receipts = [json.loads(line) for line in (DIRECTORY / f'recibos-{receipt_phase}.jsonl').read_text().splitlines()]
    assert len(receipts) == 4
    assert [r['message_id'] for r in receipts] == report['message_ids']
    assert all(r['topic'] == 'ods.industria.defeito_classificado' and r['partition'] == 0 for r in receipts)
    expected_publications = 4 if phase == 'envio' else 8
    expected_start = 0 if phase == 'envio' else 4
    assert [r['offset'] for r in receipts] == list(range(expected_start, expected_start + 4))
    health = wait_for(lambda: (value if (value := request('/health'))['status'] == 'ONLINE' else None))
    with urlopen(os.environ['FRONTEND_URL'], timeout=5) as response:
        html = response.read().decode('utf-8')
    assert '<meta name="a1-api-base" content="/api/v1" />' in html
    with urlopen(os.environ['FRONTEND_URL'] + 'js/app.js', timeout=5) as response:
        assert response.status == 200 and len(response.read()) > 0
    counts = assert_rows(report['message_ids'])
    offsets = assert_committed()
    assert offsets['high'] == expected_publications and offsets['committed'] == expected_publications
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        rows = conn.execute('SELECT message_id::text, raw_event FROM inspections').fetchall()
        assert {message_id: event for message_id, event in rows} == {e['message_id']: e for e in events}
        failures = conn.execute('SELECT count(*) FROM ingestion_failures').fetchone()[0]
        totals = {name: conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                  for name in ['inspections', 'commands']}
        assert failures == 0 and totals == {'inspections': 4, 'commands': 4}
        audit_types = dict(conn.execute('SELECT event_type, count(*) FROM audit_events GROUP BY event_type').fetchall())
        assert audit_types.get('INGESTED') == 4
        if phase != 'envio':
            assert audit_types == report['phases']['envio']['audit_counts']
    api = []
    for event in events:
        view = request('/inspections/INSP-' + event['message_id'])
        assert view['origin']['message_id'] == event['message_id']
        assert view['origin']['schema'] == event['schema'] and view['origin']['schema_version'] == '2.0'
        assert view['origin']['session_id'] == event['session_id']
        assert view['origin']['sequence'] == event['sequence']
        assert view['origin']['bbox'] == event['payload']['bbox']
        assert view['analysis']['result'] == event['payload']['result']
        assert view['analysis']['confidence'] == event['payload']['confidence']
        assert view['analysis']['similarity'] == event['payload']['similarity']
        api.append({'inspection_id': view['inspection_id'], 'result': view['analysis']['result'],
                    'triage_status': view['triage']['status']})
    report['phases'][phase] = {'status': 'aprovado', 'counts': counts, 'database_totals': totals,
        'ingestion_failures': failures, 'offsets': offsets, 'api_reads': api, 'audit_counts': audit_types,
        'original_events_preserved': True, 'health': health, 'frontend_real_api_proxy': True, 'receipts': receipts}
    report['status'] = 'composicao-local-aprovada' if phase == 'reinicio' else phase + '-aprovado'
    write_report(report)
    print(json.dumps({'phase': phase, 'status': 'aprovado', 'counts': counts, 'offsets': offsets}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['preparar', 'envio', 'reenvio', 'reinicio'])
    args = parser.parse_args()
    prepare() if args.phase == 'preparar' else verify(args.phase)
