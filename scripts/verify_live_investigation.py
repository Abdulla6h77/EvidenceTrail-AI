"""Verify the running API; persist only reports/metadata, never credentials."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import httpx

phase = sys.argv[1]
if phase not in {"first", "second"}:
    raise ValueError("Use first or second")
root = Path(__file__).resolve().parents[1]
question = ("Why did sales decrease in September 2025?" if phase == "first"
            else "Why did sales decrease in September 2025 with stockouts?")
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=240) as client:
    status = client.get("/api/config/status")
    status.raise_for_status()
    memory_status = next(item for item in status.json() if item["name"] == "Meterless H-MEM")
    assert "reference engine" in memory_status["detail"]
    response = client.post("/api/investigations", json={"question": question, "mode": "live"})
    response.raise_for_status()
    result = response.json()
    target = root / "data" / f"live-verification-{phase}.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    report = result.get("report")
    output = {"phase": phase, "investigation_id": result["id"], "status": result["status"],
              "errors": result["errors"], "report_file": str(target)}
    if report:
        output.update({"summary": report["executive_summary"],
                       "query_count": len(report["query_provenance"]),
                       "rows": [q["row_count"] for q in report["query_provenance"]],
                       "adapters": sorted({q["adapter"] for q in report["query_provenance"]}),
                       "evidence_count": len(report["evidence"]),
                       "model": report["model_provenance"],
                       "stored_memory_id": report["memory_trace"]["stored_memory_id"],
                       "recalled_ids": report["memory_trace"]["memory_ids"],
                       "memory_influenced_plan": report["memory_trace"]["influenced_plan"]})
    print(json.dumps(output, indent=2))
    assert result["status"] == "completed", result["errors"]
    assert not result["errors"]
    assert output["adapters"] == ["zetaris_rest"]
    assert report["model_provenance"]["endpoint_host"] == "openrouter.ai"
    assert report["model_provenance"]["response_id"]
    if phase == "second":
        first = json.loads((root / "data" / "live-verification-first.json").read_text())
        prior_id = first["report"]["memory_trace"]["stored_memory_id"]
        assert prior_id in report["memory_trace"]["memory_ids"]
        assert any("Memory-informed check" in plan["purpose"] for plan in result["plan"]["plans"])
        assert client.get(f"/api/investigations/{first['id']}").json()["report"] == first["report"]
