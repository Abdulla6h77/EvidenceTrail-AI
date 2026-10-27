from __future__ import annotations

import json
import threading
from pathlib import Path

from app.models.domain import Investigation


class InvestigationStore:
    """Small durable JSON store for the local MVP.

    A JSON file keeps the demo self-contained and inspectable. The store is
    intentionally behind an interface-like class so it can move to a server DB
    without changing API or workflow models.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._items: dict[str, Investigation] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._items = {
                item["id"]: Investigation.model_validate(item)
                for item in payload
                if isinstance(item, dict) and item.get("id")
            }
        except (OSError, ValueError):
            self._items = {}

    def _save(self) -> None:
        payload = [item.model_dump(mode="json") for item in self._items.values()]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, investigation: Investigation) -> Investigation:
        with self._lock:
            self._items[investigation.id] = investigation
            self._save()
        return investigation

    def get(self, investigation_id: str) -> Investigation | None:
        with self._lock:
            return self._items.get(investigation_id)

    def list(self, search: str | None = None, status: str | None = None) -> list[Investigation]:
        with self._lock:
            items = list(self._items.values())
        if search:
            needle = search.lower()
            items = [item for item in items if needle in item.request.question.lower()]
        if status:
            items = [item for item in items if item.status.value == status]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)
