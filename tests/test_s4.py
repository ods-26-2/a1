"""S3-09: real PostgreSQL/API plus explicit S4 simulator; no real media claim."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
import json

import pytest

from backend.fake_producer import default_events
from backend.s4 import S4Adapter
from backend.s4_fake import FakeS4
from backend.s4_kafka import S4KafkaWorker


@pytest.fixture
def lab(client,ingest,sql):
    event=default_events(False)[0]
    inspection=ingest(event).inspection_id
    now=[datetime.now(timezone.utc)]
    adapter=S4Adapter(client.app.state.services.repository,lambda:now[0],timeout=30,retry_interval=1)
    fake=FakeS4(session_id=event['session_id'],clock=lambda:now[0])
    command=sql("SELECT command_id FROM commands WHERE target='S4'")[0][0]
    return adapter,fake,command,inspection,now,client,sql


def deliver(lab):
    a,f,c,*_=lab
    assert a.dispatch_pending(f.send)==1
    return f.messages(c)


def status(lab): return lab[-1]('SELECT status FROM commands WHERE command_id=%s',(lab[2],))[0][0]
def evidence(lab): return lab[5].get('/api/v1/inspections/'+lab[3]).json()['evidence']


def test_reply_is_not_descriptor_and_api_is_updated_only_after_match(lab):
    a,f,c,inspection,now,client,sql=lab
    reply,clip=deliver(lab)
    assert f.sent[0]['payload']['at']==clip['payload']['start_at']
    assert a.receive(reply)=='ACCEPTED'
    assert status(lab)=='ACCEPTED' and evidence(lab)['state']=='PENDING'
    assert a.receive(clip)=='ACCEPTED'
    assert status(lab)=='COMPLETED' and evidence(lab)['state']=='AVAILABLE'
    assert evidence(lab)['clip_id']==clip['payload']['clip_id']
    assert sql('SELECT descriptor FROM evidence')[0][0]==clip
    assert sql("SELECT count(*) FROM audit_events WHERE event_type='S4_AVAILABLE'")[0][0]==1
    assert sql('SELECT count(*) FROM inspections')[0][0]==1
    assert sql('SELECT count(*) FROM reviews')[0][0]==0


def test_lost_delivery_reuses_durable_envelope_after_adapter_restart(lab):
    a,f,c,_,now,*_=lab
    def uncertain(topic,message):
        f.send(topic,message)
        raise RuntimeError('lost acknowledgement')
    with pytest.raises(RuntimeError): a.dispatch_pending(uncertain)
    original=f.sent[0]
    now[0]+=timedelta(seconds=2)
    restarted=S4Adapter(a.repository,lambda:now[0],retry_interval=1)
    assert restarted.dispatch_pending(f.send)==1
    assert f.sent[1]==original and f.captures==1
    for m in f.messages(c): restarted.receive(m)
    now[0]+=timedelta(seconds=2)
    assert restarted.dispatch_pending(f.send)==0


@pytest.mark.parametrize('reverse',[False,True])
def test_duplicates_and_descriptor_before_reply_do_not_regress(lab,reverse):
    a=lab[0]
    messages=deliver(lab)
    for m in reversed(messages) if reverse else messages:
        a.receive(m)
        assert a.receive(m)=='DUPLICATE'
    assert status(lab)=='COMPLETED'
    assert lab[-1]("SELECT count(*) FROM audit_events WHERE event_type='S4_AVAILABLE'")[0][0]==1


@pytest.mark.parametrize('code',['SOURCE_NOT_FOUND','OUT_OF_BUFFER','DISK_FULL'])
def test_service_error_is_unavailable_and_audited(lab,code):
    a,f,*_=lab
    f.error=code
    assert a.receive(deliver(lab)[0])=='ACCEPTED'
    assert status(lab)=='REJECTED'
    assert evidence(lab)['state']=='UNAVAILABLE' and code in evidence(lab)['detail']
    assert evidence(lab)['url'] is None


@pytest.mark.parametrize('field',['source','session','event','at','end','captured','clip','type'])
def test_wrong_inspection_media_is_durably_rejected(lab,field):
    a=lab[0]
    reply,clip=deliver(lab)
    a.receive(reply)
    if field=='source': clip['source_id']='other'
    elif field=='session': clip['session_id']=str(uuid4())
    elif field=='event': clip['payload']['event_id']=str(uuid4())
    elif field=='at': clip['payload']['start_at']='2026-01-01T00:00:00.000Z'
    elif field=='end': clip['payload']['end_at']='2026-01-01T00:00:00.000Z'
    elif field=='captured': clip['captured_at']='2026-01-01T00:00:00.000Z'
    elif field=='clip': clip['payload']['clip_id']=str(uuid4())
    else: clip['payload']['media_type']='CLIP'
    assert a.receive(clip)=='REJECTED'
    assert evidence(lab)['state']=='PENDING'
    assert lab[-1]('SELECT count(*) FROM ingestion_failures')[0][0]==1


@pytest.mark.parametrize('field',['producer','version','hash','timestamp','uuid','nan'])
def test_malformed_descriptor_never_updates_evidence(lab,field):
    clip=deliver(lab)[1]
    if field=='producer': clip['producer']='I8'
    elif field=='version': clip['schema_version']='2.0'
    elif field=='hash': clip['payload']['hash_sha256']='short'
    elif field=='timestamp': clip['payload']['expires_at']='2026-99-01T00:00:00.000Z'
    elif field=='uuid': clip['message_id']='bad'
    else: clip['payload']['extra']=float('nan')
    assert lab[0].receive(clip)=='REJECTED'
    assert evidence(lab)['state']=='PENDING'


def test_timeout_and_late_response_cannot_resurrect(lab):
    messages=deliver(lab)
    lab[4][0]+=timedelta(seconds=31)
    lab[0].expire()
    assert status(lab)=='EXPIRED' and evidence(lab)['state']=='UNAVAILABLE'
    for m in messages: assert lab[0].receive(m)=='IGNORED'
    assert lab[0].dispatch_pending(lab[1].send)==0


def test_expired_media_and_api_hides_url_even_without_worker_tick(lab):
    a,f,*_=lab
    reply,clip=deliver(lab)
    a.receive(clip)
    # SQL projection must hide stale URLs immediately, independently of worker.
    lab[-1]('UPDATE evidence SET expires_at=%s',(datetime.now(timezone.utc)-timedelta(seconds=1),))
    assert evidence(lab)['state']=='EXPIRED' and evidence(lab)['url'] is None
    a.expire()
    assert lab[-1]('SELECT state FROM evidence')[0][0]=='EXPIRED'


def test_already_expired_descriptor_has_no_public_url(lab):
    clip=deliver(lab)[1]
    clip['payload']['expires_at']=(lab[4][0]-timedelta(seconds=1)).isoformat(timespec='milliseconds').replace('+00:00','Z')
    assert lab[0].receive(clip)=='ACCEPTED'
    assert evidence(lab)['state']=='EXPIRED' and evidence(lab)['url'] is None


def test_native_s4_uri_requires_access_gateway(lab):
    clip=deliver(lab)[1]
    clip['payload']['media_uri']='s4://clips/'+clip['payload']['clip_id']+'.png'
    assert lab[0].receive(clip)=='ACCEPTED'
    assert status(lab)=='COMPLETED'
    assert evidence(lab)['state']=='UNAVAILABLE' and evidence(lab)['url'] is None


def test_event_id_fallback_correlates_without_correlation_id(lab):
    clip=deliver(lab)[1]
    del clip['correlation_id']
    assert lab[0].receive(clip)=='ACCEPTED'
    assert evidence(lab)['state']=='AVAILABLE'


def test_unknown_command_is_ignored_and_conflicting_duplicate_is_rejected(lab):
    a=lab[0]
    clip=deliver(lab)[1]
    unknown=deepcopy(clip)
    unknown['correlation_id']=str(uuid4())
    assert a.receive(unknown)=='IGNORED'
    a.receive(clip)
    changed=deepcopy(clip)
    changed['payload']['media_uri']='https://other.invalid/changed.png'
    assert a.receive(changed)=='REJECTED'
    assert evidence(lab)['url']==clip['payload']['media_uri']


def test_failure_persisting_command_prevents_send(lab,monkeypatch):
    def fail(*args,**kwargs): raise RuntimeError('DB unavailable')
    monkeypatch.setattr(lab[0].repository.pool,'connection',fail)
    with pytest.raises(RuntimeError): lab[0].dispatch_pending(lab[1].send)
    assert lab[1].sent==[]


class ConsumerDouble:
    def __init__(self): self.commits=[]
    def commit(self,**kwargs): self.commits.append(kwargs['message']); return []


class WireMessage:
    def __init__(self,body,topic='ods.s4.clip'): self.body,self.name=body,topic
    def value(self): return self.body
    def topic(self): return self.name
    def offset(self): return 7


def worker(adapter):
    instance=S4KafkaWorker.__new__(S4KafkaWorker)
    instance.adapter=adapter
    instance.consumer=ConsumerDouble()
    return instance


def test_offset_commits_after_durable_acceptance_and_duplicate(lab):
    clip=deliver(lab)[1]
    w=worker(lab[0])
    message=WireMessage(json.dumps(clip).encode())
    w.process(message)
    assert evidence(lab)['state']=='AVAILABLE'
    w.process(message)
    assert len(w.consumer.commits)==2
    assert lab[-1]("SELECT count(*) FROM audit_events WHERE event_type='S4_AVAILABLE'")[0][0]==1


def test_offset_does_not_advance_if_database_fails(lab,monkeypatch):
    clip=deliver(lab)[1]
    w=worker(lab[0])
    def fail(*a,**k): raise RuntimeError('DB unavailable')
    monkeypatch.setattr(lab[0].repository.pool,'connection',fail)
    with pytest.raises(RuntimeError): w.process(WireMessage(json.dumps(clip).encode()))
    assert w.consumer.commits==[]


@pytest.mark.parametrize('body,topic',[(b'not-json','ods.s4.clip'),(b'\xff','ods.s4.clip'),(b'{"schema":"wrong"}','ods.s4.clip')])
def test_bad_wire_record_is_saved_before_commit(lab,body,topic):
    w=worker(lab[0]);w.process(WireMessage(body,topic))
    assert len(w.consumer.commits)==1
    assert lab[-1]('SELECT count(*) FROM ingestion_failures')[0][0]==1


def test_default_health_reports_adapter_disabled(client):
    s4=next(x for x in client.get('/api/v1/health').json()['components'] if x['name']=='s4')
    assert s4['status']=='DOWN' and 'desativado' in s4['detail']


def test_error_after_acceptance_and_refusal_prevents_retry(lab):
    reply,clip=deliver(lab)
    lab[0].receive(reply)
    failed=deepcopy(reply)
    failed['payload']={'status':'ERROR','error':{'code':'OUT_OF_BUFFER','message':'janela removida'}}
    assert lab[0].receive(failed)=='ACCEPTED'
    assert status(lab)=='FAILED'
    assert lab[0].receive(clip)=='IGNORED'
    assert evidence(lab)['state']=='UNAVAILABLE'


def test_enabled_worker_is_stopped_before_pool_closes(settings,monkeypatch):
    import threading
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from conftest import OfflineSubscriber
    monkeypatch.setenv('S4_ENABLED','1')
    stopped=threading.Event()
    class Worker:
        def __init__(self,*args):pass
        def run(self):stopped.wait()
        def parar(self):stopped.set()
        def health_snapshot(self):return {'name':'s4','status':'UP','detail':'Double lifecycle test'}
    with TestClient(create_app(settings,consumer_factory=OfflineSubscriber,s4_factory=Worker)) as c:
        assert c.get('/api/v1/health').json()['status']=='ONLINE'
        assert not stopped.is_set()
    assert stopped.is_set()


@pytest.mark.parametrize('identity',['bad\x00id','bad\ud800id'])
def test_unpersistable_identity_is_safely_rejected_before_offset_commit(lab,identity):
    clip=deliver(lab)[1]
    clip['message_id']=identity
    w=worker(lab[0]);w.process(WireMessage(json.dumps(clip).encode()))
    assert len(w.consumer.commits)==1
    assert lab[-1]('SELECT message_id FROM ingestion_failures')[0][0] is None
