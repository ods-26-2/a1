"""Opt-in S4 Kafka worker; offsets advance only after durable processing."""
import json
import logging
import os
import threading
import time

from confluent_kafka import Consumer, Producer, KafkaException

LOG=logging.getLogger(__name__)
TOPICS=['ods.s4.capture.reply','ods.s4.clip']
COMMAND='ods.s4.capture.command'


class S4KafkaWorker:
    def __init__(self,adapter,broker,*,consumer_factory=Consumer,producer_factory=Producer):
        self.adapter,self.broker=adapter,broker
        self.stop=threading.Event()
        self.lock=threading.Lock()
        self.detail='Adaptador S4 iniciando.'
        self.running=self.assigned=self.connected=False
        self.fatal=False
        self.consumer=consumer_factory({'bootstrap.servers':broker,'group.id':os.getenv('S4_GROUP_ID','a1-s4-v1'),
            'auto.offset.reset':'earliest','enable.auto.commit':False,'enable.auto.offset.store':False,
            'allow.auto.create.topics':False,'session.timeout.ms':10000,'socket.timeout.ms':5000})
        try:
            self.producer=producer_factory({'bootstrap.servers':broker,'enable.idempotence':True,'acks':'all',
                'allow.auto.create.topics':False,'delivery.timeout.ms':5000,'socket.timeout.ms':5000})
        except BaseException:
            self.consumer.close()
            raise

    def _assign(self,consumer,partitions): self.assigned=True
    def _revoke(self,consumer,partitions): self.assigned=False

    def send(self,topic,message):
        receipt=[]
        def delivered(error,msg): receipt.append(error)
        self.producer.produce(topic,key=message['message_id'],value=json.dumps(message,allow_nan=False).encode(),on_delivery=delivered)
        remaining=self.producer.flush(5)
        if remaining or not receipt or receipt[0] is not None:
            raise RuntimeError('Entrega S4 não confirmada; pedido retido para reenvio')

    def process(self,msg):
        """A DB exception escapes: no commit and no next message bypass."""
        try:
            if msg.topic() not in TOPICS: raise ValueError('tópico S4 inválido')
            message=json.loads(msg.value().decode('utf-8'))
            if message.get('schema')!=msg.topic(): raise ValueError('schema difere do tópico S4')
        except (ValueError,UnicodeError,AttributeError,TypeError,RecursionError) as exc:
            self.adapter.reject(None,f'JSON/tópico inválido: {exc}; offset={msg.offset()}')
        else:
            self.adapter.receive(message)
        offsets=self.consumer.commit(message=msg,asynchronous=False)
        if any(getattr(p,'error',None) for p in offsets or []): raise RuntimeError('Commit S4 não confirmado')

    def run(self):
        try:
            if self.stop.is_set(): return
            self.running=True
            self.consumer.subscribe(TOPICS,on_assign=self._assign,on_revoke=self._revoke,on_lost=self._revoke)
            probe_at=0
            while not self.stop.is_set():
                if time.monotonic()>=probe_at:
                    try:
                        metadata=self.consumer.list_topics(timeout=2)
                        if not metadata.brokers or any(t not in metadata.topics or metadata.topics[t].error for t in TOPICS+[COMMAND]):
                            raise RuntimeError('Tópicos S4 indisponíveis; provisionar explicitamente')
                        self.connected=True
                    except (KafkaException,RuntimeError) as exc:
                        self.connected=False
                        self.detail=str(exc)
                    probe_at=time.monotonic()+5
                msg=self.consumer.poll(.2)
                if msg is not None:
                    if msg.error():
                        self.connected=False
                        self.detail=str(msg.error())
                        self.stop.wait(.2)
                        continue
                    if self.stop.is_set(): break
                    self.process(msg)
                if not self.connected:
                    self.adapter.expire()
                    continue
                try:
                    self.adapter.dispatch_pending(self.send,limit=1)
                except (BufferError,KafkaException,RuntimeError) as exc:
                    # An uncertain send keeps its durable ID and next retry time.
                    self.connected=False
                    self.detail=str(exc)
                else:
                    self.detail='Transporte S4 conectado; disponibilidade/correção do serviço exige prova própria.'
        except Exception as exc:
            self.fatal=True
            self.detail=f'Adaptador S4 parou: {type(exc).__name__}: {exc}'
            LOG.exception(self.detail)
        finally:
            self.running=False
            self.connected=False
            self.consumer.close()
            self.producer.flush(5)

    def parar(self): self.stop.set()

    def health_snapshot(self):
        return {'name':'s4','status':'UP' if self.running and self.assigned and self.connected and not self.fatal and not self.stop.is_set() else 'DOWN',
                'detail':self.detail}
