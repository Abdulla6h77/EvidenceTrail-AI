import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.integrations.hmem import ReferenceHMEMStore


def test_reference_persistence_trust_and_feedback(tmp_path):
    store = ReferenceHMEMStore(tmp_path)
    content = "September stockouts and supplier delays reduced retail sales"
    record = store.add_summary(content, "inv-proof", ["retail"], [], 0.9,
                               provenance_refs=["evidence:inv-proof:E1"])
    restarted = ReferenceHMEMStore(tmp_path)
    result = restarted.retrieve(content)
    assert result.retrieved[0].id == record.id
    assert result.retrieved[0].provenance["refs"][-1] == "evidence:inv-proof:E1"
    assert result.context and result.scores[record.id] >= 0.35
    restarted.feedback(record.id, "wrong")
    snapshot = ReferenceHMEMStore(tmp_path).inspect()
    assert snapshot["records"][0]["confidence"] == pytest.approx(0.7)
    assert snapshot["records"][0]["accessCount"] == 1
    assert "review" in snapshot["records"][0]["tags"]
    assert [entry["action"] for entry in snapshot["ledger"]] == ["create", "read", "feedback"]


def test_corrupt_reference_state_fails_without_overwrite(tmp_path):
    (tmp_path / "state.json").write_text("broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Meterless reference engine failed"):
        ReferenceHMEMStore(tmp_path)
    assert (tmp_path / "state.json").read_text() == "broken"


def test_fastapi_restart_in_separate_processes(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts" / "hmem_restart_demo.py"
    outputs = []
    for phase in ("write", "recall"):
        completed = subprocess.run(
            [sys.executable, str(script), phase, str(tmp_path / "restart.db")],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=45,
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0]["pid"] != outputs[1]["pid"]
    assert outputs[0]["memory_id"] in outputs[1]["recalled_ids"]
    assert outputs[1]["memory_influenced_plan"]
    assert outputs[1]["prior_report_preserved"]
