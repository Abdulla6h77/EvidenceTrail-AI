"""Local H-MEM-compatible implementation.

The public Meterless H-MEM material describes canonical records, provenance,
confidence, hybrid retrieval, and audit behavior but does not provide a stable
hosted API contract. This adapter implements those documented behaviors locally
and labels itself honestly as a local fallback.
"""

from __future__ import annotations

import json
import math
import re
import uuid
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.models.memory import MemoryRecord, MemoryTraceResult


class HMEMAdapter(Protocol):
    """Interface shared by the local fallback and a future verified runtime adapter."""
    mode: str

    def add_summary(self, content: str, investigation_id: str, tags: list[str], entities: list[str], confidence: float, provenance_refs: list[str] | None = None) -> MemoryRecord: ...

    def retrieve(self, query: str, top_n: int = 5) -> MemoryTraceResult: ...


class MeterlessHMEMAdapter:
    """Explicit placeholder for a live Meterless runtime contract.

    No URL, method, or payload is guessed here. The class exists so callers can
    wire a verified implementation without changing the workflow interface.
    """

    mode = "meterless_unconfigured"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return False

    def add_summary(self, *args, **kwargs) -> MemoryRecord:
        raise RuntimeError("Live Meterless H-MEM adapter is not configured or verified")

    def retrieve(self, *args, **kwargs) -> MemoryTraceResult:
        raise RuntimeError("Live Meterless H-MEM adapter is not configured or verified")


class HMEMStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[MemoryRecord] = []
        self._load()

    @property
    def mode(self) -> str:
        return "local_hmem_fallback"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = [MemoryRecord.model_validate(item) for item in payload]
        except (OSError, ValueError):
            self._records = []

    def _save(self) -> None:
        self.path.write_text(
            json.dumps([record.model_dump(mode="json") for record in self._records], indent=2),
            encoding="utf-8",
        )

    def add_summary(
        self,
        content: str,
        investigation_id: str,
        tags: list[str],
        entities: list[str],
        confidence: float,
        provenance_refs: list[str] | None = None,
    ) -> MemoryRecord:
        now = datetime.now(UTC)
        record = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            content=content,
            type="factual",
            layer="long_term",
            timestamp=now,
            last_accessed=now,
            confidence=max(0, min(1, confidence)),
            source=f"investigation:{investigation_id}",
            mission_id=investigation_id,
            tags=tags[:10],
            entities=entities[:10],
        )
        self._records.append(record)
        self._save()
        return record

    def retrieve(self, query: str, top_n: int = 5) -> MemoryTraceResult:
        query_tokens = _tokens(query)
        scored: list[tuple[float, MemoryRecord]] = []
        for record in self._records:
            memory_tokens = _tokens(record.content + " " + " ".join(record.tags + record.entities))
            overlap = len(query_tokens & memory_tokens) / max(1, len(query_tokens | memory_tokens))
            semantic = _hash_similarity(query, record.content)
            score = (0.35 * semantic + 0.20 * overlap + 0.10 * (1 if record.layer == "long_term" else 0.8)) * record.confidence
            if record.superseded_by:
                score *= 0.8
            if score >= 0.12:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [record for _, record in scored[:top_n]]
        if selected:
            selected_ids = {record.id for record in selected}
            now = datetime.now(UTC)
            self._records = [
                record.model_copy(
                    update={
                        "last_accessed": now,
                        "access_count": record.access_count + 1,
                    }
                )
                if record.id in selected_ids
                else record
                for record in self._records
            ]
            self._save()
        return MemoryTraceResult(
            retrieved=selected,
            strategy="comprehensive" if selected else "minimal",
            retrieval_reason=(
                "Retrieved prior investigation summaries using hybrid lexical/semantic scoring"
                if selected
                else "No matching prior investigation memory"
            ),
        )


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2}


def _hash_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = len(left_tokens & right_tokens)
    return min(1.0, shared / math.sqrt(len(left_tokens) * len(right_tokens)))


_ENGINE_LOCK = threading.RLock()


class ReferenceHMEMStore:
    """Pinned Meterless reference engine over a local JSON subprocess boundary.

    One API worker per persistence directory. Calls in this process serialize
    load/mutate/save; independent API workers must use separate directories.
    Legacy fallback files are preserved and are not silently imported as trusted facts.
    """

    mode = "meterless_reference_local"

    def __init__(self, path: Path, node_binary: str = "node") -> None:
        self.path = path.resolve()
        self.node_binary = node_binary
        self.bridge = Path(__file__).resolve().parents[2] / "vendor" / "meterless-hmem" / "bridge.ts"
        self.inspect()  # Fail explicitly at startup if runtime/state is unavailable.

    def _call(self, action: str, **payload):
        with _ENGINE_LOCK:
            completed = subprocess.run(
                [self.node_binary, "--experimental-transform-types", str(self.bridge)],
                input=json.dumps({"persistDir": str(self.path), "action": action, **payload}),
                capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
            )
            if completed.returncode:
                raise RuntimeError(f"Meterless reference engine failed: {completed.stderr[-2000:]}")
            return json.loads(completed.stdout)

    @staticmethod
    def _record(raw) -> MemoryRecord:
        return MemoryRecord(
            **{key: raw[key] for key in ("id", "content", "type", "layer", "tags", "confidence", "source", "domain", "namespace", "entities")},
            timestamp=datetime.fromtimestamp(raw["timestamp"] / 1000, UTC),
            last_accessed=datetime.fromtimestamp(raw["lastAccessed"] / 1000, UTC),
            access_count=raw["accessCount"], mission_id=raw.get("missionId"),
            related_to=raw.get("relatedTo", []), superseded_by=raw.get("supersededBy"),
            provenance_origin=raw["provenance"]["origin"],
            provenance_label=raw["provenance"]["label"],
            provenance=raw["provenance"], supersedes=raw.get("supersedes"),
            derived_from=raw.get("derivedFrom", []), score=raw.get("score"),
        )

    def add_summary(self, content, investigation_id, tags, entities, confidence,
                    provenance_refs=None) -> MemoryRecord:
        raw = self._call("add", input={
            "content": content, "type": "factual", "layer": "working",
            "tags": tags, "confidence": confidence,
            "source": f"investigation:{investigation_id}", "missionId": investigation_id,
            "provenance": {"origin": "plan_completion",
                           "learnedAt": int(datetime.now(UTC).timestamp() * 1000),
                           "label": "Synthetic retail investigation finding; requires revalidation",
                           "refs": [f"investigation:{investigation_id}", *(provenance_refs or [])]},
        })
        return self._record(raw)

    def retrieve(self, query: str, top_n: int = 5) -> MemoryTraceResult:
        result = self._call("query", query=query, topN=top_n)
        return MemoryTraceResult(
            retrieved=[self._record({**item["memory"], "score": item["relevance"]}) for item in result["memories"]],
            strategy=result["trace"]["strategy"],
            retrieval_reason=result["trace"]["retrievalReason"],
            context=result["context"], scores=result["trace"]["scores"],
        )

    def feedback(self, memory_id: str, kind: str) -> None:
        if kind not in {"helpful", "not_helpful", "wrong"}:
            raise ValueError("Unknown feedback kind")
        self._call("feedback", id=memory_id, kind=kind)

    def inspect(self):
        return self._call("inspect")
