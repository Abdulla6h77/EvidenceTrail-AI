from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.core.container import AppServices
from app.data.retail import SCHEMA
from app.models.domain import (
    ConnectivityStatus,
    HealthResponse,
    HistoryResponse,
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    Mode,
    OverviewResponse,
)


router = APIRouter(prefix="/api")


def services(request: Request) -> AppServices:
    return request.app.state.services


@router.get("/health", response_model=HealthResponse)
def health(app_services: AppServices = Depends(services)) -> HealthResponse:
    return HealthResponse(
        app=app_services.settings.app_name,
        mode=Mode.DEMO if app_services.settings.app_env == "demo" else Mode.LIVE,
        database="ready",
    )


@router.get("/config/status", response_model=list[ConnectivityStatus])
def config_status(app_services: AppServices = Depends(services)) -> list[ConnectivityStatus]:
    configured_mode = Mode.DEMO if app_services.settings.app_env == "demo" else Mode.LIVE
    zetaris_state = app_services.zetaris
    model_state = app_services.nemotron.status()
    return [
        ConnectivityStatus(
            name="Synthetic retail data",
            status="ready",
            mode=Mode.DEMO,
            detail="Seeded local SQLite dataset with deterministic scenarios",
        ),
        ConnectivityStatus(
            name="Zetaris",
            status="ready" if zetaris_state.configured else "not_configured",
            mode=Mode.LIVE,
            detail=(
                f"Configured SqlEditor adapter; dataset mode: {app_services.settings.zetaris_dataset_mode}"
                if zetaris_state.configured
                else "Add ZETARIS_BASE_URL, ZETARIS_API_KEY, and ZETARIS_ORG_ID for live mode"
            ),
        ),
        ConnectivityStatus(
            name="NVIDIA Nemotron",
            status="ready" if model_state["status"] == "ready" else "not_configured",
            mode=Mode.LIVE,
            detail=model_state["detail"],
        ),
        ConnectivityStatus(
            name="Meterless H-MEM",
            status="ready",
            mode=configured_mode,
            detail=("Pinned Meterless H-MEM reference engine, local persistent runtime"
                    if app_services.hmem.mode == "meterless_reference_local"
                    else "Working local H-MEM-compatible fallback; reference engine disabled"),
        ),
    ]


@router.get("/overview", response_model=OverviewResponse)
def overview(app_services: AppServices = Depends(services)) -> OverviewResponse:
    recent = app_services.investigations.list()[:5]
    return OverviewResponse(
        total_investigations=len(app_services.investigations.list()),
        recent_investigations=recent,
        connectivity=config_status(app_services),
    )


@router.get("/data/schema")
def data_schema() -> dict[str, object]:
    return {
        "dataset": "synthetic_retail",
        "adapter": "local_sqlite_demo",
        "tables": [{"name": name, "definition": definition} for name, definition in SCHEMA.items()],
    }


@router.get("/investigations", response_model=HistoryResponse)
def list_investigations(
    search: str | None = Query(default=None, max_length=200),
    status: InvestigationStatus | None = None,
    app_services: AppServices = Depends(services),
) -> HistoryResponse:
    items = app_services.investigations.list(search=search, status=status.value if status else None)
    return HistoryResponse(investigations=items, total=len(items))


@router.post("/investigations", response_model=Investigation, status_code=201)
def create_investigation(
    payload: InvestigationRequest,
    app_services: AppServices = Depends(services),
) -> Investigation:
    if payload.mode == Mode.LIVE:
        if not app_services.zetaris.configured or not app_services.nemotron.configured:
            raise HTTPException(status_code=503, detail="Live investigation execution requires configured Zetaris and Nemotron adapters")
    return app_services.workflow.run(payload)


@router.get("/investigations/{investigation_id}", response_model=Investigation)
def get_investigation(
    investigation_id: str,
    app_services: AppServices = Depends(services),
) -> Investigation:
    item = app_services.investigations.get(investigation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return item


@router.get("/investigations/{investigation_id}/report")
def download_report(
    investigation_id: str,
    format: Literal["json", "markdown"] = Query(default="json"),
    app_services: AppServices = Depends(services),
) -> Response:
    item = app_services.investigations.get(investigation_id)
    if not item or not item.report:
        raise HTTPException(status_code=404, detail="Completed report not found")
    if format == "json":
        body = json.dumps(item.report.model_dump(mode="json"), indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{investigation_id}.json"'},
        )
    body = report_markdown(item)
    return Response(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{investigation_id}.md"'},
    )


def report_markdown(item: Investigation) -> str:
    assert item.report is not None
    report = item.report
    lines = [
        f"# EvidenceTrail Investigation — {item.id}",
        "",
        f"**Question:** {report.question}",
        f"**Generated:** {report.generated_at.isoformat()}",
        "",
        "## Executive summary",
        report.executive_summary,
        "",
        "## Findings",
    ]
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.title}",
                finding.explanation,
                f"- Confidence: {finding.confidence:.0%}",
                f"- Causal claim: {finding.causal_claim}",
                f"- Uncertainty: {finding.uncertainty}",
                f"- Evidence IDs: {', '.join(finding.evidence_ids) or 'none'}",
                "",
            ]
        )
    lines.append("## Evidence")
    for evidence in report.evidence:
        lines.append(
            f"- **{evidence.evidence_id}** [{evidence.direction}] {evidence.statement} "
            f"(confidence {evidence.confidence:.0%})"
        )
    lines.extend(["", "## Recommended actions"])
    for recommendation in report.recommendations:
        lines.append(f"- **{recommendation.priority.upper()}** {recommendation.action} — {recommendation.rationale}")
    lines.extend(["", "## Uncertainty"])
    lines.extend(f"- {note}" for note in report.uncertainty)
    lines.extend(["", "## Memory trace", f"- Retrieved: {report.memory_trace.retrieved}", f"- Influenced plan: {report.memory_trace.influenced_plan}"])
    if report.memory_trace.note:
        lines.append(f"- Note: {report.memory_trace.note}")
    lines.extend(["", "## Query provenance"])
    for query in report.query_provenance:
        lines.append(f"- `{query.query_id}` ({query.row_count} rows): `{query.sql}`")
    return "\n".join(lines) + "\n"
