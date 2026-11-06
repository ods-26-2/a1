"""Activity 24: real A1 persistence, injected P7 simulator, no hardware/broker."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.fake_producer import default_events
from backend.p7 import P7Adapter, validate
from backend.p7_fake import FakeP7


@pytest.fixture
def lab(client, ingest):
    inspection = ingest(default_events(False)[0]).inspection_id
    now = [datetime.now(timezone.utc)]
    adapter = P7Adapter(client.app.state.services.repository, lambda: now[0])
    fake = FakeP7(clock=lambda: now[0])
    return adapter, fake, inspection, now


def request(lab, **kwargs):
    adapter, _, inspection, _ = lab
    return adapter.request(inspection, command_id=kwargs.pop('command_id', uuid4()),
        source_id='pt0', pan_deg=kwargs.pop('pan_deg', 12.5),
        tilt_deg=kwargs.pop('tilt_deg', -8), **kwargs)


def test_acceptance_is_not_completion_and_audit_is_durable(lab, sql):
    adapter, fake, _, _ = lab
    row = request(lab)
    command_id = row['command_id']
    assert row['status'] == 'PENDING'
    assert fake.movements == 0
    assert adapter.dispatch(command_id, fake.send)['status'] == 'SENT'
    reply, state = fake.messages(command_id)
    assert adapter.receive(reply)
    assert adapter.get(command_id)['status'] == 'ACCEPTED'
    assert adapter.receive(state)
    assert adapter.get(command_id)['status'] == 'COMPLETED'
    assert [r[0] for r in sql("SELECT event_type FROM audit_events WHERE event_type LIKE 'P7_%%' ORDER BY event_id")] == [
        'P7_PENDING', 'P7_SENT', 'P7_ACCEPTED', 'P7_COMPLETED']
    assert adapter.get(command_id)['payload'] == row['payload']


def test_retry_after_lost_reply_and_recreated_adapter_does_not_move_twice(lab, sql):
    adapter, fake, inspection, now = lab
    row = request(lab)
    command_id = row['command_id']
    def lost_reply(topic, message):
        fake.send(topic, message)
        raise TimeoutError('delivery uncertain')
    with pytest.raises(TimeoutError):
        adapter.dispatch(command_id, lost_reply)
    now[0] += timedelta(seconds=2)
    restarted = P7Adapter(adapter.repository, lambda: now[0])
    assert restarted.request(inspection, command_id=command_id, source_id='pt0',
        pan_deg=12.5, tilt_deg=-8)['payload'] == row['payload']
    restarted.dispatch(command_id, fake.send)
    assert len(fake.sent) == 2 and fake.sent[0] == fake.sent[1]
    assert fake.movements == 1
    for message in fake.messages(command_id):
        restarted.receive(message)
        assert not restarted.receive(message)
    restarted.dispatch(command_id, fake.send)
    assert len(fake.sent) == 2
    assert sql("SELECT count(*) FROM commands WHERE target='P7'")[0][0] == 1


@pytest.mark.parametrize('field,value', [('pan_deg', -90), ('pan_deg', 90), ('tilt_deg', -45), ('tilt_deg', 45)])
def test_exact_limits_are_accepted(lab, field, value):
    adapter, fake, _, _ = lab
    row = request(lab, **{field: value})
    adapter.dispatch(row['command_id'], fake.send)
    for message in fake.messages(row['command_id']):
        adapter.receive(message)
    assert adapter.get(row['command_id'])['status'] == 'COMPLETED'


@pytest.mark.parametrize('field,value', [('pan_deg', -90.01), ('pan_deg', 90.01),
    ('tilt_deg', -45.01), ('tilt_deg', 45.01), ('pan_deg', float('nan')),
    ('pan_deg', float('inf')), ('pan_deg', True), ('speed_deg_s', 0), ('speed_deg_s', -1)])
def test_invalid_request_never_reaches_device_or_database(lab, sql, field, value):
    with pytest.raises(ValueError):
        request(lab, **{field: value})
    assert lab[1].movements == 0
    assert sql("SELECT count(*) FROM commands WHERE target='P7'")[0][0] == 0


def test_same_id_with_another_intent_is_rejected(lab):
    row = request(lab)
    with pytest.raises(ValueError, match='outra intenção'):
        request(lab, command_id=row['command_id'], pan_deg=10)


@pytest.mark.parametrize('code', ['NOT_HOMED', 'LIMIT_SWITCH_REACHED', 'DEVICE_ERROR'])
def test_refusal_preserves_error_and_does_not_move(lab, sql, code):
    adapter, _, _, now = lab
    fake = FakeP7(homed=code != 'NOT_HOMED', error=code, clock=lambda: now[0])
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    assert adapter.receive(fake.messages(row['command_id'])[0])
    assert adapter.get(row['command_id'])['status'] == 'REJECTED'
    assert fake.movements == 0
    assert sql("SELECT details->'message'->'payload'->'error'->>'code' FROM audit_events WHERE event_type='P7_REJECTED'")[0][0] == code


def test_fake_out_of_range_never_moves(lab):
    row = request(lab)
    bad = deepcopy(row['payload'])
    bad['payload']['pan_deg'] = 91
    fake = lab[1]
    fake.send('ods.p7.move.command', bad)
    reply = fake.messages(row['command_id'])[0]
    validate(reply)
    assert reply['payload']['error']['code'] == 'OUT_OF_RANGE'
    assert fake.movements == 0


def test_state_before_reply_completes_without_regression(lab):
    adapter, fake, _, _ = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    reply, state = fake.messages(row['command_id'])
    assert adapter.receive(state)
    assert not adapter.receive(reply)
    assert adapter.get(row['command_id'])['status'] == 'COMPLETED'


@pytest.mark.parametrize('change', ['unknown', 'source', 'mismatch', 'not_homed', 'moving', 'uncorrelated'])
def test_unrelated_or_incomplete_state_never_completes(lab, change):
    adapter, fake, _, _ = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    state = fake.messages(row['command_id'])[1]
    if change == 'unknown':
        state['payload']['last_command_id'] = state['correlation_id'] = str(uuid4())
    elif change == 'source':
        state['source_id'] = 'pt-other'
    elif change == 'mismatch':
        state['payload']['pan_deg'] += 1
    elif change == 'not_homed':
        state['payload']['is_homed'] = False
    elif change == 'moving':
        state['payload']['state'] = 'MOVING'
    else:
        del state['payload']['last_command_id']
        del state['correlation_id']
    assert not adapter.receive(state)
    assert adapter.get(row['command_id'])['status'] == 'SENT'


def test_state_error_is_failure_not_refusal(lab):
    adapter, fake, _, _ = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    reply, state = fake.messages(row['command_id'])
    adapter.receive(reply)
    state['payload'].update(state='ERROR', error={'code': 'DEVICE_ERROR', 'message': 'motor failed'})
    assert adapter.receive(state)
    assert adapter.get(row['command_id'])['status'] == 'FAILED'


@pytest.mark.parametrize('sent', [False, True])
def test_timeout_never_claims_physical_failure_or_resends_late(lab, sent):
    adapter, fake, _, now = lab
    row = request(lab)
    if sent:
        adapter.dispatch(row['command_id'], fake.send)
    now[0] += timedelta(seconds=30)
    assert adapter.expire(row['command_id'])['status'] == 'EXPIRED'
    adapter.dispatch(row['command_id'], fake.send)
    assert len(fake.sent) == int(sent)
    if sent:
        for message in fake.messages(row['command_id']):
            assert not adapter.receive(message)
    assert adapter.get(row['command_id'])['status'] == 'EXPIRED'


def test_database_failure_prevents_send(lab, monkeypatch):
    adapter, fake, _, _ = lab
    row = request(lab)
    def unavailable(*args, **kwargs):
        raise RuntimeError('database unavailable')
    monkeypatch.setattr(adapter.repository.pool, 'connection', unavailable)
    with pytest.raises(RuntimeError):
        adapter.dispatch(row['command_id'], fake.send)
    assert fake.sent == []


@pytest.mark.parametrize('change', ['producer', 'version', 'nan', 'uuid', 'correlation'])
def test_invalid_reply_cannot_change_status(lab, change):
    adapter, fake, _, _ = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    message = fake.messages(row['command_id'])[1]
    if change == 'producer': message['producer'] = 'I8'
    elif change == 'version': message['schema_version'] = '2.0'
    elif change == 'nan': message['payload']['pan_deg'] = float('nan')
    elif change == 'uuid': message['message_id'] = 'bad'
    else: message['correlation_id'] = str(uuid4())
    with pytest.raises(ValueError):
        adapter.receive(message)
    assert adapter.get(row['command_id'])['status'] == 'SENT'


def test_refusal_out_of_range_is_registered_even_with_valid_requested_angle(lab):
    adapter, _, _, _ = lab
    fake = FakeP7(error='OUT_OF_RANGE')  # Device may have narrower calibrated limits.
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    assert adapter.receive(fake.messages(row['command_id'])[0])
    assert adapter.get(row['command_id'])['status'] == 'REJECTED'
    assert fake.movements == 0


def test_unsent_command_cannot_be_completed_by_received_state(lab):
    adapter, fake, _, _ = lab
    row = request(lab)
    fake.send('ods.p7.move.command', row['payload'])
    assert not adapter.receive(fake.messages(row['command_id'])[1])
    assert adapter.get(row['command_id'])['status'] == 'PENDING'


def test_timeout_after_acceptance_does_not_claim_completion(lab):
    adapter, fake, _, now = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    reply, state = fake.messages(row['command_id'])
    adapter.receive(reply)
    now[0] += timedelta(seconds=31)
    assert not adapter.receive(state)
    assert adapter.get(row['command_id'])['status'] == 'EXPIRED'


def test_audit_failure_rolls_back_request(lab, sql, monkeypatch):
    adapter = lab[0]
    def unavailable(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr(adapter.repository, '_audit', unavailable)
    with pytest.raises(RuntimeError):
        request(lab)
    assert sql("SELECT count(*) FROM commands WHERE target='P7'")[0][0] == 0


def test_reused_id_cannot_change_inspection(lab, ingest):
    row = request(lab)
    other = ingest(default_events(False)[1]).inspection_id
    with pytest.raises(ValueError, match='outra intenção'):
        lab[0].request(other, command_id=row['command_id'], source_id='pt0', pan_deg=12.5, tilt_deg=-8)


def test_fake_rejects_mutation_on_retry(lab):
    adapter, fake, _, _ = lab
    row = request(lab)
    adapter.dispatch(row['command_id'], fake.send)
    changed = deepcopy(row['payload'])
    changed['payload']['pan_deg'] = 15
    with pytest.raises(ValueError, match='conteúdo diferente'):
        fake.send('ods.p7.move.command', changed)
    assert fake.movements == 1
