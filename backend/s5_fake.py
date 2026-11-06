"""Contract S5 simulator: caller supplies synthetic aggregates explicitly."""
import copy
from uuid import uuid4
from .db import utc_now,to_iso
from .s5 import validate


class FakeS5:
    def __init__(self,*,series=None,error=None,clock=utc_now):
        self.series=copy.deepcopy(series if series is not None else [])
        self.error,self.clock=error,clock
        self.sent=[]
        self.responses={}

    def send(self,topic,message):
        validate(message)
        if topic!='ods.s5.metrics.query':raise ValueError('tópico incorreto')
        self.sent.append(copy.deepcopy(message))
        payload={'status':'ERROR','error':{'code':self.error,'message':self.error}} if self.error else {'status':'OK','series':copy.deepcopy(self.series)}
        reply=dict(message_type='reply',message_id=str(uuid4()),schema='ods.s5.metrics.reply',schema_version='1.1',
                   producer='S5',published_at=to_iso(self.clock()),correlation_id=message['message_id'],payload=payload)
        # Actual S5 answers repeated queries again; response IDs can legitimately differ.
        self.responses[message['message_id']]=validate(reply)

    def reply(self,query_id):return copy.deepcopy(self.responses[str(query_id)])
