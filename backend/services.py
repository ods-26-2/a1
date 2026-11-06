"""Wiring of the A1 services over one connection pool."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from psycopg_pool import ConnectionPool

from .db import utc_now
from .ingestion import IngestionService
from .inspections import InspectionService, ReviewService
from .repository import InspectionRepository
from .taxonomy import TaxonomyCatalog
from .triage import PolicyCatalog, TriageService
from .p7 import P7Adapter


@dataclass(frozen=True)
class Services:
    repository: InspectionRepository
    ingestion: IngestionService
    inspections: InspectionService
    reviews: ReviewService
    p7: P7Adapter


def build_services(
    pool: ConnectionPool, clock: Callable[[], datetime] = utc_now
) -> Services:
    taxonomy = TaxonomyCatalog()
    repository = InspectionRepository(pool)
    triage = TriageService(PolicyCatalog(), taxonomy)
    inspections = InspectionService(repository, taxonomy)
    return Services(
        repository=repository,
        ingestion=IngestionService(repository, triage, clock),
        inspections=inspections,
        reviews=ReviewService(repository, inspections, clock),
        p7=P7Adapter(repository, clock),
    )
