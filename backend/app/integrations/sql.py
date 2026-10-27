from __future__ import annotations

import re
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.models.domain import QueryProvenance, QueryResult
from app.storage.database import Database


class QueryValidationError(ValueError):
    pass


class ReadOnlySQLExecutor:
    """Bounded, read-only SQL execution for the local synthetic dataset."""

    _blocked = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|GRANT|REVOKE)\b",
        re.IGNORECASE,
    )

    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    def validate(self, sql: str) -> str:
        normalized = sql.strip().rstrip(";").strip()
        if not normalized:
            raise QueryValidationError("SQL query cannot be empty")
        if ";" in normalized:
            raise QueryValidationError("Multiple SQL statements are not allowed")
        if not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE):
            raise QueryValidationError("Only SELECT or WITH queries are allowed")
        if self._blocked.search(normalized):
            raise QueryValidationError("Destructive or session-mutating SQL is not allowed")
        if re.search(r"\bSELECT\s+\*", normalized, re.IGNORECASE) and "LIMIT" not in normalized.upper():
            normalized = f"{normalized} LIMIT {self.settings.max_query_rows}"
        return normalized

    def execute(self, sql: str) -> QueryResult:
        safe_sql = self.validate(sql)
        query_id = f"q_{uuid.uuid4().hex[:10]}"
        started = time.perf_counter()
        executed_at = datetime.now(UTC)
        try:
            with self.database.connect() as connection:
                deadline = started + self.settings.query_timeout_seconds
                connection.set_progress_handler(
                    lambda: 1 if time.perf_counter() >= deadline else 0,
                    1000,
                )
                rows = [dict(row) for row in connection.execute(safe_sql).fetchmany(self.settings.max_query_rows)]
                connection.set_progress_handler(None, 0)
            duration_ms = round((time.perf_counter() - started) * 1000)
            provenance = QueryProvenance(
                query_id=query_id,
                adapter="local_sqlite_demo",
                sql=safe_sql,
                executed_at=executed_at,
                row_count=len(rows),
                duration_ms=duration_ms,
                source=str(self.database.path),
            )
            return QueryResult(provenance=provenance, rows=rows)
        except sqlite3.Error as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            provenance = QueryProvenance(
                query_id=query_id,
                adapter="local_sqlite_demo",
                sql=safe_sql,
                executed_at=executed_at,
                row_count=0,
                duration_ms=duration_ms,
                source=str(self.database.path),
            )
            if "interrupted" in str(exc).lower() and duration_ms >= int(self.settings.query_timeout_seconds * 1000):
                error = f"SQL query timed out after {self.settings.query_timeout_seconds:.1f}s"
            else:
                error = f"SQL execution failed: {exc}"
            return QueryResult(provenance=provenance, error=error)


def rows_to_numeric(rows: list[dict[str, Any]], field: str) -> float:
    return sum(float(row.get(field) or 0) for row in rows)
