from __future__ import annotations

import uuid
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.models.domain import QueryResult


class ZetarisError(RuntimeError):
    pass


class ZetarisAdapter:
    """Opt-in Zetaris REST SQL adapter.

    Uses the verified SqlEditor contract (queryId/sql/source/limit), with Bearer,
    X-Org-ID and UUID X-Request-ID. Positional data rows are mapped using headers.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.zetaris_base_url
            and self.settings.zetaris_api_key
            and self.settings.zetaris_org_id
        )

    async def health(self) -> dict[str, str]:
        if not self.configured:
            return {"status": "not_configured", "detail": "Zetaris credentials are not configured"}
        return {"status": "ready", "detail": "Zetaris adapter configured; live health is verified on query"}

    async def execute(self, sql: str) -> QueryResult:
        if not self.configured:
            raise ZetarisError("Zetaris adapter is not configured")
        from app.integrations.sql import ReadOnlySQLExecutor
        # The shared validator is independent of database access.
        sql = ReadOnlySQLExecutor(None, self.settings).validate(sql)
        if self.settings.zetaris_dataset_mode == "inline_synthetic":
            sql = _inline_synthetic(sql)
        request_id = str(uuid.uuid4())
        base_url = self.settings.zetaris_base_url
        if not base_url:
            raise ZetarisError("Zetaris base URL is not configured")
        url = f"{base_url.rstrip('/')}/sql-editor/sqls/run"
        headers = {
            "Authorization": f"Bearer {self.settings.zetaris_api_key}",
            "X-Org-ID": self.settings.zetaris_org_id or "",
            "X-Request-ID": request_id,
            "Accept": "application/json",
        }
        body = {"queryId": request_id, "sql": sql, "source": "SqlEditor", "limit": self.settings.zetaris_page_limit}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.settings.zetaris_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload: Any = response.json()
        except httpx.HTTPStatusError as exc:
            raise ZetarisError(f"Zetaris returned HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ZetarisError(f"Zetaris request failed: {exc.__class__.__name__}") from exc

        rows = _extract_rows(payload)
        from datetime import UTC, datetime

        from app.models.domain import QueryProvenance

        provenance = QueryProvenance(
            query_id=request_id,
            adapter="zetaris_rest",
            sql=sql,
            executed_at=datetime.now(UTC),
            row_count=len(rows),
            duration_ms=round((time.perf_counter() - started) * 1000),
            source=url,
        )
        return QueryResult(provenance=provenance, rows=rows)


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        raise ZetarisError("Unexpected Zetaris response shape")
    if "headers" in payload and isinstance(payload.get("data"), list):
        headers = payload["headers"]
        if not isinstance(headers, list) or not all(isinstance(item, str) for item in headers):
            raise ZetarisError("Invalid Zetaris column headers")
        rows = payload["data"]
        if any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
            raise ZetarisError("Zetaris row/header mismatch")
        if payload.get("total", len(rows)) > len(rows):
            raise ZetarisError("Zetaris result was truncated; refine the query or increase its limit")
        return [dict(zip(headers, row)) for row in rows]
    for key in ("rows", "data", "result", "records", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _extract_rows(value)
            if nested:
                return nested
    raise ZetarisError("Unrecognized Zetaris response; refusing to treat it as empty data")


def _inline_synthetic(sql: str) -> str:
    """Execute the public demo fixture in Zetaris, without registering platform tables."""
    import re
    from app.data.retail import build_rows

    definitions = []
    for table, rows in build_rows().items():
        if not re.search(rf"\b{table}\b", sql):
            continue
        columns = list(rows[0])
        def literal(value):
            if value is None:
                return "NULL"
            if isinstance(value, (int, float)):
                return str(value)
            return "'" + str(value).replace("'", "''") + "'"
        values = ",".join("(" + ",".join(literal(row[col]) for col in columns) + ")" for row in rows)
        definitions.append(f"{table} ({','.join(columns)}) AS (VALUES {values})")
    return "WITH " + ",".join(definitions) + " " + sql if definitions else sql
