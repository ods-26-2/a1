"""Prepared A1/S5 EVENT adapter. Explicit caller/transport, no implicit activation.

Queries are independent of inspections. S5 owns aggregates; this adapter never
manufactures S5/S2 events from I8 classifications or sums overlapping windows.
"""
import copy
import json
import math
from datetime import timedelta,datetime,timezone
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator,FormatChecker
from referencing import Registry,Resource
from psycopg.types.json import Jsonb

from .db import utc_now,to_iso
from .ingestion import diagnostic_event_for_jsonb

SCHEMA_DIR=Path(__file__).resolve().parents[1]/'shared/schemas/s5'
SCHEMAS=[json.loads(p.read_text()) for p in SCHEMA_DIR.glob('*.json')]
REGISTRY=Registry().with_resources((s['$id'],Resource.from_contents(s)) for s in SCHEMAS)
VALIDATORS={s['title']:Draft202012Validator(s,registry=REGISTRY,format_checker=FormatChecker())
            for s in SCHEMAS if s['title'].startswith('ods.')}
SECONDS={'1m':60,'15m':900,'1h':3600,'1d':86400}
TERMINAL={'COMPLETED','REJECTED','EXPIRED'}


class S5ContractError(ValueError):pass


def instant(value):
    # S5 schemas enforce canonical milliseconds/Z before reaching this helper.
    try:return datetime.strptime(value,'%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
    except (ValueError,TypeError) as exc:raise S5ContractError('data S5 inválida') from exc


def uuid(value):
    try:
        if not isinstance(value,str) or UUID(value).version!=4:raise ValueError()
    except (ValueError,TypeError,AttributeError) as exc:raise S5ContractError('UUID v4 obrigatório') from exc


def validate(message):
    if diagnostic_event_for_jsonb(message) is None:raise S5ContractError('JSON S5 não persistível')
    try:
        schema=message['schema']
        VALIDATORS[schema].validate(message)
        if message['schema_version'] not in {'1.0','1.1'}:raise S5ContractError('versão S5 não suportada')
        uuid(message['message_id']);instant(message['published_at'])
        if schema=='ods.s5.metrics.query':
            if message['producer']!='A1' or message['payload']['metric']!='EVENT':
                raise S5ContractError('A1 prepara somente consultas EVENT para S5')
            q=message['payload'];start=instant(q['period_start_at']);end=instant(q['period_end_at'])
            if end<=start or (end-start).total_seconds()>1000*SECONDS[q['granularity']]:
                raise S5ContractError('período deve ser positivo e ter no máximo 1000 janelas')
            # Activity profile is outside this A1 slice; use the stable 1.0 query.
            if 'profile' in q or 'timezone' in q:raise S5ContractError('perfil de atividade não faz parte deste adaptador EVENT')
        elif schema=='ods.s5.metrics.reply':
            uuid(message['correlation_id'])
        else:
            uuid(message['session_id']);instant(message['captured_at'])
            _metric(message['payload'])
        return message
    except S5ContractError:raise
    except Exception as exc:raise S5ContractError(str(exc)) from exc


def _metric(payload):
    start=instant(payload['window_start_at']);end=instant(payload['window_end_at'])
    if end<=start or (end-start).total_seconds()!=SECONDS[payload['granularity']]:
        raise S5ContractError('janela EVENT incompatível com a granularidade')
    if payload['uncertain_count']>payload['count']:raise S5ContractError('uncertain_count excede count')


class S5Adapter:
    def __init__(self,repository,clock=utc_now,*,timeout=30,retry_interval=5):
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in (timeout,retry_interval)):
            raise ValueError('tempos S5 devem ser positivos e finitos')
        self.repository,self.clock=repository,clock
        self.timeout,self.retry=timedelta(seconds=timeout),timedelta(seconds=retry_interval)

    def request(self,*,query_id,period_start_at,period_end_at,granularity,event_type=None,zone_id=None,object_class=None):
        uuid(str(query_id))
        payload=dict(metric='EVENT',period_start_at=period_start_at,period_end_at=period_end_at,granularity=granularity)
        for key,value in [('event_type',event_type),('zone_id',zone_id),('class',object_class)]:
            if value is not None:payload[key]=value
        now=self.clock()
        envelope=validate(dict(message_id=str(query_id),schema='ods.s5.metrics.query',schema_version='1.0',
            message_type='query',producer='A1',target='S5',published_at=to_iso(now),payload=payload))
        with self.repository.pool.connection() as conn:
            row=conn.execute('''INSERT INTO s5_queries(query_id,status,envelope,created_at,deadline_at)
                VALUES(%s,'PENDING',%s,%s,%s) ON CONFLICT(query_id) DO NOTHING RETURNING *''',
                (query_id,Jsonb(envelope),now,now+self.timeout)).fetchone()
            if row is None:
                row=conn.execute('SELECT * FROM s5_queries WHERE query_id=%s FOR UPDATE',(query_id,)).fetchone()
                if row['envelope']['payload']!=payload:raise S5ContractError('query_id já usado com outra intenção')
            return row

    def get(self,query_id):
        with self.repository.pool.connection() as conn:
            return conn.execute('SELECT * FROM s5_queries WHERE query_id=%s',(query_id,)).fetchone()

    def expire(self):
        with self.repository.pool.connection() as conn:
            conn.execute("UPDATE s5_queries SET status='EXPIRED' WHERE status IN ('PENDING','SENT') AND deadline_at<=%s",(self.clock(),))

    def dispatch_pending(self,send,*,limit=10):
        self.expire();sent=0
        for _ in range(limit):
            now=self.clock()
            with self.repository.pool.connection() as conn:
                row=conn.execute('''SELECT * FROM s5_queries WHERE status IN ('PENDING','SENT')
                    AND (next_attempt_at IS NULL OR next_attempt_at<=%s)
                    ORDER BY created_at,query_id LIMIT 1 FOR UPDATE SKIP LOCKED''',(now,)).fetchone()
                if row is None:break
                conn.execute("UPDATE s5_queries SET status='SENT',next_attempt_at=%s WHERE query_id=%s",(now+self.retry,row['query_id']))
                envelope=copy.deepcopy(row['envelope'])
            send('ods.s5.metrics.query',envelope)
            sent+=1
        return sent

    def reject(self,message,reason):
        identity=message.get('message_id') if isinstance(message,dict) else None
        if not isinstance(identity,str) or '\x00' in identity:identity=None
        if identity is not None:
            try:identity.encode('utf-8')
            except UnicodeEncodeError:identity=None
        safe_reason=reason.encode('utf-8',errors='backslashreplace').decode('utf-8').replace('\x00','\\u0000')
        self.repository.record_failure(received_at=self.clock(),message_id=identity,reason='S5: '+safe_reason,event=diagnostic_event_for_jsonb(message))
        return 'REJECTED'

    def receive(self,message):
        try:
            message=validate(message)
            if message['schema']=='ods.s5.metrics.query':raise S5ContractError('entrada A1 deve ser reply/event_metrics')
            if message['schema']=='ods.s5.event_metrics':return self._event(message)
            return self._reply(message)
        except S5ContractError as exc:return self.reject(message,str(exc))

    def _reply(self,message):
        payload=message['payload']
        with self.repository.pool.connection() as conn:
            row=conn.execute('SELECT * FROM s5_queries WHERE query_id=%s FOR UPDATE',(message['correlation_id'],)).fetchone()
            if row is None:return 'IGNORED'
            if row['status']=='PENDING':raise S5ContractError('reply de consulta ainda não enviada')
            if row['status'] in TERMINAL:return 'DUPLICATE' if row['status']!='EXPIRED' else 'IGNORED'
            if self.clock()>=row['deadline_at']:
                conn.execute("UPDATE s5_queries SET status='EXPIRED' WHERE query_id=%s",(row['query_id'],));return 'IGNORED'
            if payload['status']=='OK':
                q=row['envelope']['payload'];previous=None
                for item in payload['series']:
                    if 'event_type' not in item:raise S5ContractError('série ZONE não responde consulta EVENT')
                    _metric(item)
                    start=instant(item['window_start_at']);end=instant(item['window_end_at'])
                    if (item['granularity']!=q['granularity'] or start<instant(q['period_start_at'])
                            or end>instant(q['period_end_at']) or (previous is not None and start<previous)):
                        raise S5ContractError('série fora do período/granularidade/ordem solicitados')
                    for key in ('event_type','zone_id','class'):
                        if key in q and item.get(key)!=q[key]:raise S5ContractError('filtro da série difere da consulta')
                    previous=start
                status='COMPLETED'
            else:status='REJECTED'
            conn.execute('UPDATE s5_queries SET status=%s,response=%s WHERE query_id=%s',(status,Jsonb(message),row['query_id']))
            return 'ACCEPTED'

    def _event(self,message):
        with self.repository.pool.connection() as conn:
            row=conn.execute('''INSERT INTO s5_metric_events(message_id,envelope,received_at)
                VALUES(%s,%s,%s) ON CONFLICT(message_id) DO NOTHING RETURNING message_id''',
                (message['message_id'],Jsonb(message),self.clock())).fetchone()
            if row is None:
                existing=conn.execute('SELECT envelope FROM s5_metric_events WHERE message_id=%s',(message['message_id'],)).fetchone()
                if existing['envelope']!=message:raise S5ContractError('message_id S5 repetido com conteúdo diferente')
                return 'DUPLICATE'
            return 'ACCEPTED'

    def events(self,*,limit=100):
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError('limit deve estar entre 1 e 1000')
        with self.repository.pool.connection() as conn:
            return conn.execute('SELECT envelope FROM s5_metric_events ORDER BY received_at,message_id LIMIT %s',(limit,)).fetchall()
