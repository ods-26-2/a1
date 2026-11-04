"""InspectionRepository: PostgreSQL persistence of inspections and audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4

from psycopg import errors
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool


class ConflictingContextError(ValueError):
    """Another message already registered the same source/session/frame/detection."""


@dataclass(frozen=True)
class AuditEntry:
    event_type: str
    actor: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NewInspection:
    inspection_id: str
    message_id: str
    schema_name: str
    schema_version: str
    producer: str
    source_id: str
    session_id: str
    sequence: int
    frame_index: int
    detection_id: int
    bbox: list[int]
    correlation_id: str | None
    captured_at: datetime
    published_at: datetime
    received_at: datetime
    model_version: str
    taxonomy_version: str
    policy_version: str
    result: str
    defect_class: str | None
    confidence: float
    similarity: float
    triage_status: str
    triage_reason: str
    triage_decided_at: datetime
    raw_event: Mapping[str, Any]


@dataclass(frozen=True)
class NewCommand:
    command_id: UUID
    target: str
    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class SaveResult:
    inspection_id: str
    created: bool


_VIEW_QUERY = """
SELECT i.*,
       e.state AS evidence_state, e.clip_id AS evidence_clip_id,
       e.url AS evidence_url, e.expires_at AS evidence_expires_at,
       e.detail AS evidence_detail,
       r.status AS final_status, r.reason AS final_reason,
       r.operator AS final_operator, r.recorded_at AS final_recorded_at,
       CASE WHEN r.classification_set THEN r.defect_class ELSE i.defect_class END AS final_defect_class
FROM inspections i
LEFT JOIN evidence e ON e.inspection_id = i.inspection_id
LEFT JOIN LATERAL (
    SELECT status, reason, operator, recorded_at, defect_class, classification_set
    FROM reviews
    WHERE reviews.inspection_id = i.inspection_id
    ORDER BY seq DESC
    LIMIT 1
) r ON true
"""


class InspectionRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def ping(self, *, timeout: float = 2.0) -> None:
        with self.pool.connection(timeout=timeout) as conn:
            conn.execute("SELECT 1")

    def save_ingested(
        self,
        record: NewInspection,
        *,
        evidence_detail: str,
        command: NewCommand,
        audit: list[AuditEntry],
    ) -> SaveResult:
        """Store a new inspection atomically; a repeated message_id stores nothing."""

        try:
            with self.pool.connection() as conn:
                row = conn.execute(
                    """
                    INSERT INTO inspections (
                        inspection_id, message_id, schema_name, schema_version,
                        producer, source_id, session_id, sequence, frame_index,
                        detection_id, bbox, correlation_id, captured_at,
                        published_at, received_at, model_version,
                        taxonomy_version, policy_version, result, defect_class,
                        confidence, similarity, triage_status, triage_reason,
                        triage_decided_at, raw_event
                    ) VALUES (
                        %(inspection_id)s, %(message_id)s, %(schema_name)s,
                        %(schema_version)s, %(producer)s, %(source_id)s,
                        %(session_id)s, %(sequence)s, %(frame_index)s,
                        %(detection_id)s, %(bbox)s, %(correlation_id)s,
                        %(captured_at)s, %(published_at)s, %(received_at)s,
                        %(model_version)s, %(taxonomy_version)s,
                        %(policy_version)s, %(result)s, %(defect_class)s,
                        %(confidence)s, %(similarity)s, %(triage_status)s,
                        %(triage_reason)s, %(triage_decided_at)s, %(raw_event)s
                    )
                    ON CONFLICT (message_id) DO NOTHING
                    RETURNING inspection_id
                    """,
                    {**record.__dict__, "raw_event": Jsonb(dict(record.raw_event))},
                ).fetchone()

                if row is None:
                    existing = conn.execute(
                        "SELECT inspection_id FROM inspections WHERE message_id = %s",
                        (record.message_id,),
                    ).fetchone()
                    return SaveResult(existing["inspection_id"], created=False)

                now = record.received_at
                conn.execute(
                    """
                    INSERT INTO evidence (inspection_id, state, detail, updated_at)
                    VALUES (%s, 'PENDING', %s, %s)
                    """,
                    (record.inspection_id, evidence_detail, now),
                )
                conn.execute(
                    """
                    INSERT INTO commands (
                        command_id, inspection_id, target, kind, status, payload,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, 'PENDING', %s, %s, %s)
                    """,
                    (
                        command.command_id,
                        record.inspection_id,
                        command.target,
                        command.kind,
                        Jsonb(dict(command.payload)),
                        now,
                        now,
                    ),
                )
                self._audit(conn, record.inspection_id, audit, now)
                return SaveResult(record.inspection_id, created=True)
        except errors.UniqueViolation as exc:
            raise ConflictingContextError(
                "fonte, sessão, quadro e detecção já registrados por outra mensagem"
            ) from exc

    def record_failure(
        self,
        *,
        received_at: datetime,
        message_id: str | None,
        reason: str,
        event: Any,
    ) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_failures (received_at, message_id, reason, event)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    received_at,
                    message_id,
                    reason,
                    Jsonb(event) if isinstance(event, (dict, list)) else None,
                ),
            )

    def find_current(self) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return conn.execute(
                _VIEW_QUERY + " ORDER BY i.received_at DESC, i.inspection_id DESC LIMIT 1"
            ).fetchone()

    def find(self, inspection_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return conn.execute(
                _VIEW_QUERY + " WHERE i.inspection_id = %s", (inspection_id,)
            ).fetchone()

    def add_review(
        self,
        inspection_id: str,
        *,
        action: str,
        operator: str,
        recorded_at: datetime,
        reason: str,
        decide: Callable[[str, str | None], tuple[str, str | None]],
    ) -> dict[str, Any] | None:
        """Append a review under the inspection lock, preserving the automatic row.

        Returns ``None`` when the inspection does not exist.
        """

        with self.pool.connection() as conn:
            current = conn.execute(
                """
                SELECT i.triage_status, i.defect_class,
                       (SELECT status FROM reviews r
                        WHERE r.inspection_id = i.inspection_id
                        ORDER BY seq DESC LIMIT 1) AS final_status,
                       (SELECT CASE WHEN r.classification_set THEN r.defect_class ELSE i.defect_class END
                        FROM reviews r WHERE r.inspection_id = i.inspection_id
                        ORDER BY seq DESC LIMIT 1) AS final_defect_class
                FROM inspections i
                WHERE i.inspection_id = %s
                FOR UPDATE
                """,
                (inspection_id,),
            ).fetchone()
            if current is None:
                return None

            previous_status = current["final_status"] or current["triage_status"]
            previous_class = current["final_defect_class"] if current["final_status"] else current["defect_class"]
            status, defect_class = decide(previous_status, previous_class)
            review = conn.execute(
                """
                INSERT INTO reviews (
                    review_id, inspection_id, action, status, reason, operator,
                    recorded_at, defect_class, classification_set
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
                RETURNING review_id, action, status, reason, operator, recorded_at, defect_class
                """,
                (uuid4(), inspection_id, action, status, reason, operator, recorded_at, defect_class),
            ).fetchone()
            self._audit(
                conn,
                inspection_id,
                [
                    AuditEntry(
                        "REVIEW_RECORDED",
                        operator,
                        {
                            "review_id": str(review["review_id"]),
                            "action": action,
                            "previous_status": current["final_status"]
                            or current["triage_status"],
                            "status": status,
                            "previous_defect_class": previous_class,
                            "defect_class": defect_class,
                            "reason": reason,
                        },
                    )
                ],
                recorded_at,
            )
            return review

    def reviews(self, inspection_id: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            return conn.execute(
                """
                SELECT review_id, action, status, reason, operator, recorded_at, defect_class, classification_set
                FROM reviews WHERE inspection_id = %s ORDER BY seq
                """,
                (inspection_id,),
            ).fetchall()

    def pending_reviews(self, *, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        # The queue is a projection of persisted immutable inspections/reviews;
        # it survives restart and cannot drift from the final decision.
        query = _VIEW_QUERY + " WHERE COALESCE(r.status, i.triage_status) = 'REVIEW'"
        with self.pool.connection() as conn:
            total = conn.execute("SELECT count(*) AS total FROM (" + query + ") pending").fetchone()["total"]
            rows = conn.execute(query + " ORDER BY i.received_at, i.inspection_id LIMIT %s OFFSET %s", (limit, offset)).fetchall()
            return rows, total

    def audit_events(self, inspection_id: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            return conn.execute(
                """
                SELECT event_type, actor, occurred_at, details
                FROM audit_events WHERE inspection_id = %s ORDER BY event_id
                """,
                (inspection_id,),
            ).fetchall()

    @staticmethod
    def _audit(conn, inspection_id: str, entries: list[AuditEntry], at: datetime) -> None:
        for entry in entries:
            conn.execute(
                """
                INSERT INTO audit_events (inspection_id, event_type, actor, occurred_at, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (inspection_id, entry.event_type, entry.actor, at, Jsonb(dict(entry.details))),
            )
