from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    id: str
    content: str = Field(min_length=10)
    type: Literal["factual", "general", "preference", "personal"] = "factual"
    layer: Literal["short_term", "working", "long_term"] = "working"
    timestamp: datetime
    last_accessed: datetime
    access_count: int = 0
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    source: str = Field(min_length=1)
    provenance_origin: str = "investigation"
    provenance_label: str = "EvidenceTrail investigation summary"
    mission_id: str | None = None
    domain: str = "retail"
    namespace: str = "retail/investigations"
    entities: list[str] = Field(default_factory=list, max_length=10)
    related_to: list[str] = Field(default_factory=list, max_length=5)
    superseded_by: str | None = None
    supersedes: str | None = None
    derived_from: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    score: float | None = None


class MemoryTraceResult(BaseModel):
    context: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    retrieved: list[MemoryRecord] = Field(default_factory=list)
    strategy: str = "minimal"
    retrieval_reason: str = "No matching prior investigation memory"
