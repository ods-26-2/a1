"""S4 adapter proof: real Kafka/PG/API; synthetic S4 and image, clearly labeled."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import psycopg
from confluent_kafka import Producer, Consumer, TopicPartition
from backend.fake_producer import default_events, refresh

SESSION='00000000-0000-4000-8000-000000000019'
ROOT=Path('/evidencias')


def sql(query,params=()):
    with psycopg.connect(os.environ['DATABASE_URL']) as connection:
        cursor=connection.execute(query,params)
        return cursor.fetchall()


def get(path):
    return json.load(urlopen('http://backend:8000/api/v1'+path,timeout=2))


def wait_for(check):
    end=time.monotonic()+45
    last=None
    while time.monotonic()<end:
        try:
            last=check()
            if last:return last
        except Exception as exc:last=str(exc)
        time.sleep(.25)
    raise AssertionError(f'Prova S4 excedeu o prazo: {last}')


def offsets():
    client=Consumer({'bootstrap.servers':os.environ['KAFKA_BROKER_URL'],'group.id':'a1-s4-v1','enable.auto.commit':False})
    try:
        result={}
        for topic in ['ods.s4.capture.reply','ods.s4.clip']:
            partition=TopicPartition(topic,0)
            high=client.get_watermark_offsets(partition,timeout=2)[1]
            committed=client.committed([partition],timeout=2)[0].offset
            result[topic]=dict(committed=committed,high=high)
        return result
    finally:client.close()


def snapshot(ids):
    views=[get('/inspections/'+identity) for identity in ids]
    assert all(v['evidence']['state']=='AVAILABLE' for v in views)
    assert len({v['evidence']['clip_id'] for v in views})==4
    assert sql("SELECT count(*) FROM commands WHERE target='S4' AND status='COMPLETED'")[0][0]==4
    assert sql("SELECT count(*) FROM audit_events WHERE event_type='S4_AVAILABLE'")[0][0]==4
    assert sql('SELECT count(*) FROM ingestion_failures')[0][0]==0
    for view in views:
        clip=view['evidence']['clip_id']
        body=urlopen('http://s4-fake:8080/media/'+clip+'.png',timeout=2).read()
        descriptor=sql('SELECT descriptor FROM evidence WHERE inspection_id=%s',(view['inspection_id'],))[0][0]
        assert hashlib.sha256(body).hexdigest()==descriptor['payload']['hash_sha256']
        assert descriptor['source_id']==view['origin']['source_id']
        assert descriptor['payload']['start_at']==view['times']['captured_at']
    return dict(inspections=len(views),completed_commands=4,available_audits=4,synthetic_image_hashes_verified=4)


def publish(events):
    producer=Producer({'bootstrap.servers':os.environ['KAFKA_BROKER_URL'],'acks':'all','enable.idempotence':True,'delivery.timeout.ms':10000})
    receipts=[]
    for event in events:
        producer.produce('ods.industria.defeito_classificado',value=json.dumps(event).encode(),on_delivery=lambda e,m:receipts.append(e))
    assert producer.flush(10)==0 and len(receipts)==len(events) and not any(receipts)


def main():
    if '--recheck' in sys.argv:
        report=json.loads((ROOT/'resultado-s4.json').read_text())
        report['after_backend_restart']=snapshot(report['inspection_ids'])
    else:
        events=refresh(default_events(False,'2.0'))
        for index,event in enumerate(events):
            event['message_id']=str(uuid4());event['session_id']=SESSION
            event['sequence']=index;event['payload']['frame_index']=index
        ids=['INSP-'+event['message_id'] for event in events]
        publish(events)
        wait_for(lambda:sql("SELECT count(*) FROM evidence WHERE state='AVAILABLE'")[0][0]==4)
        before=snapshot(ids)
        # Re-send exact stored S4 commands through Kafka: fake returns same descriptors.
        commands=sql("SELECT transport_envelope FROM commands WHERE target='S4' ORDER BY created_at,command_id")
        producer=Producer({'bootstrap.servers':os.environ['KAFKA_BROKER_URL'],'acks':'all'})
        receipts=[]
        for (command,) in commands:
            producer.produce('ods.s4.capture.command',value=json.dumps(command).encode(),on_delivery=lambda e,m:receipts.append(e))
        assert producer.flush(10)==0 and len(receipts)==4 and not any(receipts)
        # Both response topics must be consumed through all duplicate messages.
        wait_for(lambda:all(x['high']>=8 and x['committed']==x['high'] for x in offsets().values()))
        after=snapshot(ids)
        health=get('/health')
        assert health['status']=='ONLINE'
        assert next(c for c in health['components'] if c['name']=='s4')['status']=='UP'
        report=dict(mode='SIMULATED_S4_AND_MEDIA_REAL_KAFKA_POSTGRES_A1',inspection_ids=ids,
                    first=before,after_duplicate_commands=after,response_offsets=offsets(),health=health)
    (ROOT/'resultado-s4.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
