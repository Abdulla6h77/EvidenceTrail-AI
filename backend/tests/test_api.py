from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_health_investigation_history_and_download(tmp_path):
    app = create_app(Settings(database_path=str(tmp_path / "api.db")))
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        schema = client.get("/api/data/schema")
        assert schema.status_code == 200
        assert {table["name"] for table in schema.json()["tables"]} >= {"monthly_sales", "inventory", "supplier_delays"}

        created = client.post(
            "/api/investigations",
            json={"question": "Why did sales decrease in September 2025?", "mode": "demo"},
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["status"] == "completed"
        investigation_id = payload["id"]

        history = client.get("/api/investigations")
        assert history.status_code == 200
        assert history.json()["total"] == 1

        markdown = client.get(f"/api/investigations/{investigation_id}/report?format=markdown")
        assert markdown.status_code == 200
        assert "EvidenceTrail Investigation" in markdown.text

        live = client.post(
            "/api/investigations",
            json={"question": "Why did sales decrease in September 2025?", "mode": "live"},
        )
        assert live.status_code == 503
        assert "Live investigation execution" in live.json()["detail"]
