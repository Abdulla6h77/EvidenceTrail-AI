from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Mode(StrEnum):
    DEMO = "demo"
    LIVE = "live"


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageName(StrEnum):
    UNDERSTAND = "understand_question"
    PLAN = "create_plan"
    RETRIEVE = "retrieve_data"
    EVALUATE = "evaluate_explanations"
    CHECK = "check_evidence"
    REPORT = "generate_report"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=8, max_length=1000)
    dataset: Literal["synthetic_retail"] = "synthetic_retail"
    mode: Mode = Mode.DEMO


class ParsedQuestion(BaseModel):
    metric: str = "revenue"
    entities: list[str] = Field(default_factory=list)
    period: str | None = None
    comparison_period: str | None = None
    intent: str = "explain_change"
    keywords: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    purpose: str
    sql: str
    hypothesis: str
    required_columns: list[str] = Field(default_factory=list)


class InvestigationPlan(BaseModel):
    parsed_question: ParsedQuestion
    plans: list[QueryPlan]
    memory_ids: list[str] = Field(default_factory=list)
    memory_influenced_plan: bool = False
    memory_note: str | None = None


class QueryProvenance(BaseModel):
    query_id: str
    adapter: str
    sql: str
    executed_at: datetime
    row_count: int
    duration_ms: int
    source: str


class QueryResult(BaseModel):
    provenance: QueryProvenance
    rows: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class EvidenceRecord(BaseModel):
    evidence_id: str
    statement: str
    direction: Literal["supports", "contradicts", "missing"]
    strength: Literal["strong", "moderate", "weak"]
    confidence: float = Field(ge=0, le=1)
    source_query_id: str | None = None
    source_fields: list[str] = Field(default_factory=list)
    values: dict[str, Any] = Field(default_factory=dict)
    caveat: str | None = None


class Finding(BaseModel):
    finding_id: str
    title: str
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    uncertainty: str
    causal_claim: Literal["not_established", "possible_contributor", "supported_contributor"] = (
        "not_established"
    )


class Recommendation(BaseModel):
    action: str
    rationale: str
    priority: Literal["high", "medium", "low"]
    evidence_ids: list[str] = Field(default_factory=list)


class MemoryTrace(BaseModel):
    context: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    provenance: dict[str, dict] = Field(default_factory=dict)
    retrieved: bool = False
    influenced_plan: bool = False
    memory_ids: list[str] = Field(default_factory=list)
    stored_memory_id: str | None = None
    note: str | None = None


class InvestigationReport(BaseModel):
    model_provenance: dict[str, Any] = Field(default_factory=dict)
    investigation_id: str
    question: str
    generated_at: datetime
    mode: Mode
    executive_summary: str
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    query_provenance: list[QueryProvenance] = Field(default_factory=list)
    memory_trace: MemoryTrace = Field(default_factory=MemoryTrace)
    data_quality_notes: list[str] = Field(default_factory=list)


class StageUpdate(BaseModel):
    name: StageName
    label: str
    status: StageStatus
    detail: str | None = None
    completed_at: datetime | None = None


class Investigation(BaseModel):
    id: str
    request: InvestigationRequest
    status: InvestigationStatus
    created_at: datetime
    updated_at: datetime
    stages: list[StageUpdate]
    plan: InvestigationPlan | None = None
    queries: list[QueryResult] = Field(default_factory=list)
    tool_events: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    report: InvestigationReport | None = None


class ConnectivityStatus(BaseModel):
    name: str
    status: Literal["connected", "ready", "not_configured", "error"]
    mode: Mode
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    mode: Mode
    database: str


class OverviewResponse(BaseModel):
    total_investigations: int
    recent_investigations: list[Investigation]
    connectivity: list[ConnectivityStatus]


class HistoryResponse(BaseModel):
    investigations: list[Investigation]
    total: int
