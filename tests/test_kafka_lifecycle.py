"""Health and shutdown ordering through the actual FastAPI lifespan."""
import threading
import io
import json
import shlex
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import app as api
from backend.config import Settings


def setup_api(monkeypatch, *, subscriber_up=False, stuck=False):
    trace = []
    release = threading.Event()
    subscribers = []
    pool = SimpleNamespace(close=lambda: trace.append('pool-close'))
    monkeypatch.setattr(api, 'open_pool', lambda settings: pool)
    monkeypatch.setattr(api, 'apply_schema', lambda pool: None)
    monkeypatch.setattr(api, 'build_services', lambda pool, clock: SimpleNamespace(
        ingestion=object(), repository=SimpleNamespace(ping=lambda: None)))
    class Subscriber:
        def __init__(self, **kwargs): subscribers.append(self)
        def comecar_a_consumir(self):
            release.wait()
            trace.append('worker-exit')
        def parar(self):
            trace.append('stop')
            if not stuck: release.set()
        def health_snapshot(self):
            return {'name': 'i8-subscriber', 'status': 'UP' if subscriber_up else 'DOWN',
                    'detail': 'Test double; no broker connection.'}
    return Subscriber, trace, release


@pytest.mark.parametrize('subscriber_up, expected', [(False, 'DEGRADED'), (True, 'ONLINE')])
def test_health_uses_actual_subscriber_snapshot(monkeypatch, subscriber_up, expected):
    factory, trace, _ = setup_api(monkeypatch, subscriber_up=subscriber_up)
    with TestClient(api.create_app(Settings('unused'), consumer_factory=factory)) as client:
        body = client.get('/api/v1/health').json()
        assert body['status'] == expected
        subscriber = next(c for c in body['components'] if c['name'] == 'i8-subscriber')
        assert subscriber['status'] == ('UP' if subscriber_up else 'DOWN')
    assert trace == ['stop', 'worker-exit', 'pool-close']


def test_shutdown_timeout_does_not_close_pool_under_live_worker(monkeypatch):
    factory, trace, release = setup_api(monkeypatch, stuck=True)
    monkeypatch.setenv('KAFKA_SHUTDOWN_TIMEOUT', '0.01')
    try:
        with pytest.raises(RuntimeError, match='pool mantido aberto'):
            with TestClient(api.create_app(Settings('unused'), consumer_factory=factory)):
                pass
        assert 'pool-close' not in trace
    finally:
        release.set()


def test_consumer_startup_failure_closes_pool(monkeypatch):
    _, trace, _ = setup_api(monkeypatch)
    def fail(**kwargs): raise RuntimeError('consumer constructor failed')
    with pytest.raises(RuntimeError, match='constructor failed'):
        with TestClient(api.create_app(Settings('unused'), consumer_factory=fail)):
            pass
    assert trace == ['pool-close']


@pytest.mark.parametrize('status, expected', [('ONLINE', 0), ('DEGRADED', 1)])
def test_docker_healthcheck_requires_online_body(monkeypatch, status, expected):
    import urllib.request
    dockerfile = Path(__file__).resolve().parents[1] / 'Dockerfile'
    line = next(line.strip() for line in dockerfile.read_text().splitlines()
                if line.strip().startswith('CMD python -c '))
    command = shlex.split(line)[3]
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *args, **kwargs:
                        io.StringIO(json.dumps({'status': status})))
    with pytest.raises(SystemExit) as stopped:
        exec(compile(command, '<docker-healthcheck>', 'exec'), {})
    assert stopped.value.code == expected
