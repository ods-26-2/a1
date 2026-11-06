"""Activity 23: S5 EVENT preparation with real PG, explicit fake transport."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest

from backend.s5 import S5Adapter,S5ContractError
from backend.s5_fake import FakeS5

START='2026-11-06T12:00:00.000Z'
END='2026-11-06T13:00:00.000Z'


def metric():
    return dict(event_type='TEST_EVENT',window_start_at=START,window_end_at=END,granularity='1h',count=4,uncertain_count=1)


@pytest.fixture
def lab(client):
    now=[datetime.now(timezone.utc)]
    adapter=S5Adapter(client.app.state.services.repository,lambda:now[0],retry_interval=1)
    return adapter,FakeS5(series=[metric()],clock=lambda:now[0]),now


def query(lab,**kwargs):
    return lab[0].request(query_id=kwargs.pop('query_id',uuid4()),period_start_at=kwargs.pop('start',START),
        period_end_at=kwargs.pop('end',END),granularity=kwargs.pop('granularity','1h'),**kwargs)


def reply(lab,row):
    assert lab[0].dispatch_pending(lab[1].send)==1
    return lab[1].reply(row['query_id'])


def test_event_query_reply_is_durable_and_independent_of_inspections(lab,sql):
    a,f,_=lab
    row=query(lab,event_type='TEST_EVENT')
    assert row['status']=='PENDING'
    message=reply(lab,row)
    assert f.sent[0]['producer']=='A1' and f.sent[0]['target']=='S5'
    assert a.receive(message)=='ACCEPTED'
    stored=a.get(row['query_id'])
    assert stored['status']=='COMPLETED' and stored['response']['payload']['series']==[metric()]
    assert sql('SELECT count(*) FROM inspections')[0][0]==0
    assert sql('SELECT count(*) FROM commands')[0][0]==0


def test_retry_and_recreated_adapter_keep_original_envelope(lab,sql):
    a,f,now=lab
    row=query(lab)
    def uncertain(topic,message):
        f.send(topic,message);raise RuntimeError('ack lost')
    with pytest.raises(RuntimeError):a.dispatch_pending(uncertain)
    original=f.sent[0]
    now[0]+=timedelta(seconds=2)
    restarted=S5Adapter(a.repository,lambda:now[0])
    assert restarted.request(query_id=row['query_id'],period_start_at=START,period_end_at=END,granularity='1h')['envelope']==original
    restarted.dispatch_pending(f.send)
    assert f.sent[1]==original
    assert restarted.receive(f.reply(row['query_id']))=='ACCEPTED'
    assert restarted.receive(f.reply(row['query_id']))=='DUPLICATE'
    assert sql('SELECT count(*) FROM s5_queries')[0][0]==1


def test_query_id_cannot_be_reused_for_another_filter(lab):
    row=query(lab)
    with pytest.raises(S5ContractError,match='outra intenção'):query(lab,query_id=row['query_id'],event_type='OTHER_EVENT')


@pytest.mark.parametrize('kwargs',[dict(start=END),dict(start='2026-99-06T12:00:00.000Z'),
    dict(end='2027-11-06T13:00:00.000Z'),dict(granularity='5m'),dict(event_type='minusculo'),
    dict(zone_id='')])
def test_invalid_request_does_not_persist_or_send(lab,sql,kwargs):
    with pytest.raises(S5ContractError):query(lab,**kwargs)
    assert sql('SELECT count(*) FROM s5_queries')[0][0]==0
    assert not lab[1].sent


@pytest.mark.parametrize('code',['INVALID_QUERY','PERIOD_TOO_LONG','UNKNOWN_ZONE'])
def test_error_reply_keeps_explicit_reason(lab,code):
    a,f,_=lab;f.error=code
    row=query(lab)
    assert a.receive(reply(lab,row))=='ACCEPTED'
    stored=a.get(row['query_id'])
    assert stored['status']=='REJECTED'
    assert stored['response']['payload']['error']['code']==code
    assert a.dispatch_pending(f.send)==0


def test_empty_series_is_success_not_service_error(lab):
    lab[1].series=[];row=query(lab)
    assert lab[0].receive(reply(lab,row))=='ACCEPTED'
    assert lab[0].get(row['query_id'])['response']['payload']['series']==[]


@pytest.mark.parametrize('change',['period','granularity','filter','uncertain','window','order','zone_series'])
def test_semantically_incompatible_reply_is_rejected(lab,sql,change):
    row=query(lab,event_type='TEST_EVENT')
    message=reply(lab,row);item=message['payload']['series'][0]
    if change=='period':item.update(window_start_at='2026-11-06T11:00:00.000Z',window_end_at=START)
    elif change=='granularity':item.update(granularity='15m',window_end_at='2026-11-06T12:15:00.000Z')
    elif change=='filter':item['event_type']='OTHER_EVENT'
    elif change=='uncertain':item['uncertain_count']=5
    elif change=='window':item['window_end_at']='2026-11-06T12:15:00.000Z'
    elif change=='order':
        # Valid individual windows, but reverse chronological order.
        row2=query(lab,start='2026-11-06T11:00:00.000Z');lab[0].dispatch_pending(lab[1].send)
        message=lab[1].reply(row2['query_id'])
        message['payload']['series']=[metric(),dict(metric(),window_start_at='2026-11-06T11:00:00.000Z',window_end_at=START)]
        row=row2
    else:
        message['payload']['series']=[dict(zone_id='z',window_start_at=START,window_end_at=END,granularity='1h',
            total_count=1,occupancy_peak=1,occupancy_avg=1,dwell_avg_s=1)]
    assert lab[0].receive(message)=='REJECTED'
    assert lab[0].get(row['query_id'])['status']=='SENT'
    assert sql('SELECT count(*) FROM ingestion_failures')[0][0]==1


def test_unknown_and_late_replies_do_not_change_queries(lab):
    row=query(lab);message=reply(lab,row)
    unknown=deepcopy(message);unknown['correlation_id']=str(uuid4())
    assert lab[0].receive(unknown)=='IGNORED'
    lab[2][0]+=timedelta(seconds=31)
    assert lab[0].receive(message)=='IGNORED'
    assert lab[0].get(row['query_id'])['status']=='EXPIRED'
    assert lab[0].dispatch_pending(lab[1].send)==0


def event(lab):
    return dict(message_type='event',message_id=str(uuid4()),schema='ods.s5.event_metrics',schema_version='1.0',
        producer='S5',published_at=START,captured_at=START,session_id=str(uuid4()),sequence=0,payload=metric())


def test_event_metrics_are_stored_once_without_aggregating_or_changing_i8(lab,sql):
    message=event(lab)
    assert lab[0].receive(message)=='ACCEPTED'
    assert lab[0].receive(message)=='DUPLICATE'
    assert lab[0].events()[0]['envelope']==message
    assert sql('SELECT count(*) FROM s5_metric_events')[0][0]==1
    assert sql('SELECT count(*) FROM inspections')[0][0]==0
    changed=deepcopy(message);changed['payload']['count']=5
    assert lab[0].receive(changed)=='REJECTED'
    assert lab[0].events()[0]['envelope']==message


@pytest.mark.parametrize('field,value',[('producer','I8'),('schema_version','2.0'),('message_id','bad\x00id'),
    ('captured_at','2026-99-06T12:00:00.000Z'),('sequence',True)])
def test_invalid_events_are_durably_rejected(lab,sql,field,value):
    message=event(lab);message[field]=value
    assert lab[0].receive(message)=='REJECTED'
    assert sql('SELECT count(*) FROM s5_metric_events')[0][0]==0
    assert sql('SELECT count(*) FROM ingestion_failures')[0][0]==1


def test_database_failure_prevents_send(lab,monkeypatch):
    row=query(lab)
    def fail(*args,**kwargs):raise RuntimeError('DB unavailable')
    monkeypatch.setattr(lab[0].repository.pool,'connection',fail)
    with pytest.raises(RuntimeError):lab[0].dispatch_pending(lab[1].send)
    assert not lab[1].sent
