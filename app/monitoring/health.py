"""Health/readiness checks. Readiness reflects critical dependency state
(database availability) per spec §11."""

from __future__ import annotations

from dataclasses import dataclass

from app.database.session import is_database_available


@dataclass(frozen=True, slots=True)
class ReadinessStatus:
    ready: bool
    database_available: bool


def check_readiness() -> ReadinessStatus:
    db_ok = is_database_available()
    return ReadinessStatus(ready=db_ok, database_available=db_ok)
