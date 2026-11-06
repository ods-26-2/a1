"""P7 contract adapter, explicitly driven by a caller; no hardware or broker I/O.

Commands use the existing durable commands/audit tables. Transport is injected;
SENT means send attempted, ACCEPTED means reply OK, COMPLETED needs matching state.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from psycopg.types.json import Jsonb

from .db import from_iso, to_iso, utc_now
from .repository import AuditEntry, InspectionRepository

SCHEMAS = Path(__file__).resolve().parents[1] / "shared/schemas/p7"
FILES = {
    "ods.p7.move.command": "moveCommand.schema.json",
    "ods.p7.move.reply": "moveReply.schema.json",
    "ods.p7.state": "actuatorStateEvent.schema.json",
}
TERMINAL = {"COMPLETED", "REJECTED", "FAILED", "EXPIRED"}


def validate(message):
    """B1 schema plus 6c envelope, identity, JSON and finite-number checks."""
    try:
        message = json.loads(json.dumps(message, allow_nan=False))
        schema = json.loads((SCHEMAS / FILES[message["schema"]]).read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(message)
        for key in ("message_id",):
            if UUID(message[key]).version != 4:
                raise ValueError("message_id deve ser UUID v4")
        if message["schema_version"] != "1.0":
            raise ValueError("schema_version não suportada")
        from_iso(message["published_at"])
        if not message["published_at"].endswith("Z"):
            raise ValueError("published_at deve ser UTC")
        if message["schema"] == "ods.p7.move.command":
            if message["producer"] != "A1" or message["target"] != "P7":
                raise ValueError("comando deve sair de A1 para P7")
        elif message["producer"] != "P7":
            raise ValueError("resposta deve vir de P7")
        if message["schema"] == "ods.p7.state":
            UUID(message["session_id"])
            from_iso(message["captured_at"])
            sequence = message["sequence"]
            if type(sequence) is not int or sequence < 0:
                raise ValueError("sequence inválida")
            correlation = message.get("correlation_id")
            last = message["payload"].get("last_command_id")
            if correlation is not None and correlation != last:
                raise ValueError("correlation_id difere de last_command_id")
        # Prevent values which jsonb rejects, including NUL and lone surrogates.
        def strings(value):
            if isinstance(value, str):
                if "\x00" in value:
                    raise ValueError("NUL não permitido")
                value.encode("utf-8")
            elif isinstance(value, dict):
                for key, item in value.items():
                    strings(key)
                    strings(item)
            elif isinstance(value, list):
                for item in value:
                    strings(item)
        strings(message)
        return message
    except Exception as exc:
        raise ValueError(f"Mensagem P7 inválida: {exc}") from exc


class P7Adapter:
    def __init__(self, repository: InspectionRepository, clock=utc_now, *, timeout=30):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout deve ser positivo e finito")
        self.repository, self.clock = repository, clock
        self.timeout = timedelta(seconds=timeout)

    def request(self, inspection_id, *, command_id, source_id, pan_deg, tilt_deg,
                speed_deg_s=None):
        """Caller supplies stable UUID; reuse with another intent is rejected."""
        payload = {"source_id": source_id, "pan_deg": pan_deg, "tilt_deg": tilt_deg}
        if speed_deg_s is not None:
            payload["speed_deg_s"] = speed_deg_s
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("source_id vazio")
        now = self.clock()
        envelope = validate({"schema": "ods.p7.move.command", "schema_version": "1.0",
            "message_type": "command", "message_id": str(command_id), "producer": "A1",
            "target": "P7", "published_at": to_iso(now), "payload": payload})
        with self.repository.pool.connection() as conn:
            row = conn.execute("""INSERT INTO commands
                (command_id, inspection_id, target, kind, status, payload, created_at, updated_at)
                VALUES (%s, %s, 'P7', 'PAN_TILT_MOVE', 'PENDING', %s, %s, %s)
                ON CONFLICT (command_id) DO NOTHING RETURNING *""",
                (command_id, inspection_id, Jsonb(envelope), now, now)).fetchone()
            if row is not None:
                self._audit(conn, row, "PENDING", envelope)
                return row
            row = conn.execute("SELECT * FROM commands WHERE command_id=%s FOR UPDATE",
                               (command_id,)).fetchone()
            if (row["inspection_id"] != inspection_id or row["target"] != "P7"
                    or row["kind"] != "PAN_TILT_MOVE" or row["payload"]["payload"] != payload):
                raise ValueError("command_id já usado com outra intenção")
            return row

    def get(self, command_id):
        with self.repository.pool.connection() as conn:
            return self._row(conn, command_id)

    def _row(self, conn, command_id):
        row = conn.execute("""SELECT * FROM commands WHERE command_id=%s
            AND target='P7' AND kind='PAN_TILT_MOVE' FOR UPDATE""", (command_id,)).fetchone()
        if row is None:
            raise ValueError("comando P7 não encontrado")
        return row

    def _audit(self, conn, row, status, message):
        self.repository._audit(conn, row["inspection_id"], [AuditEntry(
            "P7_" + status, "A1", {"command_id": str(row["command_id"]),
                                   "message": message})], self.clock())

    def _change(self, conn, row, status, message):
        if status != row["status"]:
            conn.execute("UPDATE commands SET status=%s, updated_at=%s WHERE command_id=%s",
                         (status, self.clock(), row["command_id"]))
            self._audit(conn, row, status, message)
            row["status"] = status
        return row

    def _expire(self, conn, row):
        if row["status"] not in TERMINAL and self.clock() >= row["created_at"] + self.timeout:
            self._change(conn, row, "EXPIRED", {"detail": "Prazo sem conclusão; resultado físico desconhecido."})

    def dispatch(self, command_id, send):
        """Persist before sending. Retry reuses stored envelope without changing ID/time.

        send(topic, message) must be bounded by its transport. A send exception
        leaves SENT (delivery may have occurred). Only explicit retry resends.
        """
        with self.repository.pool.connection() as conn:
            row = self._row(conn, command_id)
            self._expire(conn, row)
            if row["status"] not in {"PENDING", "SENT"}:
                return row
            self._change(conn, row, "SENT", {})
            envelope = copy.deepcopy(row["payload"])
        send("ods.p7.move.command", envelope)
        return self.get(command_id)

    def expire(self, command_id):
        with self.repository.pool.connection() as conn:
            row = self._row(conn, command_id)
            self._expire(conn, row)
            return row

    def receive(self, message):
        message = validate(message)
        is_reply = message["schema"] == "ods.p7.move.reply"
        if not is_reply and message["schema"] != "ods.p7.state":
            raise ValueError("esperada reply ou state")
        payload = message["payload"]
        command_id = message.get("correlation_id") if is_reply else payload.get("last_command_id")
        if command_id is None:
            return False  # Unsolicited homing/heartbeat is not a command result.
        with self.repository.pool.connection() as conn:
            try:
                row = self._row(conn, command_id)
            except ValueError:
                return False
            target = row["payload"]["payload"]
            source = payload.get("source_id") if is_reply else message["source_id"]
            if source is not None and source != target["source_id"]:
                return False
            self._expire(conn, row)
            if row["status"] in TERMINAL or row["status"] == "PENDING":
                return False
            if is_reply:
                status = "REJECTED" if payload["status"] == "ERROR" else "ACCEPTED"
            elif payload["state"] == "ERROR":
                status = "FAILED"
            elif payload["state"] == "IDLE" and payload["is_homed"] and all(
                math.isclose(payload[key], target[key], rel_tol=0, abs_tol=1e-6)
                for key in ("pan_deg", "tilt_deg")
            ):
                status = "COMPLETED"
            else:
                return False
            previous = row["status"]
            self._change(conn, row, status, message)
            return previous != status
