"""Inspection queries and human review (InspectionController/ReviewController).

Builds the API v1 models from persisted rows. Labels are resolved with the
taxonomy version stored in each inspection, so history keeps its own labels.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from .db import to_iso
from .repository import InspectionRepository
from .taxonomy import TaxonomyCatalog


def _optional_iso(value: datetime | None) -> str | None:
    return to_iso(value) if value is not None else None


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


class InspectionService:
    def __init__(self, repository: InspectionRepository, taxonomy: TaxonomyCatalog) -> None:
        self.repository = repository
        self.taxonomy = taxonomy

    def current(self) -> dict[str, Any] | None:
        row = self.repository.find_current()
        return self.view(row) if row else None

    def get(self, inspection_id: str) -> dict[str, Any] | None:
        row = self.repository.find(inspection_id)
        return self.view(row) if row else None

    def queue(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        rows, total = self.repository.pending_reviews(limit=limit, offset=offset)
        return {"items": [self.view(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def review_options(self, inspection_id: str) -> dict[str, Any] | None:
        row = self.repository.find(inspection_id)
        if row is None:
            return None
        taxonomy = self.taxonomy.load(row["taxonomy_version"])
        return {"taxonomy_version": taxonomy.version, "classes": list(taxonomy.classes.values())}

    def history(self, inspection_id: str) -> dict[str, Any] | None:
        row = self.repository.find(inspection_id)
        if row is None:
            return None
        view = self.view(row)
        return {
            "inspection_id": inspection_id,
            "triage": view["triage"],
            "final_decision": view["final_decision"],
            "reviews": [
                {
                    "review_id": str(review["review_id"]),
                    "action": review["action"],
                    "status": review["status"],
                    "reason": review["reason"],
                    "decided_by": review["operator"],
                    "decided_at": to_iso(review["recorded_at"]),
                    "defect_class": review["defect_class"] if review["classification_set"] else row["defect_class"],
                    "taxonomy_version": row["taxonomy_version"],
                }
                for review in self.repository.reviews(inspection_id)
            ],
            "events": [
                {
                    "event_type": event["event_type"],
                    "actor": event["actor"],
                    "occurred_at": to_iso(event["occurred_at"]),
                    "details": event["details"],
                }
                for event in self.repository.audit_events(inspection_id)
            ],
        }

    def view(self, row: Mapping[str, Any]) -> dict[str, Any]:
        defect = None
        if row["result"] == "NON_CONFORMING":
            label = self.taxonomy.resolve(row["taxonomy_version"], row["defect_class"])
            defect = {
                key: label[key] for key in ("defect_class", "name", "description", "severity")
            }

        final_decision = None
        if row["final_status"] is not None:
            final_decision = {
                "status": row["final_status"],
                "reason": row["final_reason"],
                "decided_by": row["final_operator"],
                "decided_at": to_iso(row["final_recorded_at"]),
                "defect_class": row["final_defect_class"],
                "taxonomy_version": row["taxonomy_version"],
            }

        return {
            "inspection_id": row["inspection_id"],
            "origin": {
                "message_id": str(row["message_id"]),
                "schema": row["schema_name"],
                "schema_version": row["schema_version"],
                "producer": row["producer"],
                "source_id": row["source_id"],
                "session_id": str(row["session_id"]),
                "sequence": row["sequence"],
                "frame_index": row["frame_index"],
                "detection_id": row["detection_id"],
                "bbox": list(row["bbox"]),
            },
            "times": {
                "captured_at": to_iso(row["captured_at"]),
                "published_at": to_iso(row["published_at"]),
                "received_at": to_iso(row["received_at"]),
            },
            "versions": {
                "model": row["model_version"],
                "taxonomy": row["taxonomy_version"],
                "policy": row["policy_version"],
            },
            "analysis": {
                "result": row["result"],
                "confidence": row["confidence"],
                "similarity": row["similarity"],
                "defect": defect,
            },
            "triage": {
                "status": row["triage_status"],
                "reason": row["triage_reason"],
                "decided_by": "AUTO",
                "decided_at": to_iso(row["triage_decided_at"]),
            },
            "final_decision": final_decision,
            "evidence": {
                "state": row["evidence_state"] or "UNAVAILABLE",
                "clip_id": _optional_str(row["evidence_clip_id"]),
                "url": row["evidence_url"] if row["evidence_state"] == "AVAILABLE" else None,
                "expires_at": _optional_iso(row["evidence_expires_at"]),
                "detail": row["evidence_detail"] or "Sem registro de evidência para a inspeção.",
            },
        }


class ReviewService:
    def __init__(
        self,
        repository: InspectionRepository,
        inspections: InspectionService,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.inspections = inspections
        self.clock = clock

    def submit(self, inspection_id: str, *, action: str, operator: str, reason: str,
               status: str | None = None, defect_class: str | None = None) -> dict[str, Any] | None:
        """Record a review as a new row; the automatic decision is never changed."""

        operator, reason = operator.strip(), reason.strip()
        if not operator or len(operator) > 64 or not reason or len(reason) > 1000:
            raise ValueError("operador e motivo são obrigatórios (máximos: 64 e 1000 caracteres)")
        if action not in {"CONFIRM", "CORRECT", "SEND_TO_REVIEW"}:
            raise ValueError("ação de revisão inválida")
        if action != "CORRECT" and (status is not None or defect_class is not None):
            raise ValueError("estado e classe só podem ser enviados em CORRECT")
        row = self.repository.find(inspection_id)
        if row is None:
            return None
        if action == "CORRECT":
            if status not in {"APPROVED", "REJECTED", "REVIEW"}:
                raise ValueError("CORRECT exige estado final válido")
            if status == "REJECTED" and defect_class is None:
                raise ValueError("reprovação exige uma classe de defeito")
            if status == "APPROVED" and defect_class is not None:
                raise ValueError("aprovação não admite classe de defeito")
            if defect_class is not None:
                self.inspections.taxonomy.resolve(row["taxonomy_version"], defect_class)

        def decide(current_status: str, current_class: str | None) -> tuple[str, str | None]:
            if action == "CORRECT":
                return status, defect_class
            return ("REVIEW" if action == "SEND_TO_REVIEW" else current_status), current_class

        recorded_at = self.clock()
        review = self.repository.add_review(
            inspection_id,
            action=action,
            operator=operator,
            recorded_at=recorded_at,
            reason=reason,
            decide=decide,
        )
        if review is None:
            return None
        return {
            "review_id": str(review["review_id"]),
            "action": review["action"],
            "recorded_at": to_iso(review["recorded_at"]),
            "persisted": True,
            "inspection": self.inspections.get(inspection_id),
        }
