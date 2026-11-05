"""Real PostgreSQL ingestion through the subscriber, with Kafka I/O doubled."""
import json

from backend.config import KafkaSettings
from backend.fake_producer import default_events
from backend.kafka_client import A1KafkaConsumer
from test_kafka_transport import ConsumerDouble, Message


def subscriber(service, messages):
    trace, clients = [], []
    def factory(config):
        clients.append(ConsumerDouble(config, trace, messages))
        return clients[-1]
    worker = A1KafkaConsumer(service, consumer_factory=factory,
        settings=KafkaSettings(topic='test-piece-analysis', retry_attempts=3,
                               retry_initial=.001, retry_max=.002))
    clients[0].stop = worker.parar
    return worker, clients[0]


def test_candidate_and_duplicate_commit_only_after_real_database_write(client, sql):
    event = default_events(False)[0]
    message = json.dumps(event).encode()
    worker, kafka = subscriber(client.app.state.services.ingestion,
                               [Message(message, 0), Message(message, 1)])
    worker.comecar_a_consumir()
    assert kafka.commits == [0, 1]
    assert sql('SELECT count(*) FROM inspections')[0][0] == 1
    assert sql('SELECT count(*) FROM commands')[0][0] == 1
    assert sql("SELECT count(*) FROM audit_events WHERE event_type = 'INGESTED'")[0][0] == 1
    assert sql("SELECT raw_event->>'occurred_at' FROM inspections")[0][0] == event['occurred_at']


def test_transient_repository_failure_retries_and_saves_once(client, sql, monkeypatch):
    repository = client.app.state.services.repository
    original, calls = repository.save_ingested, []
    def fail_once(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('temporary database failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(repository, 'save_ingested', fail_once)
    raw = json.dumps(default_events(False)[0]).encode()
    worker, kafka = subscriber(client.app.state.services.ingestion, [Message(raw)])
    worker.comecar_a_consumir()
    assert len(calls) == 2 and kafka.commits == [0]
    assert sql('SELECT count(*) FROM inspections')[0][0] == 1


def test_bad_wire_record_is_logged_in_real_database_before_commit(client, sql):
    worker, kafka = subscriber(client.app.state.services.ingestion, [Message(b'\xff', 7)])
    worker.comecar_a_consumir()
    assert kafka.commits == [7]
    assert sql('SELECT count(*) FROM inspections')[0][0] == 0
    assert 'offset=7' in sql('SELECT reason FROM ingestion_failures')[0][0]


def test_failed_rejection_storage_blocks_offset_and_later_record(client, sql, monkeypatch):
    def fail(**kwargs): raise RuntimeError('failure store offline')
    monkeypatch.setattr(client.app.state.services.repository, 'record_failure', fail)
    worker, kafka = subscriber(client.app.state.services.ingestion,
                               [Message(b'invalid', 0), Message(b'{}', 1)])
    worker.comecar_a_consumir()
    assert kafka.commits == [] and len(kafka.messages) == 1
    assert sql('SELECT count(*) FROM inspections')[0][0] == 0
