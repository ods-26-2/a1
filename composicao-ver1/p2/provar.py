"""Observa imagens, journal, recibos, Kafka, API e PostgreSQL; não injeta resultados."""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from urllib.request import urlopen

DIRECTORY=Path('/evidencias')
sys.path.insert(0,'/repos/a1/validacao-local')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_events(rows, samples, events, engine):
    """Falha se o journal não corresponde à inferência de referência e aos frames."""
    assert len(events)==len(rows)==len(samples)==3
    assert len({e['message_id'] for e in events})==len(events)
    for sequence,(row,sample,event) in enumerate(zip(rows,samples,events)):
        assert event['schema']=='ods.industria.defeito_classificado' and event['schema_version']=='2.0'
        assert event['artifact_version']==engine
        assert event['source_id']==row['source_id'] and event['session_id']==row['session_id']
        assert event['sequence']==sequence and event['captured_at']==row['captured_at']
        payload=event['payload'];expected=sample['expected']
        assert payload['frame_index']==row['frame_index'] and payload['detection_id']==row['detection_id']
        assert payload['bbox']==row['bbox']
        assert payload['result']==expected['result'] and payload.get('defect_class')==expected['defect_class']
        for field in ['similarity','confidence']:
            assert math.isclose(payload[field],expected[field],rel_tol=1e-4,abs_tol=5e-5)
        timestamps=[datetime.fromisoformat(event[k].replace('Z','+00:00')) for k in ['captured_at','occurred_at','published_at']]
        assert timestamps==sorted(timestamps)


def verify(phase):
    import psycopg
    from provar_fluxo import assert_rows,assert_committed,request,wait_for
    if phase=='engine-ausente':
        from provar_fluxo import offsets
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            assert conn.execute('SELECT count(*) FROM inspections').fetchone()[0]==0
            assert conn.execute('SELECT count(*) FROM commands').fetchone()[0]==0
        assert offsets()['high']==0 and not (DIRECTORY/'eventos.jsonl').exists()
        (DIRECTORY/'engine-ausente.json').write_text(json.dumps(dict(
            status='aprovado',fallback=False,journal_created=False,publications=0,inspections=0,commands=0))+'\n')
        return
    preparation=json.loads((DIRECTORY/'preparacao.json').read_text())
    assert digest(DIRECTORY/'frames.jsonl')==preparation['frames_sha256']
    rows=[json.loads(line) for line in (DIRECTORY/'frames.jsonl').read_text().splitlines()]
    for sample in preparation['samples']:
        assert digest(DIRECTORY/sample['image'])==sample['image_sha256']
    for name,expected_hash in preparation['artifact_hashes'].items():
        if name.startswith('models/'):
            path=Path('/repos/i8')/name
        elif name.startswith('engines/'):
            path=DIRECTORY/name
        elif name.startswith('taxonomy/'):
            path=Path('/repos/a1/shared/artifacts/defect-taxonomy/defects-a1-1.0.0')/Path(name).name
        else:
            raise AssertionError('Artefato não reconhecido no registro de preparação')
        assert digest(path)==expected_hash
    events=[json.loads(line) for line in (DIRECTORY/'eventos.jsonl').read_text().splitlines()]
    check_events(rows,preparation['samples'],events,preparation['engine_version'])
    report_path=DIRECTORY/'resultado.json'
    report=json.loads(report_path.read_text()) if report_path.exists() else dict(
        scope=preparation['scope'],synthetic_images=True,real_inference=True,shared_broker=False,
        industrial_acceptance=False,persistence_latency_measured=False,
        versions={'a1':os.environ['A1_SHA'],**json.loads((DIRECTORY/'versoes.json').read_text())},
        a1_working_tree_modified=os.environ['A1_DIRTY']=='true',
        preparation_sha256=digest(DIRECTORY/'preparacao.json'),events_sha256=digest(DIRECTORY/'eventos.jsonl'),
        engine=preparation['engine_version'],message_ids=[e['message_id'] for e in events],
        observed_results=sorted({e['payload']['result'] for e in events}),limits=preparation['limits'],phases={})
    assert json.loads((DIRECTORY/'engine-ausente.json').read_text())['status']=='aprovado'
    report['missing_engine_fails_before_publication']=True
    assert digest(DIRECTORY/'preparacao.json')==report['preparation_sha256']
    assert digest(DIRECTORY/'eventos.jsonl')==report['events_sha256']
    if phase=='reenvio':assert 'envio' in report['phases']
    if phase=='reinicio':assert 'reenvio' in report['phases']
    receipt_phase='reenvio' if phase=='reinicio' else phase
    receipts=[json.loads(line) for line in (DIRECTORY/f'recibos-{receipt_phase}.jsonl').read_text().splitlines()]
    ids=report['message_ids'];n=len(events)
    assert len(receipts)==n and [r['message_id'] for r in receipts]==ids
    assert all(r['topic']=='ods.industria.defeito_classificado' and r['partition']==0 for r in receipts)
    start=0 if phase=='envio' else n
    assert [r['offset'] for r in receipts]==list(range(start,start+n))
    counts=assert_rows(ids);offsets=assert_committed()
    assert offsets['high']==offsets['committed']==(n if phase=='envio' else 2*n)
    health=wait_for(lambda:(v if (v:=request('/health'))['status']=='ONLINE' else None))
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        actual=conn.execute('SELECT message_id::text, raw_event FROM inspections').fetchall()
        assert {k:v for k,v in actual}=={e['message_id']:e for e in events}
        totals={name:conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ['inspections','commands']}
        assert totals==dict(inspections=n,commands=n)
        assert conn.execute('SELECT count(*) FROM ingestion_failures').fetchone()[0]==0
        audit=dict(conn.execute('SELECT event_type,count(*) FROM audit_events GROUP BY event_type').fetchall())
        assert audit.get('INGESTED')==n
        if phase!='envio':assert audit==report['phases']['envio']['audit_counts']
    assert request('/inspections?limit=100&offset=0')['total']==n
    for event in events:
        view=request('/inspections/INSP-'+event['message_id'])
        assert view['origin']['message_id']==event['message_id']
        assert view['analysis']['result']==event['payload']['result']
        assert view['analysis']['similarity']==event['payload']['similarity']
        assert view['analysis']['confidence']==event['payload']['confidence']
    with urlopen(os.environ['FRONTEND_URL'],timeout=5) as response:
        assert '<meta name="a1-api-base" content="/api/v1" />' in response.read().decode()
    report['phases'][phase]=dict(status='aprovado',counts=counts,database_totals=totals,offsets=offsets,
        audit_counts=audit,original_events_preserved=True,reference_predictions_match=True,
        health=health,frontend_real_api_proxy=True,receipts=receipts)
    report['status']='p2-kafka-a1-local-aprovado' if phase=='reinicio' else phase+'-aprovado'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'phase':phase,'status':'aprovado','counts':counts,'offsets':offsets}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['engine-ausente','envio','reenvio','reinicio'])
    verify(parser.parse_args().phase)
