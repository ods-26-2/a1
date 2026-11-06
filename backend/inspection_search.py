"""Validated S3-10 filters over immutable I8 analysis and capture time."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class InspectionSearch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_from: AwareDatetime | None = None
    captured_to: AwareDatetime | None = None
    result: Literal["CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"] | None = None
    source_id: str | None = Field(default=None, min_length=1, max_length=256)
    defect_class: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$")
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("captured_from", "captured_to", mode="before")
    @classmethod
    def explicit_timestamp(cls, value):
        if value is not None and not isinstance(value, datetime):
            if not isinstance(value, str) or "T" not in value:
                raise ValueError("período exige data-hora ISO 8601 com fuso explícito")
        return value

    @field_validator("captured_from", "captured_to")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc) if value else value

    @field_validator("source_id")
    @classmethod
    def valid_source(cls, value):
        if value is not None:
            if not value.strip() or "\x00" in value:
                raise ValueError("origem deve ser texto não vazio sem NUL")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("origem deve ser UTF-8 válido") from exc
        return value

    @model_validator(mode="after")
    def ordered_period(self):
        if self.captured_from and self.captured_to and self.captured_from >= self.captured_to:
            raise ValueError("captured_from deve ser anterior a captured_to (fim exclusivo)")
        return self

    def predicate(self):
        """Only constant SQL fragments; user values always remain parameters."""
        clauses, values = [], []
        for field, column, operator in (
            ("captured_from", "captured_at", ">="), ("captured_to", "captured_at", "<"),
            ("result", "result", "="), ("source_id", "source_id", "="),
            ("defect_class", "defect_class", "="),
        ):
            value = getattr(self, field)
            if value is not None:
                clauses.append(f"i.{column} {operator} %s")
                values.append(value)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(values)
