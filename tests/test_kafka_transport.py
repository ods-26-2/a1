"""Kafka boundary regression tests: no network, database or ML required."""
import copy
import json
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.config import KafkaSettings
from backend.contracts import validate_piece_analysis
from backend.fake_producer import default_events, main, publish_events, refresh
from backend.ingestion import IngestResult, IngestStatus, IngestionService
from backend.kafka_client import A1KafkaConsumer


class Message:
    def __init__(self, value=b'{}', offset=0):
        self.raw, self.index = value, offset

    def value(self): return self.raw
    def offset(self): return self.index
    def topic(self): return 'test-piece-analysis'
    def partition(self): return 0
    def error(self): return None


class ConsumerDouble:
    def __init__(self, config, trace, messages=()):
        self.config, self.trace = config, trace
        self.messages = list(messages)
        self.commits = []
        self.commit_errors = []
        self.closed = False
        self.stop = lambda: None

    def subscribe(self, topics, **callbacks):
        self.topics = topics
        callbacks['on_assign'](self, [])

    def list_topics(self, **kwargs):
        return SimpleNamespace(brokers={1: object()}, topics={
            self.topics[0]: SimpleNamespace(error=None)})

    def poll(self, timeout):
        if not self.messages:
            self.stop()
            return None
        msg = self.messages.pop(0)
        self.trace.append(('poll', msg.offset()))
        return msg

    def commit(self, *, message, asynchronous):
        assert asynchronous is False
        self.trace.append(('commit', message.offset()))
        if self.commit_errors:
            error = self.commit_errors.pop(0)
            if isinstance(error, Exception):
                raise error
            if error:
                return [SimpleNamespace(error=error)]
        self.commits.append(message.offset())
        return [SimpleNamespace(error=None)]

    def close(self):
        self.trace.append(('close',))
        self.closed = True


class IngestionDouble:
    def __init__(self, trace, statuses=(IngestStatus.ACCEPTED,)):
        self.trace, self.statuses = trace, list(statuses)
        self.calls = 0
        self.rejections = []
        self.stop_on_success = None

    def ingest(self, event):
        self.calls += 1
        self.trace.append(('persist', self.calls))
        outcome = self.statuses[min(self.calls - 1, len(self.statuses) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        if self.stop_on_success:
            self.stop_on_success()
        return IngestResult(outcome, inspection_id='test-inspection')

    def reject_transport_message(self, reason):
        self.trace.append(('reject-durable',))
        self.rejections.append(reason)
        return IngestResult(IngestStatus.REJECTED, reason=reason)


def setup_worker(messages=(), statuses=(IngestStatus.ACCEPTED,)):
    trace = []
    service = IngestionDouble(trace, statuses)
    clients = []
    settings = KafkaSettings(topic='test-piece-analysis', retry_attempts=3,
                             retry_initial=.001, retry_max=.002)
    def factory(config):
        client = ConsumerDouble(config, trace, messages)
        clients.append(client)
        return client
    worker = A1KafkaConsumer(service, settings=settings, consumer_factory=factory)
    clients[0].stop = worker.parar
    return worker, clients[0], service, trace


def test_configuration_disables_both_automatic_offset_mechanisms(monkeypatch):
    monkeypatch.setenv('KAFKA_BROKER_URL', 'localhost:19092')
    monkeypatch.setenv('KAFKA_TOPIC', 'test-piece-analysis')
    monkeypatch.setenv('KAFKA_GROUP_ID', 'isolated-test')
    settings = KafkaSettings.from_env()
    assert (settings.broker_url, settings.topic, settings.group_id) == (
        'localhost:19092', 'test-piece-analysis', 'isolated-test')
    _, client, _, _ = setup_worker()
    assert client.config['enable.auto.commit'] is False
    assert client.config['enable.auto.offset.store'] is False
    assert client.config['allow.auto.create.topics'] is False


@pytest.mark.parametrize('field,value', [
    ('retry_attempts', 0), ('retry_attempts', 11), ('retry_max', 11),
    ('retry_initial', float('nan')), ('shutdown_timeout', 0), ('topic', ''),
])
def test_invalid_configuration_fails_before_start(field, value):
    with pytest.raises(ValueError):
        replace(KafkaSettings(), **{field: value})


@pytest.mark.parametrize('status', list(IngestStatus))
def test_commit_follows_each_durable_outcome(status):
    worker, client, _, trace = setup_worker([Message()], [status])
    worker.comecar_a_consumir()
    assert trace.index(('persist', 1)) < trace.index(('commit', 0)) < trace.index(('close',))
    assert client.commits == [0]


def test_transient_database_failure_retries_same_record_before_next_poll():
    worker, client, service, trace = setup_worker(
        [Message(offset=0), Message(offset=1)],
        [RuntimeError('database offline'), IngestStatus.ACCEPTED])
    worker.comecar_a_consumir()
    assert client.commits == [0, 1]
    assert service.calls == 3
    assert trace.index(('persist', 2)) < trace.index(('commit', 0)) < trace.index(('poll', 1))


def test_permanent_database_failure_never_commits_or_polls_later_message():
    worker, client, service, trace = setup_worker(
        [Message(offset=0), Message(offset=1)], [RuntimeError('database offline')])
    worker.comecar_a_consumir()
    assert service.calls == 3
    assert client.commits == []
    assert ('poll', 1) not in trace
    assert client.closed and worker.health_snapshot()['status'] == 'DOWN'


@pytest.mark.parametrize('commit_error', [RuntimeError('broker offline'), 'partition commit error'])
def test_commit_retry_does_not_repeat_persistence(commit_error):
    worker, client, service, trace = setup_worker([Message()])
    client.commit_errors = [commit_error]
    worker.comecar_a_consumir()
    assert service.calls == 1 and client.commits == [0]
    assert trace.count(('commit', 0)) == 2


def test_failed_commit_never_advances_to_later_message():
    worker, client, service, trace = setup_worker([Message(offset=0), Message(offset=1)])
    client.commit_errors = [RuntimeError('offline')] * 3
    worker.comecar_a_consumir()
    assert service.calls == 1 and client.commits == []
    assert ('poll', 1) not in trace


@pytest.mark.parametrize('raw', [b'not-json', b'\xff', None, b'{"x": NaN}'])
def test_bad_wire_message_is_durably_rejected_before_commit(raw):
    worker, client, service, trace = setup_worker([Message(raw)])
    worker.comecar_a_consumir()
    assert service.calls == 0 and len(service.rejections) == 1
    assert 'offset=0' in service.rejections[0]
    assert trace.index(('reject-durable',)) < trace.index(('commit', 0))


def test_failure_to_record_rejection_leaves_offset_uncommitted():
    worker, client, service, _ = setup_worker([Message(b'invalid')])
    def fail(reason): raise RuntimeError('rejection storage offline')
    service.reject_transport_message = fail
    worker.comecar_a_consumir()
    assert client.commits == []


def test_actual_ingestion_service_records_invalid_json_object_and_wire_rejections():
    failures = []
    repository = SimpleNamespace(record_failure=lambda **fields: failures.append(fields))
    service = IngestionService(repository, None, lambda: datetime.now(timezone.utc))
    assert service.ingest(['not-an-object']).status == IngestStatus.REJECTED
    assert service.reject_transport_message('topic=t partition=0 offset=2').status == IngestStatus.REJECTED
    assert len(failures) == 2 and failures[-1]['event'] is None


def test_shutdown_finishes_current_durable_message_before_close():
    worker, client, service, trace = setup_worker([Message(offset=0), Message(offset=1)])
    service.stop_on_success = worker.parar
    worker.comecar_a_consumir()
    assert client.commits == [0] and ('poll', 1) not in trace
    assert trace.index(('commit', 0)) < trace.index(('close',))


def test_stop_before_worker_start_is_not_overwritten():
    worker, client, _, trace = setup_worker([Message()])
    worker.parar()
    worker.comecar_a_consumir()
    assert trace == [('close',)] and not worker.running


def test_health_requires_metadata_and_assignment_and_recovers():
    worker, client, _, _ = setup_worker()
    assert worker.health_snapshot()['status'] == 'DOWN'
    worker.running = True
    worker.assinar_topico()
    worker._probe_broker()
    assert worker.health_snapshot()['status'] == 'UP'
    worker._on_error(RuntimeError('all brokers down'))
    assert worker.health_snapshot()['status'] == 'DOWN'
    worker._probe_broker()
    assert worker.health_snapshot()['status'] == 'UP'
    worker._on_revoke(client, [])
    assert worker.health_snapshot()['status'] == 'DOWN'
    worker.parar()


@pytest.mark.parametrize('version', ['1.0', '1.1'])
def test_envelope_gate_accepts_legacy_and_candidate_but_rejects_malformed(version):
    worker, _, _, _ = setup_worker()
    event = default_events(False, version)[0]
    assert worker._validar_envelope(event) == (True, None)
    event['payload']['confidence'] = -1
    assert worker._validar_envelope(event)[0] is False


@pytest.mark.parametrize('version', ['1.0', '1.1'])
def test_fake_default_and_fresh_events_pass_strict_contract(version):
    events = default_events(False, version)
    before = copy.deepcopy(events)
    now = datetime(2026, 11, 5, 15, tzinfo=timezone.utc)
    fresh = refresh(events, clock=lambda: now)
    assert len(events) == len(fresh) == 4 and events == before
    assert len({event['session_id'] for event in fresh}) == 1
    assert [event['sequence'] for event in fresh] == list(range(4))
    for original, event in zip(events, fresh):
        validate_piece_analysis(original, strict_publisher=True)
        validate_piece_analysis(event, strict_publisher=True)
        assert event['message_id'] != original['message_id']
        assert event['published_at'] == '2026-11-05T15:00:00.000Z'
        assert ('occurred_at' in event) == (version == '1.1')
        if version == '1.1':
            delta = lambda e: datetime.fromisoformat(e['occurred_at']) - datetime.fromisoformat(e['captured_at'])
            assert delta(event) == delta(original)


def test_refresh_does_not_repair_intentionally_invalid_samples():
    event = default_events(False)[0]
    del event['occurred_at']
    event['schema'] = 'wrong-schema'
    fresh = refresh([event])[0]
    assert 'occurred_at' not in fresh and fresh['schema'] == 'wrong-schema'


class ProducerDouble:
    def __init__(self, config, *, error=None, pending=0, acknowledge=True, buffer_failures=0):
        self.config, self.error, self.pending = config, error, pending
        self.acknowledge, self.buffer_failures = acknowledge, buffer_failures
        self.messages = []
        self.flushed = False

    def produce(self, **kwargs):
        if self.buffer_failures:
            self.buffer_failures -= 1
            raise BufferError('queue full')
        self.messages.append(kwargs)

    def poll(self, timeout): pass

    def flush(self, timeout):
        self.flushed = True
        if self.acknowledge:
            for message in self.messages:
                message['on_delivery'](self.error, object())
        return self.pending


def test_fake_confirms_callbacks_and_retries_full_queue():
    clients = []
    def factory(config):
        clients.append(ProducerDouble(config, buffer_failures=1))
        return clients[-1]
    assert publish_events(default_events(False), broker='local', topic='test', producer_factory=factory) == 4
    assert clients[0].config['enable.idempotence'] is True
    assert {message['topic'] for message in clients[0].messages} == {'test'}


@pytest.mark.parametrize('options', [{'error': 'delivery failed'}, {'pending': 1}, {'acknowledge': False}])
def test_fake_never_reports_success_without_all_delivery_callbacks(options, capsys):
    assert main([], producer_factory=lambda config: ProducerDouble(config, **options)) == 1
    captured = capsys.readouterr()
    assert 'Entrega confirmada' not in captured.out
    assert 'Falha na publicação Kafka' in captured.err


def test_permanently_full_queue_has_finite_timeout():
    ticks = iter([0., 2.])
    with pytest.raises(RuntimeError, match='cheia'):
        publish_events(default_events(False), broker='local', topic='test', timeout=1,
                       producer_factory=lambda config: ProducerDouble(config, buffer_failures=100),
                       monotonic=lambda: next(ticks))


def test_custom_invalid_event_requires_explicit_invalid_flag(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{"schema": "wrong"}')
    def forbidden(config): pytest.fail('Producer must not be constructed for invalid input')
    assert main([str(path)], producer_factory=forbidden) == 1
    assert main([str(path), '--invalid'], producer_factory=ProducerDouble) == 0


@pytest.mark.parametrize('arguments', [[], ['--fresh'], ['--schema-version', '1.0'], ['--invalid']])
def test_fake_cli_success(arguments):
    assert main(arguments, producer_factory=ProducerDouble) == 0
