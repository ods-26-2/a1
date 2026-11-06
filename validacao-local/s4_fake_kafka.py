"""Disposable Kafka S4 simulator, serving one explicitly synthetic PNG."""
import base64
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit

from confluent_kafka import Consumer,Producer
from backend.s4_fake import FakeS4

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jCY0AAAAASUVORK5CYII=')
clips=set()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/health':
            body=b'{"mode":"SIMULATED"}'
            self.send_response(200);self.end_headers();self.wfile.write(body);return
        if path.startswith('/media/') and path[7:] in clips:
            self.send_response(200);self.send_header('Content-Type','image/png');self.end_headers();self.wfile.write(PNG);return
        self.send_error(404)
    def log_message(self,*args): pass


def main():
    threading.Thread(target=ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever,daemon=True).start()
    broker=os.environ['KAFKA_BROKER_URL']
    public=os.getenv('S4_FAKE_PUBLIC_URL','http://127.0.0.1:18084')
    fake=FakeS4(session_id=os.environ['S4_FAKE_SESSION_ID'])
    consumer=Consumer({'bootstrap.servers':broker,'group.id':'s4-fake-lab','auto.offset.reset':'earliest',
        'enable.auto.commit':False,'allow.auto.create.topics':False})
    producer=Producer({'bootstrap.servers':broker,'enable.idempotence':True,'acks':'all','delivery.timeout.ms':5000})
    consumer.subscribe(['ods.s4.capture.command'])
    try:
        while True:
            msg=consumer.poll(.5)
            if msg is None: continue
            if msg.error(): raise RuntimeError(str(msg.error()))
            command=json.loads(msg.value())
            fake.send(msg.topic(),command)
            receipts=[]
            for response in fake.messages(command['message_id']):
                if response['schema']=='ods.s4.clip':
                    name=response['payload']['clip_id']+'.png'
                    clips.add(name)
                    response['payload']['media_uri']=public+'/media/'+name
                    response['payload']['hash_sha256']=hashlib.sha256(PNG).hexdigest()
                producer.produce(response['schema'],key=command['message_id'],value=json.dumps(response).encode(),
                    on_delivery=lambda error,message:receipts.append(error))
            if producer.flush(5) or len(receipts)!=2 or any(receipts): raise RuntimeError('fake delivery failed')
            consumer.commit(message=msg,asynchronous=False)
            print(json.dumps({'mode':'SIMULATED','command_id':command['message_id'],'synthetic_captures':fake.captures}),flush=True)
    finally:
        consumer.close();producer.flush(5)

if __name__=='__main__':main()
