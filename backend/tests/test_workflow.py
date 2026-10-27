from app.core.config import Settings
from app.core.container import build_services
from app.models.domain import InvestigationRequest


def test_sales_decline_report_is_grounded_in_stockouts_and_supplier_delay(tmp_path):
    services = build_services(Settings(database_path=str(tmp_path / "workflow.db")))
    investigation = services.workflow.run(
        InvestigationRequest(question="Why did sales decrease in September 2025?")
    )

    assert investigation.status.value == "completed"
    assert not investigation.errors
    assert investigation.report is not None
    statements = [evidence.statement.lower() for evidence in investigation.report.evidence]
    assert any("revenue changed" in statement and "-" in statement for statement in statements)
    assert any("stockout" in statement for statement in statements)
    assert any("delivery delay" in statement for statement in statements)
    assert any(finding.causal_claim == "supported_contributor" for finding in investigation.report.findings)
    assert any(item.direction == "missing" for item in investigation.report.evidence)
    assert all("caus" not in finding.title.lower() or "causal" not in finding.explanation.lower() for finding in investigation.report.findings)


def test_hmem_memory_is_retrieved_and_changes_related_plan(tmp_path):
    services = build_services(Settings(database_path=str(tmp_path / "memory.db")))
    first = services.workflow.run(
        InvestigationRequest(question="Why did sales decrease in September 2025?")
    )
    second = services.workflow.run(
        InvestigationRequest(question="Are stockouts contributing to lost sales in September 2025?")
    )

    assert first.report is not None and second.report is not None
    assert first.report.memory_trace.retrieved is False
    assert first.report.memory_trace.stored_memory_id
    assert second.report.memory_trace.retrieved is True
    assert second.report.memory_trace.influenced_plan is True
    assert second.plan is not None
    assert any("Memory-informed check" in plan.purpose for plan in second.plan.plans)
    assert second.report.memory_trace.memory_ids
