"""S4 simulator only: descriptors, no captured image or hardware claim."""
import copy
import hashlib
from datetime import timedelta
from uuid import uuid4

from .db import utc_now,to_iso
from .s4_contracts import validate


class FakeS4:
    def __init__(self,*,session_id,clock=utc_now,error=None):
        self.session_id,self.clock,self.error=session_id,clock,error
        self.requests={}
        self.results={}
        self.sent=[]
        self.captures=0

    def send(self,topic,message):
        validate(message)
        if topic!='ods.s4.capture.command': raise ValueError('tópico incorreto')
        identity=message['message_id']
        self.sent.append(copy.deepcopy(message))
        if identity in self.requests:
            if self.requests[identity]!=message: raise ValueError('retry com conteúdo diferente')
            return
        self.requests[identity]=copy.deepcopy(message)
        clip=str(uuid4())
        payload=message['payload']
        body={'status':'ERROR','error':{'code':self.error,'message':self.error}} if self.error else {'status':'OK','clip_id':clip}
        reply=self.envelope('ods.s4.capture.reply','reply',body)
        reply['correlation_id']=identity
        results=[reply]
        if not self.error:
            self.captures+=1
            descriptor=self.envelope('ods.s4.clip','event',dict(clip_id=clip,event_id=payload['event_id'],
                media_type='SNAPSHOT',media_uri='https://s4.example.invalid/'+clip+'.png',
                start_at=payload['at'],end_at=payload['at'],hash_sha256=hashlib.sha256(b'explicit-simulated-media').hexdigest(),
                expires_at=to_iso(self.clock()+timedelta(seconds=60))))
            descriptor.update(source_id=payload['source_id'],session_id=self.session_id,
                              captured_at=payload['at'],sequence=self.captures-1,correlation_id=identity)
            results.append(descriptor)
        self.results[identity]=results

    def envelope(self,schema,kind,payload):
        return dict(message_id=str(uuid4()),schema=schema,schema_version='1.0',message_type=kind,
                    producer='S4',published_at=to_iso(self.clock()),payload=payload)

    def messages(self,command_id): return copy.deepcopy(self.results[str(command_id)])
