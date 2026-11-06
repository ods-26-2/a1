"""Durable S4 snapshot adapter over A1's existing commands/evidence/audit.

SENT is an attempted send, ACCEPTED a reply, COMPLETED a verified descriptor.
There is no media download or regeneration of the I8 inspection here.
"""
import copy
from datetime import timedelta
import math
from uuid import UUID

from psycopg.types.json import Jsonb

from .db import utc_now, to_iso
from .ingestion import diagnostic_event_for_jsonb
from .repository import AuditEntry
from .s4_contracts import validate, timestamp, browser_url, S4ContractError

TERMINAL = {'COMPLETED','REJECTED','FAILED','EXPIRED'}
QUERY = '''SELECT c.*, i.message_id AS origin_id, i.source_id AS origin_source,
    i.session_id AS origin_session, i.captured_at AS origin_at,
    e.descriptor AS descriptor FROM commands c
    JOIN inspections i USING (inspection_id) JOIN evidence e USING (inspection_id)'''


class S4Adapter:
    def __init__(self, repository, clock=utc_now, *, timeout=30, retry_interval=5):
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in (timeout,retry_interval)):
            raise ValueError('tempos S4 devem ser positivos e finitos')
        self.repository,self.clock=repository,clock
        self.timeout=timedelta(seconds=timeout)
        self.retry=timedelta(seconds=retry_interval)

    def _audit(self,conn,row,event,details):
        self.repository._audit(conn,row['inspection_id'],[AuditEntry(event,'S4',{'command_id':str(row['command_id']),**details})],self.clock())

    def _state(self,conn,row,status,evidence_state,detail,*,message=None,clip_id=None,url=None,expires=None):
        conn.execute('UPDATE commands SET status=%s,updated_at=%s WHERE command_id=%s',(status,self.clock(),row['command_id']))
        conn.execute('''UPDATE evidence SET state=%s,detail=%s,clip_id=COALESCE(%s,clip_id),
            url=%s,expires_at=COALESCE(%s,expires_at),updated_at=%s,
            descriptor=COALESCE(%s,descriptor) WHERE inspection_id=%s''',
            (evidence_state,detail,clip_id,url,expires,self.clock(),Jsonb(message) if message else None,row['inspection_id']))
        self._audit(conn,row,'S4_'+evidence_state,{'status':status,'detail':detail,'message':message})
        row['status']=status

    def expire(self):
        now=self.clock()
        with self.repository.pool.connection() as conn:
            rows=conn.execute(QUERY+''' WHERE c.target='S4' AND c.kind='SNAPSHOT_REQUEST'
                AND c.status IN ('PENDING','SENT','ACCEPTED') AND c.created_at<=%s
                FOR UPDATE OF c,e''',(now-self.timeout,)).fetchall()
            for row in rows:
                self._state(conn,row,'EXPIRED','UNAVAILABLE','S4 não concluiu o pedido no prazo; resultado da captura desconhecido.')
            rows=conn.execute(QUERY+''' WHERE c.target='S4' AND c.status='COMPLETED'
                AND e.state='AVAILABLE' AND e.expires_at<=%s FOR UPDATE OF c,e''',(now,)).fetchall()
            for row in rows:
                self._state(conn,row,'COMPLETED','EXPIRED','Evidência expirada conforme o descritor S4.')

    def dispatch_pending(self,send,*,limit=10):
        self.expire()
        sent=0
        for _ in range(limit):
            now=self.clock()
            with self.repository.pool.connection() as conn:
                row=conn.execute(QUERY+''' WHERE c.target='S4' AND c.kind='SNAPSHOT_REQUEST'
                    AND c.status IN ('PENDING','SENT')
                    AND (c.next_attempt_at IS NULL OR c.next_attempt_at<=%s)
                    ORDER BY c.created_at,c.command_id LIMIT 1 FOR UPDATE OF c,e SKIP LOCKED''',(now,)).fetchone()
                if row is None: break
                envelope=row['transport_envelope']
                if envelope is None:
                    envelope=validate(dict(schema='ods.s4.capture.command',schema_version='1.0',
                        message_type='command',message_id=str(row['command_id']),producer='A1',target='S4',
                        published_at=to_iso(row['created_at']),payload=dict(source_id=row['origin_source'],
                        media_type='SNAPSHOT',at=to_iso(row['origin_at']),event_id=str(row['origin_id']),
                        label='Inspeção '+row['inspection_id'])))
                conn.execute('''UPDATE commands SET status='SENT',transport_envelope=%s,
                    next_attempt_at=%s,updated_at=%s WHERE command_id=%s''',
                    (Jsonb(envelope),now+self.retry,now,row['command_id']))
                if row['status']=='PENDING': self._audit(conn,row,'S4_SENT',{'message':envelope})
            # Publish after committing. Failure may mean delivered; retry the same ID.
            send('ods.s4.capture.command',copy.deepcopy(envelope))
            sent+=1
        return sent

    def reject(self,message,reason):
        identity=message.get('message_id') if isinstance(message,dict) else None
        if not isinstance(identity,str) or '\x00' in identity:
            identity=None
        if identity is not None:
            try: identity.encode('utf-8')
            except UnicodeEncodeError: identity=None
        reason=reason.encode('utf-8',errors='backslashreplace').decode('utf-8').replace('\x00','\\u0000')
        self.repository.record_failure(received_at=self.clock(),message_id=identity,
            reason='S4: '+reason,event=diagnostic_event_for_jsonb(message))
        return 'REJECTED'

    def receive(self,message):
        try:
            message=validate(message)
            if message['schema']=='ods.s4.capture.command': raise S4ContractError('esperada reply ou descritor')
            return self._receive(message)
        except (S4ContractError,ValueError) as exc:
            return self.reject(message,str(exc))

    def _receive(self,message):
        payload=message['payload']
        is_reply=message['schema']=='ods.s4.capture.reply'
        correlation=message.get('correlation_id')
        event_id=payload.get('event_id') if not is_reply else None
        if not correlation and not event_id: return 'IGNORED'
        with self.repository.pool.connection() as conn:
            if correlation:
                row=conn.execute(QUERY+" WHERE c.command_id=%s AND c.target='S4' AND c.kind='SNAPSHOT_REQUEST' FOR UPDATE OF c,e",(correlation,)).fetchone()
            else:
                row=conn.execute(QUERY+" WHERE i.message_id=%s AND c.target='S4' AND c.kind='SNAPSHOT_REQUEST' FOR UPDATE OF c,e",(event_id,)).fetchone()
            if row is None: return 'IGNORED'
            if row['status']=='PENDING': raise S4ContractError('resposta a pedido ainda não enviado')
            if row['status'] in {'REJECTED','FAILED','EXPIRED'}: return 'IGNORED'
            if self.clock()>=row['created_at']+self.timeout and row['status']!='COMPLETED':
                self._state(conn,row,'EXPIRED','UNAVAILABLE','Resposta S4 recebida após o prazo; não usada.')
                return 'IGNORED'
            if is_reply:
                if row['status']=='COMPLETED': return 'DUPLICATE'
                if payload['status']=='ERROR':
                    status='FAILED' if row['status']=='ACCEPTED' else 'REJECTED'
                    self._state(conn,row,status,'UNAVAILABLE',payload['error']['code']+': '+payload['error']['message'],message=message)
                    return 'ACCEPTED'
                clip_id=payload['clip_id']
                if row['response_clip_id'] is not None and UUID(clip_id)!=row['response_clip_id']:
                    raise S4ContractError('reply alterou clip_id do pedido')
                if row['status']=='ACCEPTED': return 'DUPLICATE'
                conn.execute("UPDATE commands SET status='ACCEPTED',response_clip_id=%s,updated_at=%s WHERE command_id=%s",(clip_id,self.clock(),row['command_id']))
                self._audit(conn,row,'S4_ACCEPTED',{'clip_id':clip_id})
                return 'ACCEPTED'
            if (message['source_id']!=row['origin_source'] or UUID(message['session_id'])!=row['origin_session']
                    or (event_id and UUID(event_id)!=row['origin_id']) or payload['media_type']!='SNAPSHOT'
                    or timestamp(payload['start_at'])!=row['origin_at'] or timestamp(payload['end_at'])!=row['origin_at']
                    or timestamp(message['captured_at'])!=row['origin_at']):
                raise S4ContractError('descritor S4 não corresponde à fonte/sessão/instante da inspeção')
            if row['response_clip_id'] is not None and UUID(payload['clip_id'])!=row['response_clip_id']:
                raise S4ContractError('clip_id do descritor difere da reply')
            if row['status']=='COMPLETED':
                if row['descriptor']['payload']!=payload: raise S4ContractError('descritor repetido com conteúdo divergente')
                return 'DUPLICATE'
            expires=timestamp(payload['expires_at'])
            if expires<=row['origin_at']: raise S4ContractError('expiração anterior à captura')
            url=browser_url(payload['media_uri'])
            state='AVAILABLE' if url else 'UNAVAILABLE'
            detail='Descritor S4 correlacionado; integridade da mídia ainda não verificada por A1.' if url else 'Descritor recebido; URI exige acesso HTTP(S) controlado de S4.'
            if expires<=self.clock(): state,detail,url='EXPIRED','Evidência já expirada ao chegar.',None
            conn.execute('UPDATE commands SET response_clip_id=%s WHERE command_id=%s',(payload['clip_id'],row['command_id']))
            self._state(conn,row,'COMPLETED',state,detail,message=message,clip_id=payload['clip_id'],url=url,expires=expires)
            return 'ACCEPTED'
