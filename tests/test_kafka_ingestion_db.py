"""Real PostgreSQL ingestion through the subscriber, with Kafka I/O doubled."""
import copy
import json
from uuid import uuid4

import pytest

from backend.config import KafkaSettings
from backend.contracts import validate_piece_analysis
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


def test_final_and_duplicate_commit_only_after_real_database_write(client, sql):
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


def test_jsonb_incompatible_records_are_logged_and_do_not_block_next_message(client, sql):
    valid = json.dumps(default_events(False)[0]).encode()
    messages = [
        Message(b'{"x": 1e400}', 0),
        Message(b'{"x": "\\u0000"}', 1),
        Message(b'{"x": "\\ud800"}', 2),
        Message(valid, 3),
    ]
    worker, kafka = subscriber(client.app.state.services.ingestion, messages)
    worker.comecar_a_consumir()
    assert kafka.commits == [0, 1, 2, 3]
    assert sql('SELECT count(*) FROM ingestion_failures')[0][0] == 3
    assert sql('SELECT count(*) FROM inspections')[0][0] == 1


def test_failed_rejection_storage_blocks_offset_and_later_record(client, sql, monkeypatch):
    def fail(**kwargs): raise RuntimeError('failure store offline')
    monkeypatch.setattr(client.app.state.services.repository, 'record_failure', fail)
    worker, kafka = subscriber(client.app.state.services.ingestion,
                               [Message(b'invalid', 0), Message(b'{}', 1)])
    worker.comecar_a_consumir()
    assert kafka.commits == [] and len(kafka.messages) == 1
    assert sql('SELECT count(*) FROM inspections')[0][0] == 0


OVERSIZED_METADATA = [
    pytest.param('sequence', 2**63, 'sequence', id='sequence'),
    pytest.param('frame_index', 2**63, 'payload.frame_index', id='frame_index'),
    pytest.param('detection_id', 2**31, 'payload.detection_id', id='detection_id'),
    pytest.param('bbox', [2**31, 0, 2**31 + 1, 10], 'payload.bbox[0]', id='bbox_x_min'),
    pytest.param('bbox', [0, 2**31, 10, 2**31 + 1], 'payload.bbox[1]', id='bbox_y_min'),
    pytest.param('bbox', [0, 0, 2**31, 10], 'payload.bbox[2]', id='bbox_x_max'),
    pytest.param('bbox', [0, 0, 10, 2**31], 'payload.bbox[3]', id='bbox_y_max'),
]


@pytest.mark.parametrize('version', ['1.0', '2.0'])
@pytest.mark.parametrize('field,value,path', OVERSIZED_METADATA)
def test_oversized_metadata_is_rejected_before_next_message(client, sql, version, field, value, path):
    valid = default_events(False, version)[0]
    invalid = copy.deepcopy(valid)
    invalid['message_id'] = str(uuid4())
    target = invalid if field == 'sequence' else invalid['payload']
    target[field] = value
    # The shared contract remains unchanged; storage bounds belong to A1 ingestion.
    validate_piece_analysis(invalid)
    worker, kafka = subscriber(client.app.state.services.ingestion, [
        Message(json.dumps(invalid).encode(), 0), Message(json.dumps(valid).encode(), 1),
    ])
    original_commit = kafka.commit

    def commit_after_durable_result(*, message, asynchronous):
        if message.offset() == 0:
            assert sql('SELECT count(*) FROM ingestion_failures')[0][0] == 1
        else:
            assert sql('SELECT count(*) FROM inspections')[0][0] == 1
        return original_commit(message=message, asynchronous=asynchronous)

    kafka.commit = commit_after_durable_result
    worker.comecar_a_consumir()
    assert kafka.commits == [0, 1] and kafka.closed
    assert sql('SELECT count(*) FROM inspections')[0][0] == 1
    assert sql('SELECT count(*) FROM commands')[0][0] == 1
    assert sql("SELECT count(*) FROM audit_events WHERE event_type='INGESTED'")[0][0] == 1
    failures = sql('SELECT message_id, reason, event FROM ingestion_failures')
    assert len(failures) == 1
    assert failures[0][0] == invalid['message_id']
    assert path in failures[0][1] and 'armazenamento' in failures[0][1]
    assert failures[0][2] == invalid


@pytest.mark.parametrize('version', ['1.0', '2.0'])
def test_maximum_storage_integers_remain_accepted(client, sql, version):
    event = copy.deepcopy(default_events(False, version)[0])
    event['sequence'] = 2**63 - 1
    event['payload'].update(frame_index=2**63 - 1, detection_id=2**31 - 1,
                            bbox=[2**31 - 2, 2**31 - 2, 2**31 - 1, 2**31 - 1])
    worker, kafka = subscriber(client.app.state.services.ingestion,
                               [Message(json.dumps(event).encode())])
    worker.comecar_a_consumir()
    assert kafka.commits == [0]
    assert sql('SELECT sequence, frame_index, detection_id, bbox FROM inspections') == [
        (2**63 - 1, 2**63 - 1, 2**31 - 1, event['payload']['bbox'])]
    assert sql('SELECT count(*) FROM ingestion_failures')[0][0] == 0


def test_failed_storage_rejection_never_commits_or_skips_message(client, sql, monkeypatch):
    valid = default_events(False)[0]
    invalid = copy.deepcopy(valid)
    invalid['payload']['detection_id'] = 2**31
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('failure store offline')

    monkeypatch.setattr(client.app.state.services.repository, 'record_failure', fail)
    worker, kafka = subscriber(client.app.state.services.ingestion, [
        Message(json.dumps(invalid).encode(), 0), Message(json.dumps(valid).encode(), 1),
    ])
    worker.comecar_a_consumir()
    assert len(calls) == 3
    assert kafka.commits == [] and len(kafka.messages) == 1
    assert sql('SELECT count(*) FROM inspections')[0][0] == 0
