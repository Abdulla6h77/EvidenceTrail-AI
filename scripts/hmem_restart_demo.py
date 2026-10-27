"""Run write and recall as separate Python processes against a disposable DB.

backend/.venv/Scripts/python scripts/hmem_restart_demo.py write data/hmem-proof.db
backend/.venv/Scripts/python scripts/hmem_restart_demo.py recall data/hmem-proof.db
Explicit test opt-in only: does not change environment files or default settings.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app

phase, db = sys.argv[1:]
if phase not in {"write", "recall"}:
    raise ValueError("phase must be write or recall")
settings = Settings(database_path=str(Path(db).resolve()), meterless_hmem_enabled=True)
question = "Why did sales decrease in September 2025?"
if phase == "recall":
    question = "Why did sales decrease in September 2025 with stockouts?"
with TestClient(create_app(settings)) as client:
    history = client.get("/api/investigations").json()["investigations"]
    response = client.post("/api/investigations", json={"question": question, "mode": "demo"})
    response.raise_for_status()
    result = response.json()
    assert result["status"] == "completed", result.get("errors")
    trace = result["report"]["memory_trace"]
    output = {"phase": phase, "pid": os.getpid(), "investigation_id": result["id"],
              "memory_id": trace["stored_memory_id"], "recalled_ids": trace["memory_ids"],
              "memory_influenced_plan": trace["influenced_plan"]}
    if phase == "recall":
        assert history, "Run the write phase first"
        prior = history[0]
        old = client.get(f"/api/investigations/{prior['id']}").json()
        output["prior_report_preserved"] = old["report"] == prior["report"]
        assert prior["report"]["memory_trace"]["stored_memory_id"] in trace["memory_ids"]
        assert trace["influenced_plan"]
        assert any("Memory-informed check" in plan["purpose"] for plan in result["plan"]["plans"])
        assert any("[MEMORY CONTEXT]" in event for event in result["tool_events"])
    print(json.dumps(output))
