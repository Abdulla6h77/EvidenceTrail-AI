from __future__ import annotations

import uuid
import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Callable

from app.core.config import Settings
from app.integrations.hmem import HMEMAdapter
from app.integrations.nemotron import NemotronAdapter
from app.integrations.zetaris import ZetarisAdapter
from pydantic import BaseModel, Field
from app.integrations.sql import ReadOnlySQLExecutor, rows_to_numeric
from app.models.domain import (
    EvidenceRecord,
    Finding,
    Investigation,
    InvestigationPlan,
    InvestigationReport,
    InvestigationRequest,
    InvestigationStatus,
    MemoryTrace,
    Mode,
    QueryPlan,
    QueryResult,
    Recommendation,
    StageName,
    StageStatus,
    StageUpdate,
)
from app.storage.investigations import InvestigationStore
from app.services.question_parser import parse_question


STAGE_LABELS = {
    StageName.UNDERSTAND: "Understand question",
    StageName.PLAN: "Create investigation plan",
    StageName.RETRIEVE: "Retrieve relevant data",
    StageName.EVALUATE: "Evaluate possible explanations",
    StageName.CHECK: "Check evidence and contradictions",
    StageName.REPORT: "Generate final report",
}


class ModelSynthesis(BaseModel):
    executive_summary: str = Field(min_length=20)
    evidence_ids: list[str] = Field(min_length=1)
    uncertainty: list[str] = Field(min_length=1)


class InvestigationWorkflow:
    def __init__(
        self,
        settings: Settings,
        executor: ReadOnlySQLExecutor,
        memory: HMEMAdapter,
        store: InvestigationStore,
        zetaris: ZetarisAdapter | None = None,
        nemotron: NemotronAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.executor = executor
        self.memory = memory
        self.store = store
        self.zetaris = zetaris
        self.nemotron = nemotron

    def run(self, request: InvestigationRequest) -> Investigation:
        investigation_id = f"inv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        investigation = Investigation(
            id=investigation_id,
            request=request,
            status=InvestigationStatus.RUNNING,
            created_at=now,
            updated_at=now,
            stages=[
                StageUpdate(name=name, label=label, status=StageStatus.PENDING)
                for name, label in STAGE_LABELS.items()
            ],
        )
        self.store.upsert(investigation)

        try:
            parsed = self._stage_understand(investigation)
            memory_trace = self.memory.retrieve(request.question)
            plan = self._stage_plan(investigation, parsed, memory_trace)
            query_results = self._stage_retrieve(investigation, plan)
            evidence = self._stage_evaluate(investigation, parsed, query_results)
            report = self._stage_check_and_report(
                investigation,
                parsed,
                plan,
                query_results,
                evidence,
                memory_trace,
            )
            investigation.status = InvestigationStatus.COMPLETED
            investigation.report = report
            investigation.updated_at = datetime.now(UTC)
            self.store.upsert(investigation)
            self._save_memory(investigation, report)
            return investigation
        except Exception as exc:
            investigation.status = InvestigationStatus.FAILED
            investigation.errors.append(f"Investigation failed: {type(exc).__name__}: {exc}")
            for stage in investigation.stages:
                if stage.status == StageStatus.RUNNING:
                    stage.status = StageStatus.FAILED
            investigation.updated_at = datetime.now(UTC)
            self.store.upsert(investigation)
            return investigation

    def _stage_understand(self, investigation: Investigation):
        self._start_stage(investigation, StageName.UNDERSTAND)
        parsed = parse_question(investigation.request.question)
        investigation.tool_events.append(
            f"Parsed metric={parsed.metric}, period={parsed.period}, comparison={parsed.comparison_period}, intent={parsed.intent}"
        )
        self._complete_stage(investigation, StageName.UNDERSTAND, "Question parsed into metric, entities, and comparison period")
        return parsed

    def _stage_plan(self, investigation: Investigation, parsed, memory_trace):
        self._start_stage(investigation, StageName.PLAN)
        if memory_trace.context:
            investigation.tool_events.append(
                "Prior memory context for planning (hypotheses to re-test, not new evidence):\n"
                + memory_trace.context
            )
        plans = self._build_plans(parsed, memory_trace)
        plan = InvestigationPlan(
            parsed_question=parsed,
            plans=plans,
            memory_ids=[record.id for record in memory_trace.retrieved],
            memory_influenced_plan=bool(memory_trace.retrieved),
            memory_note=memory_trace.retrieval_reason if memory_trace.retrieved else None,
        )
        investigation.plan = plan
        detail = f"Built {len(plans)} read-only query plans"
        if memory_trace.retrieved:
            detail += f"; reused {len(memory_trace.retrieved)} relevant prior investigation memory record(s)"
        investigation.tool_events.append(detail)
        self._complete_stage(investigation, StageName.PLAN, detail)
        return plan

    def _stage_retrieve(self, investigation: Investigation, plan: InvestigationPlan):
        self._start_stage(investigation, StageName.RETRIEVE)
        results: list[QueryResult] = []
        for query_plan in plan.plans:
            if investigation.request.mode == Mode.LIVE:
                if not self.zetaris:
                    raise RuntimeError("Zetaris live adapter is unavailable")
                result = asyncio.run(self.zetaris.execute(query_plan.sql))
            else:
                result = self.executor.execute(query_plan.sql)
            results.append(result)
            investigation.tool_events.append(
                f"Executed {result.provenance.query_id}: {result.provenance.row_count} row(s) from {query_plan.purpose}"
            )
            if result.error:
                investigation.errors.append(result.error)
                if investigation.request.mode == Mode.LIVE:
                    raise RuntimeError("Live SQL query failed; no demo fallback")
        investigation.queries = results
        self._complete_stage(
            investigation,
            StageName.RETRIEVE,
            f"Executed {len(results)} bounded read-only queries; {sum(len(result.rows) for result in results)} rows returned",
        )
        return results

    def _stage_evaluate(self, investigation: Investigation, parsed, results: list[QueryResult]):
        self._start_stage(investigation, StageName.EVALUATE)
        evidence = self._build_evidence(parsed, results)
        self._complete_stage(
            investigation,
            StageName.EVALUATE,
            f"Generated {len(evidence)} evidence records from returned values",
        )
        return evidence

    def _stage_check_and_report(
        self,
        investigation: Investigation,
        parsed,
        plan: InvestigationPlan,
        results: list[QueryResult],
        evidence: list[EvidenceRecord],
        memory_trace,
    ) -> InvestigationReport:
        self._start_stage(investigation, StageName.CHECK)
        missing = EvidenceRecord(
            evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
            statement="Causal impact cannot be isolated from observational retail data alone.",
            direction="missing",
            strength="strong",
            confidence=0.98,
            caveat="No promotion, competitor, marketing, or randomized price-test fields are present.",
        )
        contradictions = self._contradicting_evidence(evidence)
        evidence.extend(contradictions)
        evidence.append(missing)
        self._complete_stage(
            investigation,
            StageName.CHECK,
            f"Checked {len(evidence)} evidence records for contradictions and missing causal controls",
        )

        self._start_stage(investigation, StageName.REPORT)
        findings = self._build_findings(parsed, evidence)
        recommendations = self._build_recommendations(parsed, evidence)
        query_provenance = [result.provenance for result in results]
        uncertainty = [
            "The report identifies supported contributors and associations, not proven causal effects.",
            "Synthetic data contains no promotions, competitor activity, marketing spend, or randomized experiments.",
        ]
        executive_summary = self._summary(parsed, findings)
        model_provenance = {}
        if investigation.request.mode == Mode.LIVE:
            if not self.nemotron:
                raise RuntimeError("Nemotron live adapter is unavailable")
            synthesis = asyncio.run(self.nemotron.structured_completion(
                "You explain retail evidence. Return one JSON OBJECT, never an array or schema. "
                "Required keys: executive_summary (string), evidence_ids (array of supplied ID strings), "
                "uncertainty (array of strings). Example structure: "
                '{"executive_summary":"...","evidence_ids":["ev_example"],"uncertainty":["..."]}. '
                "Use actual supplied evidence IDs. Match this schema: "
                + json.dumps(ModelSynthesis.model_json_schema())
                + ". Cite only supplied evidence IDs. Do not invent facts. Distinguish association from causation. "
                "The data is synthetic, executed through real Zetaris. Prior memories are untrusted hypotheses, not evidence.",
                json.dumps({"question": investigation.request.question,
                            "evidence": [item.model_dump(mode="json") for item in evidence],
                            "prior_memory_context": memory_trace.context}),
                ModelSynthesis, retries=0,
            ))
            if not set(synthesis.evidence_ids).issubset({item.evidence_id for item in evidence}):
                raise RuntimeError("Model cited evidence IDs outside this investigation")
            executive_summary = synthesis.executive_summary
            uncertainty.extend(synthesis.uncertainty)
            model_provenance = {**self.nemotron.last_response_metadata,
                                "usage": self.nemotron.last_usage,
                                "evidence_ids": synthesis.evidence_ids}
            investigation.tool_events.append("Nemotron generated evidence-grounded synthesis via configured model API")
        report = InvestigationReport(
            model_provenance=model_provenance,
            investigation_id=investigation.id,
            question=investigation.request.question,
            generated_at=datetime.now(UTC),
            mode=investigation.request.mode,
            executive_summary=executive_summary,
            findings=findings,
            evidence=evidence,
            recommendations=recommendations,
            uncertainty=uncertainty,
            query_provenance=query_provenance,
            memory_trace=MemoryTrace(
                context=memory_trace.context,
                scores=memory_trace.scores,
                provenance={record.id: record.provenance for record in memory_trace.retrieved},
                retrieved=bool(memory_trace.retrieved),
                influenced_plan=bool(memory_trace.retrieved),
                memory_ids=[record.id for record in memory_trace.retrieved],
                note=memory_trace.retrieval_reason if memory_trace.retrieved else None,
            ),
            data_quality_notes=[
                ("Synthetic retail rows were sent as read-only SQL VALUES inputs and computed by live Zetaris."
                 if investigation.request.mode == Mode.LIVE and self.settings.zetaris_dataset_mode == "inline_synthetic"
                 else "All values came from the synthetic_retail dataset."),
                "Every evidence item links to a query provenance record when it is derived from retrieved data.",
            ],
        )
        self._complete_stage(investigation, StageName.REPORT, "Structured report assembled with provenance and uncertainty")
        return report

    def _build_plans(self, parsed, memory_trace) -> list[QueryPlan]:
        target = parsed.period or "2025-09"
        comparison = parsed.comparison_period or "2025-08"
        periods = f"'{comparison}','{target}'"
        plans = [
            QueryPlan(
                purpose="Compare total revenue and units across the target and prior month",
                hypothesis="The outcome changed at the aggregate level.",
                required_columns=["month", "revenue", "units_sold"],
                sql=(
                    "SELECT month, ROUND(SUM(revenue), 2) AS revenue, SUM(units_sold) AS units_sold "
                    f"FROM monthly_sales WHERE month IN ({periods}) GROUP BY month ORDER BY month"
                ),
            ),
            QueryPlan(
                purpose="Identify product-level revenue drivers and availability signals",
                hypothesis="A small number of products explain most of the change.",
                required_columns=["product_id", "name", "category", "month", "revenue", "units_sold", "stockout_days"],
                sql=(
                    "SELECT s.product_id, p.name, p.category, s.month, ROUND(s.revenue, 2) AS revenue, "
                    "s.units_sold, i.stockout_days, i.ending_inventory "
                    "FROM monthly_sales s JOIN products p ON p.product_id=s.product_id "
                    "JOIN inventory i ON i.product_id=s.product_id AND i.month=s.month "
                    f"WHERE s.month IN ({periods}) ORDER BY s.product_id, s.month"
                ),
            ),
            QueryPlan(
                purpose="Check price changes alongside unit demand",
                hypothesis="A price change is associated with a unit-demand change.",
                required_columns=["product_id", "month", "avg_price", "units_sold"],
                sql=(
                    "SELECT product_id, month, ROUND(AVG(unit_price), 2) AS avg_price, SUM(units_sold) AS units_sold "
                    f"FROM monthly_sales WHERE month IN ({periods}) GROUP BY product_id, month ORDER BY product_id, month"
                ),
            ),
            QueryPlan(
                purpose="Measure stockouts and ending inventory in the comparison window",
                hypothesis="Availability constraints may have limited observed sales.",
                required_columns=["month", "product_id", "name", "stockout_days", "ending_inventory"],
                sql=(
                    "SELECT i.month, i.product_id, p.name, i.stockout_days, i.ending_inventory "
                    "FROM inventory i JOIN products p ON p.product_id=i.product_id "
                    f"WHERE i.month IN ({periods}) ORDER BY i.month, i.stockout_days DESC"
                ),
            ),
            QueryPlan(
                purpose="Check supplier delivery delays associated with affected products",
                hypothesis="Supplier delays may be associated with availability disruptions.",
                required_columns=["month", "supplier_id", "name", "delay_days", "affected_pos"],
                sql=(
                    "SELECT d.month, d.supplier_id, s.name, d.delay_days, d.affected_pos "
                    "FROM supplier_delays d JOIN suppliers s ON s.supplier_id=d.supplier_id "
                    f"WHERE d.month IN ({periods}) ORDER BY d.month, d.delay_days DESC"
                ),
            ),
        ]
        if memory_trace.retrieved:
            memory_text = " ".join(record.content.lower() for record in memory_trace.retrieved)
            if "stockout" in memory_text or "availability" in memory_text or "supplier" in memory_text:
                plans.append(
                    QueryPlan(
                        purpose="Memory-informed check: re-test the prior availability pattern in the new period",
                        hypothesis="A prior investigation found availability evidence worth validating again.",
                        required_columns=["month", "product_id", "stockout_days"],
                        sql=(
                            "SELECT month, product_id, stockout_days FROM inventory "
                            f"WHERE month IN ({periods}) AND stockout_days > 0 ORDER BY stockout_days DESC"
                        ),
                    )
                )
        return plans

    def _build_evidence(self, parsed, results: list[QueryResult]) -> list[EvidenceRecord]:
        evidence: list[EvidenceRecord] = []
        total_result = next((result for result in results if "SUM(revenue)" in result.provenance.sql), None)
        if total_result and total_result.rows:
            rows_by_month = {row["month"]: row for row in total_result.rows}
            target = parsed.period or "2025-09"
            comparison = parsed.comparison_period or "2025-08"
            current = rows_by_month.get(target, {})
            prior = rows_by_month.get(comparison, {})
            current_revenue = float(current.get("revenue") or 0)
            prior_revenue = float(prior.get("revenue") or 0)
            change = current_revenue - prior_revenue
            pct = (change / prior_revenue * 100) if prior_revenue else 0
            direction = "supports" if change < 0 else "contradicts"
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                    statement=f"Revenue changed from ${prior_revenue:,.0f} in {comparison} to ${current_revenue:,.0f} in {target} ({pct:+.1f}%).",
                    direction=direction,
                    strength="strong",
                    confidence=0.99,
                    source_query_id=total_result.provenance.query_id,
                    source_fields=["month", "revenue", "units_sold"],
                    values={"target_revenue": current_revenue, "comparison_revenue": prior_revenue, "percent_change": round(pct, 2)},
                )
            )

        product_result = next((result for result in results if "FROM monthly_sales s" in result.provenance.sql), None)
        if product_result:
            grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
            for row in product_result.rows:
                grouped[str(row["product_id"])][str(row["month"])] = row
            target = parsed.period or "2025-09"
            comparison = parsed.comparison_period or "2025-08"
            for product_id, periods in grouped.items():
                current = periods.get(target)
                prior = periods.get(comparison)
                if not current or not prior:
                    continue
                change = float(current.get("revenue") or 0) - float(prior.get("revenue") or 0)
                if change < 0:
                    evidence.append(
                        EvidenceRecord(
                            evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                            statement=f"{current['name']} revenue fell by ${abs(change):,.0f} from {comparison} to {target}.",
                            direction="supports",
                            strength="strong" if abs(change) > 1000 else "moderate",
                            confidence=0.9,
                            source_query_id=product_result.provenance.query_id,
                            source_fields=["product_id", "month", "revenue", "stockout_days"],
                            values={"product_id": product_id, "revenue_change": round(change, 2), "stockout_days": current.get("stockout_days", 0)},
                        )
                    )

        availability_result = next((result for result in results if "FROM inventory i" in result.provenance.sql), None)
        if availability_result:
            target = parsed.period or "2025-09"
            comparison = parsed.comparison_period or "2025-08"
            target_rows = [row for row in availability_result.rows if row.get("month") == target]
            prior_rows = [row for row in availability_result.rows if row.get("month") == comparison]
            target_days = sum(int(row.get("stockout_days") or 0) for row in target_rows)
            prior_days = sum(int(row.get("stockout_days") or 0) for row in prior_rows)
            if target_days:
                direction = "supports" if target_days >= prior_days else "contradicts"
                evidence.append(
                    EvidenceRecord(
                        evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                        statement=f"Products recorded {target_days} total stockout days in {target}, versus {prior_days} in {comparison}.",
                        direction=direction,
                        strength="strong" if target_days > prior_days else "moderate",
                        confidence=0.9,
                        source_query_id=availability_result.provenance.query_id,
                        source_fields=["month", "product_id", "stockout_days", "ending_inventory"],
                        values={"target_stockout_days": target_days, "comparison_stockout_days": prior_days},
                        caveat="Stockouts indicate constrained availability; they do not by themselves prove lost demand or causality.",
                    )
                )

        price_result = next((result for result in results if "avg_price" in result.provenance.sql), None)
        if price_result:
            target = parsed.period or "2025-09"
            comparison = parsed.comparison_period or "2025-08"
            by_product: dict[str, dict[str, Any]] = defaultdict(dict)
            for row in price_result.rows:
                by_product[str(row["product_id"])][str(row["month"])] = row
            for product_id, periods in by_product.items():
                current = periods.get(target)
                prior = periods.get(comparison)
                if not current or not prior:
                    continue
                price_change = float(current.get("avg_price") or 0) - float(prior.get("avg_price") or 0)
                unit_change = int(current.get("units_sold") or 0) - int(prior.get("units_sold") or 0)
                if price_change > 0 and unit_change < 0:
                    evidence.append(
                        EvidenceRecord(
                            evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                            statement=f"{product_id} price rose ${price_change:,.2f} while units sold fell by {abs(unit_change)} from {comparison} to {target}.",
                            direction="supports",
                            strength="moderate",
                            confidence=0.78,
                            source_query_id=price_result.provenance.query_id,
                            source_fields=["product_id", "month", "avg_price", "units_sold"],
                            values={"product_id": product_id, "price_change": round(price_change, 2), "unit_change": unit_change},
                            caveat="This is an association; price response is confounded by availability and seasonality in this dataset.",
                        )
                    )

        supplier_result = next((result for result in results if "FROM supplier_delays" in result.provenance.sql), None)
        if supplier_result:
            target = parsed.period or "2025-09"
            delay_rows = [row for row in supplier_result.rows if row.get("month") == target and int(row.get("delay_days") or 0) > 0]
            for row in delay_rows:
                evidence.append(
                    EvidenceRecord(
                        evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                        statement=f"{row['name']} had a {row['delay_days']}-day delivery delay in {target}, affecting {row['affected_pos']} purchase order(s).",
                        direction="supports",
                        strength="moderate",
                        confidence=0.84,
                        source_query_id=supplier_result.provenance.query_id,
                        source_fields=["month", "supplier_id", "delay_days", "affected_pos"],
                        values={"supplier_id": row["supplier_id"], "delay_days": row["delay_days"], "affected_pos": row["affected_pos"]},
                    )
                )
        return evidence

    def _contradicting_evidence(self, evidence: list[EvidenceRecord]) -> list[EvidenceRecord]:
        revenue = next((item for item in evidence if "Revenue changed" in item.statement), None)
        declines = [item for item in evidence if "revenue fell" in item.statement]
        if revenue and revenue.direction == "supports" and len(declines) < 6:
            return [
                EvidenceRecord(
                    evidence_id=f"ev_{uuid.uuid4().hex[:10]}",
                    statement="Not every product declined in the comparison window; the aggregate change is concentrated rather than universal.",
                    direction="contradicts",
                    strength="moderate",
                    confidence=0.76,
                    caveat="The product query returned a limited synthetic catalog, so concentration should be rechecked on live data.",
                )
            ]
        return []

    def _build_findings(self, parsed, evidence: list[EvidenceRecord]) -> list[Finding]:
        findings: list[Finding] = []
        supports = [item for item in evidence if item.direction == "supports"]
        stockout_ids = [item.evidence_id for item in supports if "stockout" in item.statement.lower()]
        delay_ids = [item.evidence_id for item in supports if "delay" in item.statement.lower()]
        price_ids = [item.evidence_id for item in supports if "price rose" in item.statement.lower()]
        decline_ids = [item.evidence_id for item in supports if "revenue fell" in item.statement.lower()]
        if stockout_ids:
            findings.append(
                Finding(
                    finding_id=f"finding_{uuid.uuid4().hex[:10]}",
                    title="Repeated stockouts are a supported contributor",
                    explanation="The target period contains measurable stockout days and low ending inventory, which is consistent with constrained availability limiting observed sales.",
                    evidence_ids=stockout_ids + delay_ids,
                    supporting_evidence=stockout_ids + delay_ids,
                    confidence=0.86,
                    uncertainty="Stockouts support a possible contribution, but this dataset cannot separate unmet demand from lower demand.",
                    causal_claim="supported_contributor",
                )
            )
        if price_ids:
            findings.append(
                Finding(
                    finding_id=f"finding_{uuid.uuid4().hex[:10]}",
                    title="Price increases coincide with lower unit demand for affected products",
                    explanation="At least one product had a higher average price and fewer units sold in the target period.",
                    evidence_ids=price_ids,
                    supporting_evidence=price_ids,
                    confidence=0.75,
                    uncertainty="The observed association is confounded by stockouts and seasonality; no causal pricing experiment is available.",
                    causal_claim="possible_contributor",
                )
            )
        if decline_ids:
            findings.append(
                Finding(
                    finding_id=f"finding_{uuid.uuid4().hex[:10]}",
                    title="Revenue decline is concentrated in a subset of products",
                    explanation="The product comparison identifies which products account for the observed decline instead of attributing it to the whole catalog.",
                    evidence_ids=decline_ids,
                    supporting_evidence=decline_ids,
                    confidence=0.9,
                    uncertainty="The concentration result is descriptive and depends on the selected comparison period.",
                    causal_claim="not_established",
                )
            )
        contradiction_ids = [item.evidence_id for item in evidence if item.direction == "contradicts"]
        if contradiction_ids:
            findings.append(
                Finding(
                    finding_id=f"finding_{uuid.uuid4().hex[:10]}",
                    title="The evidence does not support a single universal explanation",
                    explanation="Contradicting evidence shows that the outcome is not moving uniformly across all products or factors.",
                    evidence_ids=contradiction_ids,
                    contradicting_evidence=contradiction_ids,
                    confidence=0.74,
                    uncertainty="A broader catalog or live dataset could reveal additional segments not represented in the demo.",
                    causal_claim="not_established",
                )
            )
        if not findings:
            findings.append(
                Finding(
                    finding_id=f"finding_{uuid.uuid4().hex[:10]}",
                    title="No supported driver was found in the selected window",
                    explanation="The retrieved data did not provide enough directional evidence to support one of the built-in hypotheses.",
                    confidence=0.35,
                    uncertainty="Investigate a broader period or connect a richer data source.",
                    causal_claim="not_established",
                )
            )
        return findings

    def _build_recommendations(self, parsed, evidence: list[EvidenceRecord]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        stockout_ids = [item.evidence_id for item in evidence if "stockout" in item.statement.lower()]
        delay_ids = [item.evidence_id for item in evidence if "delay" in item.statement.lower()]
        price_ids = [item.evidence_id for item in evidence if "price rose" in item.statement.lower()]
        if stockout_ids:
            recommendations.append(
                Recommendation(
                    action="Review replenishment thresholds and create an exception queue for products with repeated stockout days.",
                    rationale="Availability evidence is the strongest supported contributor in this investigation.",
                    priority="high",
                    evidence_ids=stockout_ids,
                )
            )
        if delay_ids:
            recommendations.append(
                Recommendation(
                    action="Ask affected suppliers for recovery dates and compare promised versus actual delivery performance.",
                    rationale="Delivery delay evidence is associated with the inventory disruptions in the target period.",
                    priority="high",
                    evidence_ids=delay_ids,
                )
            )
        if price_ids:
            recommendations.append(
                Recommendation(
                    action="Run a controlled price review for affected products before making a broad price rollback.",
                    rationale="Price and unit changes move together, but the current data does not establish causality.",
                    priority="medium",
                    evidence_ids=price_ids,
                )
            )
        recommendations.append(
            Recommendation(
                action="Add promotion, competitor, and lost-demand fields to the next investigation slice.",
                rationale="Those missing controls would reduce uncertainty around causal attribution.",
                priority="low",
                evidence_ids=[item.evidence_id for item in evidence if item.direction == "missing"],
            )
        )
        return recommendations

    def _summary(self, parsed, findings: list[Finding]) -> str:
        if not findings:
            return "The investigation did not find a supported explanation in the selected data window."
        lead = findings[0]
        return (
            f"For {parsed.period}, the strongest supported signal is {lead.title.lower()}. "
            f"The report distinguishes observed evidence from causal certainty and includes {len(findings)} finding(s) for follow-up."
        )

    def _save_memory(self, investigation: Investigation, report: InvestigationReport) -> None:
        lead = report.findings[0].title if report.findings else "No supported driver"
        summary = (
            f"Investigation {investigation.id} asked: {investigation.request.question}. "
            f"Period {investigation.plan.parsed_question.period if investigation.plan else 'unknown'}. "
            f"Lead finding: {lead}. "
            f"Evidence-backed summary: {report.executive_summary}"
        )
        tags = ["retail", "investigation", "evidence", investigation.plan.parsed_question.intent if investigation.plan else "explain_change"]
        if self.memory.mode == "meterless_reference_local":
            # Concise capture preserves retrieval signal; full evidence stays in the report.
            summary = f"{investigation.request.question} {lead}."
        entities = investigation.plan.parsed_question.entities if investigation.plan else []
        memory = self.memory.add_summary(
            content=summary,
            investigation_id=investigation.id,
            tags=tags,
            entities=entities,
            confidence=max((finding.confidence for finding in report.findings), default=0.5),
            provenance_refs=[f"query:{query.query_id}" for query in report.query_provenance],
        )
        if self.memory.mode == "meterless_reference_local":
            for finding in report.findings:
                self.memory.add_summary(
                    content=f"{investigation.request.question} {finding.title}: {finding.explanation} Uncertainty: {finding.uncertainty}",
                    investigation_id=investigation.id, tags=tags, entities=entities,
                    confidence=finding.confidence,
                    provenance_refs=[f"evidence:{investigation.id}:{evidence_id}" for evidence_id in finding.evidence_ids],
                )
        report.memory_trace.stored_memory_id = memory.id
        self.store.upsert(investigation)

    def _start_stage(self, investigation: Investigation, stage_name: StageName) -> None:
        for stage in investigation.stages:
            if stage.name == stage_name:
                stage.status = StageStatus.RUNNING
                stage.detail = None
        investigation.updated_at = datetime.now(UTC)
        self.store.upsert(investigation)

    def _complete_stage(self, investigation: Investigation, stage_name: StageName, detail: str) -> None:
        for stage in investigation.stages:
            if stage.name == stage_name:
                stage.status = StageStatus.COMPLETED
                stage.detail = detail
                stage.completed_at = datetime.now(UTC)
        investigation.updated_at = datetime.now(UTC)
        self.store.upsert(investigation)
