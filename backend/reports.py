"""Local reports and explicit operator cause hypotheses; no causal inference."""
import csv
import io
import json
from collections import Counter
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from fastapi import Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .db import to_iso, utc_now
from .inspection_search import InspectionFilters
from .repository import AuditEntry, _VIEW_QUERY

MAX_RECORDS = 5000
MAX_BYTES = 10 * 1024 * 1024


class ReportLimitExceeded(ValueError):
    pass


class InspectionReportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_format: Literal["json", "csv"] = "json"


class ReportQuery(InspectionFilters):
    captured_from: AwareDatetime
    captured_to: AwareDatetime
    file_format: Literal["json", "csv"] = "json"

    @model_validator(mode="after")
    def bounded_period(self):
        if self.captured_to - self.captured_from > timedelta(days=31):
            raise ValueError("relatórios aceitam período máximo de 31 dias")
        return self


class CauseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator: str = Field(min_length=1, max_length=64)
    cause: str = Field(min_length=1, max_length=200)
    basis: str = Field(min_length=1, max_length=1000)

    @field_validator("operator", "cause", "basis", mode="before")
    @classmethod
    def valid_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if any(ord(char) < 32 and char not in "\n\t\r" for char in value):
                raise ValueError("texto contém caractere de controle inválido")
            try: value.encode("utf-8")
            except UnicodeEncodeError as exc: raise ValueError("texto deve ser UTF-8 válido") from exc
        return value


def cause_view(row):
    return {"cause_id": str(row["cause_id"]), "inspection_id": row["inspection_id"],
            "operator": row["operator"], "cause": row["cause"], "basis": row["basis"],
            "recorded_at": to_iso(row["recorded_at"]), "status": "OPERATOR_REPORTED"}


def aggregate_report(kind, rows, filters, generated_at):
    """Deterministic grouping over one bounded snapshot. Missing cause is explicit."""
    groups = Counter()
    if kind == "recurrence":
        for row in rows:
            if row["result"] == "NON_CONFORMING":
                groups[(row["source_id"], row["taxonomy_version"], row["defect_class"]) ] += 1
        items = [{"source_id": key[0], "taxonomy_version": key[1], "defect_class": key[2],
                  "count": count, "rate": count / len(rows), "recurring": count >= 2}
                 for key, count in sorted(groups.items(), key=lambda item: (-item[1], item[0]))]
    else:
        for row in rows: groups[row.get("cause")] += 1
        items = [{"cause": key, "status": "OPERATOR_REPORTED" if key is not None else "NOT_RECORDED", "count": count}
                 for key, count in sorted(groups.items(), key=lambda item: (-item[1], item[0] is None, item[0] or ""))]
    return {"report_version": "1.0", "kind": kind, "generated_at": to_iso(generated_at),
            "filters": filters.model_dump(mode="json", exclude={"file_format"}),
            "total_inspections": len(rows), "items": items}


class ReportService:
    def __init__(self, repository, inspections, clock=utc_now):
        self.repository, self.inspections, self.clock = repository, inspections, clock

    def aggregate(self, kind, filters):
        where, params = filters.predicate()
        with self.repository.pool.connection() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '5000ms'")
            rows = conn.execute("""SELECT i.source_id,i.taxonomy_version,i.defect_class,i.result,c.cause
                FROM inspections i LEFT JOIN LATERAL (
                    SELECT cause FROM inspection_causes WHERE inspection_id=i.inspection_id
                    ORDER BY seq DESC LIMIT 1
                ) c ON true""" + where + " ORDER BY i.captured_at DESC,i.inspection_id DESC LIMIT %s",
                (*params, MAX_RECORDS + 1)).fetchall()
            if len(rows) > MAX_RECORDS:
                raise ReportLimitExceeded("mais de 5000 inspeções; reduza o período/filtros")
        return aggregate_report(kind, rows, filters, self.clock())

    def record_cause(self, inspection_id, body):
        with self.repository.pool.connection() as conn:
            conn.execute("SET LOCAL statement_timeout = '5000ms'")
            if not conn.execute("SELECT inspection_id FROM inspections WHERE inspection_id=%s FOR UPDATE", (inspection_id,)).fetchone():
                return None
            row = conn.execute("""INSERT INTO inspection_causes(cause_id,inspection_id,operator,cause,basis,recorded_at)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(), inspection_id, body.operator, body.cause, body.basis, self.clock())).fetchone()
            self.repository._audit(conn, inspection_id, [AuditEntry("CAUSE_RECORDED", body.operator,
                {"cause_id": str(row["cause_id"]), "cause": body.cause, "basis": body.basis, "status": "OPERATOR_REPORTED"})], row["recorded_at"])
            return cause_view(row)

    def inspection(self, inspection_id):
        with self.repository.pool.connection() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '5000ms'")
            row = conn.execute(_VIEW_QUERY + " WHERE i.inspection_id=%s", (inspection_id,)).fetchone()
            if row is None: return None
            reviews = conn.execute("SELECT * FROM reviews WHERE inspection_id=%s ORDER BY seq LIMIT %s", (inspection_id, MAX_RECORDS + 1)).fetchall()
            events = conn.execute("SELECT * FROM audit_events WHERE inspection_id=%s ORDER BY event_id LIMIT %s", (inspection_id, MAX_RECORDS + 1)).fetchall()
            causes = conn.execute("SELECT * FROM inspection_causes WHERE inspection_id=%s ORDER BY seq LIMIT %s", (inspection_id, MAX_RECORDS + 1)).fetchall()
            if any(len(values) > MAX_RECORDS for values in (reviews, events, causes)):
                raise ReportLimitExceeded("trilha excede 5000 entradas; relatório não será truncado")
        return {"report_version": "1.0", "kind": "inspection", "generated_at": to_iso(self.clock()),
                "inspection": self.inspections.view(row),
                "history": self.inspections.history_view(row, reviews, events),
                "causes": [cause_view(cause) for cause in causes]}


def csv_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def render_report(report, file_format):
    # Stable key ordering, columns, rows and explicit metadata for reproducibility.
    if file_format == "json":
        body = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        media_type = "application/json"
    else:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerow(["section", "record_json"])
        for name in sorted(report):
            value = report[name]
            values = value if isinstance(value, list) else [value]
            for entry in values:
                # JSON cells retain nested inspection/evidence/audit without loss.
                writer.writerow([csv_cell(name), csv_cell(json.dumps(entry, ensure_ascii=False, sort_keys=True))])
        body = ("\ufeff" + buffer.getvalue()).encode("utf-8")
        media_type = "text/csv; charset=utf-8"
    if len(body) > MAX_BYTES: raise ReportLimitExceeded("exportação excede 10 MiB; reduza o período/filtros")
    return Response(body, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="a1-{report["kind"]}.{file_format}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
