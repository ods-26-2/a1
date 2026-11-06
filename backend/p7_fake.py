"""Finite in-memory P7 simulator. Never imports a driver or moves hardware.

Deduplication lasts only for this simulator instance; it does not certify the
real device's retry handling. Bounds follow B1/6c, not raw servo coordinates.
"""
from copy import deepcopy
from uuid import uuid4

from .db import to_iso, utc_now
from .p7 import validate


class FakeP7:
    def __init__(self, *, source_id="pt0", homed=True, error=None, clock=utc_now):
        self.source_id, self.homed, self.error = source_id, homed, error
        self.clock = clock
        self.session_id = str(uuid4())
        self.sequence = 0
        self.movements = 0
        self.commands = {}
        self.responses = {}
        self.sent = []

    def send(self, topic, command):
        if topic != "ods.p7.move.command":
            raise ValueError("tópico P7 inválido")
        self.sent.append(deepcopy(command))
        command_id = command["message_id"]
        if command_id in self.commands:
            if self.commands[command_id] != command:
                raise ValueError("ID repetido com conteúdo diferente")
            return
        # OUT_OF_RANGE must be exercisable at the device boundary, even though
        # the A1 publisher correctly rejects such a command before sending it.
        payload = command["payload"]
        code = self.error
        if not (-90 <= payload["pan_deg"] <= 90 and -45 <= payload["tilt_deg"] <= 45):
            code = "OUT_OF_RANGE"
        else:
            validate(command)
        if payload["source_id"] != self.source_id:
            code = "DEVICE_ERROR"
        elif not self.homed:
            code = "NOT_HOMED"
        self.commands[command_id] = deepcopy(command)
        if code:
            reply_payload = {"status": "ERROR", "error": {"code": code, "message": code}}
        else:
            self.movements += 1
            reply_payload = {"status": "OK", "source_id": self.source_id,
                "pan_deg": payload["pan_deg"], "tilt_deg": payload["tilt_deg"],
                "state": "MOVING", "is_homed": True}
        reply = self._envelope("ods.p7.move.reply", "reply", reply_payload)
        reply["correlation_id"] = command_id
        replies = [reply]
        if not code:
            state = self._envelope("ods.p7.state", "event", {
                **{key: payload[key] for key in ("pan_deg", "tilt_deg")},
                "state": "IDLE", "is_homed": True, "last_command_id": command_id})
            state.update(source_id=self.source_id, session_id=self.session_id,
                         sequence=self.sequence, captured_at=to_iso(self.clock()),
                         correlation_id=command_id)
            self.sequence += 1
            replies.append(state)
        self.responses[command_id] = replies

    def messages(self, command_id):
        return deepcopy(self.responses[str(command_id)])

    def _envelope(self, schema, kind, payload):
        return {"schema": schema, "schema_version": "1.0", "message_type": kind,
                "message_id": str(uuid4()), "producer": "P7",
                "published_at": to_iso(self.clock()), "payload": payload}
