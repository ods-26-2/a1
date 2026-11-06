"""IngestionService: entry point of versioned I8 events into A1.

Transport-agnostic: the fake 6c producer and the B3 subscriber adapter (Ícaro)
both call :meth:`IngestionService.ingest` with the decoded event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math
from typing import Any, Callable, Mapping
from uuid import uuid4

from .contracts import ContractValidationError, validate_piece_analysis
from .db import from_iso, to_iso
from .repository import (
    AuditEntry,
    ConflictingContextError,
    InspectionRepository,
    NewCommand,
    NewInspection,
)
from .taxonomy import TaxonomyError
from .triage import TriageError, TriageService


EVIDENCE_PENDING_DETAIL = (
    "Pedido de snapshot a S4 registrado como comando pendente; "
    "aguardando envio e descritor S4 correlacionado (S3-09)."
)


class IngestStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class IngestResult:
    status: IngestStatus
    inspection_id: str | None = None
    reason: str | None = None


def diagnostic_event_for_jsonb(event: Any) -> dict[str, Any] | None:
    """Return a safe diagnostic copy, or None when jsonb cannot store it."""
    if not isinstance(event, Mapping):
        return None
    candidate = dict(event)
    pending: list[Any] = [candidate]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if isinstance(current, (dict, list)):
            identity = id(current)
            if identity in seen:
                return None
            seen.add(identity)
        if isinstance(current, str):
            if "\x00" in current:
                return None
            try:
                current.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                return None
        elif isinstance(current, float):
            if not math.isfinite(current):
                return None
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif current is not None and not isinstance(current, (bool, int)):
            return None
    return candidate


def inspection_id_for(event: Mapping[str, Any]) -> str:
    # The complete message UUID avoids collisions between session prefixes and
    # cameras. Existing inspection IDs remain stored and queryable unchanged.
    return f"INSP-{event['message_id']}"


def _validate_storage_bounds(event: Mapping[str, Any]) -> None:
    """Check A1 column limits after the shared contract has validated types.

    These are local persistence limits, not changes to the I8 wire contract.
    Permanent input errors must be recorded as rejections before Kafka commits,
    rather than retried as if PostgreSQL were temporarily unavailable.
    """
    payload = event["payload"]
    for path, value, maximum in (
        ("sequence", event["sequence"], 2**63 - 1),
        ("payload.frame_index", payload["frame_index"], 2**63 - 1),
        ("payload.detection_id", payload["detection_id"], 2**31 - 1),
        *((f"payload.bbox[{index}]", value, 2**31 - 1)
          for index, value in enumerate(payload["bbox"])),
    ):
        if value > maximum:
            raise ContractValidationError(
                f"{path}: excede limite de armazenamento A1 ({maximum})"
            )


class IngestionService:
    def __init__(
        self,
        repository: InspectionRepository,
        triage: TriageService,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.triage = triage
        self.clock = clock

    def ingest(self, event: Any) -> IngestResult:
        received_at = self.clock()
        try:
            if not isinstance(event, Mapping):
                raise ContractValidationError("$: o evento deve ser um objeto JSON")
            validated = validate_piece_analysis(event)
            _validate_storage_bounds(validated)
            decision = self.triage.decide(validated["payload"])
        except (ContractValidationError, TaxonomyError, TriageError) as exc:
            return self._reject(event, received_at, str(exc))

        payload = validated["payload"]
        inspection_id = inspection_id_for(validated)
        decided_at = self.clock()
        record = NewInspection(
            inspection_id=inspection_id,
            message_id=validated["message_id"],
            schema_name=validated["schema"],
            schema_version=validated["schema_version"],
            producer=validated["producer"],
            source_id=validated["source_id"],
            session_id=validated["session_id"],
            sequence=validated["sequence"],
            frame_index=payload["frame_index"],
            detection_id=payload["detection_id"],
            bbox=list(payload["bbox"]),
            correlation_id=validated.get("correlation_id"),
            captured_at=from_iso(validated["captured_at"]),
            published_at=from_iso(validated["published_at"]),
            received_at=received_at,
            model_version=validated["artifact_version"],
            taxonomy_version=payload["taxonomy_version"],
            policy_version=decision.policy_version,
            result=payload["result"],
            defect_class=payload.get("defect_class"),
            confidence=payload["confidence"],
            similarity=payload["similarity"],
            triage_status=decision.status,
            triage_reason=decision.reason,
            triage_decided_at=decided_at,
            raw_event=validated,
        )
        command = NewCommand(
            command_id=uuid4(),
            target="S4",
            kind="SNAPSHOT_REQUEST",
            payload={
                "inspection_id": inspection_id,
                "source_id": validated["source_id"],
                "session_id": validated["session_id"],
                "frame_index": payload["frame_index"],
                "captured_at": validated["captured_at"],
                "bbox": list(payload["bbox"]),
            },
        )
        audit = [
            AuditEntry(
                "INGESTED",
                "I8",
                {
                    "message_id": validated["message_id"],
                    "schema_version": validated["schema_version"],
                    "artifact_version": validated["artifact_version"],
                    "result": payload["result"],
                },
            ),
            AuditEntry(
                "TRIAGED",
                "AUTO",
                {
                    "status": decision.status,
                    "policy_version": decision.policy_version,
                    "decided_at": to_iso(decided_at),
                },
            ),
            AuditEntry(
                "EVIDENCE_REQUESTED",
                "A1",
                {"command_id": str(command.command_id), "target": "S4"},
            ),
        ]

        try:
            saved = self.repository.save_ingested(
                record,
                evidence_detail=EVIDENCE_PENDING_DETAIL,
                command=command,
                audit=audit,
            )
        except ConflictingContextError as exc:
            return self._reject(event, received_at, str(exc))

        if not saved.created:
            return IngestResult(IngestStatus.DUPLICATE, saved.inspection_id)
        return IngestResult(IngestStatus.ACCEPTED, saved.inspection_id)

    def reject_transport_message(self, reason: str) -> IngestResult:
        """Persist a transport rejection before the subscriber can commit its offset."""
        return self._reject(None, self.clock(), reason)

    def _reject(self, event: Any, received_at: datetime, reason: str) -> IngestResult:
        message_id = event.get("message_id") if isinstance(event, Mapping) else None
        self.repository.record_failure(
            received_at=received_at,
            message_id=str(message_id) if message_id is not None else None,
            reason=reason,
            event=diagnostic_event_for_jsonb(event),
        )
        return IngestResult(IngestStatus.REJECTED, reason=reason)
