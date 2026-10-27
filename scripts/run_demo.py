"""Run the two-investigation memory demo without starting a web server."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.core.container import build_services  # noqa: E402
from app.models.domain import InvestigationRequest  # noqa: E402


def main() -> None:
    services = build_services(Settings(database_path=str(ROOT / "data" / "evidencetrail.db")))
    first = services.workflow.run(
        InvestigationRequest(question="Why did sales decrease in September 2025?")
    )
    second = services.workflow.run(
        InvestigationRequest(question="Are stockouts contributing to lost sales in September 2025?")
    )
    print(
        json.dumps(
            {
                "investigation_a": {
                    "id": first.id,
                    "status": first.status,
                    "lead_finding": first.report.findings[0].title if first.report else None,
                    "stored_memory_id": first.report.memory_trace.stored_memory_id if first.report else None,
                },
                "investigation_b": {
                    "id": second.id,
                    "status": second.status,
                    "memory_retrieved": second.report.memory_trace.retrieved if second.report else False,
                    "memory_influenced_plan": second.report.memory_trace.influenced_plan if second.report else False,
                    "memory_query_added": bool(
                        second.plan
                        and any("Memory-informed check" in plan.purpose for plan in second.plan.plans)
                    ),
                },
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
