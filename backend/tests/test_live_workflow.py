import json
import uuid

import httpx
import pytest

from app.core.config import Settings
from app.core.container import build_services
from app.integrations.nemotron import ModelUnavailableError
from app.integrations.zetaris import ZetarisAdapter, ZetarisError, _extract_rows
from app.models.domain import InvestigationRequest
from app.services.investigation import ModelSynthesis


def test_zetaris_positional_results_and_invalid_shapes():
    assert _extract_rows({"headers": ["value"], "data": [["7"]], "total": 1}) == [{"value": "7"}]
    assert _extract_rows({"headers": ["value"], "data": [], "total": 0}) == []
    for payload in ({"error": "failed"}, {"headers": ["x"], "data": [[1, 2]]},
                    {"headers": ["x"], "data": [[1]], "total": 2}):
        with pytest.raises(ZetarisError):
            _extract_rows(payload)


@pytest.mark.asyncio
async def test_zetaris_request_contract_and_write_rejection(monkeypatch):
    calls = []
    def respond(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body["source"] == "SqlEditor"
        assert body["sql"] == "SELECT 1 AS value"
        assert uuid.UUID(body["queryId"])
        assert uuid.UUID(request.headers["X-Request-ID"])
        assert "select" not in body
        return httpx.Response(200, json={"headers": ["value"], "data": [["1"]], "total": 1})
    client_class = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client_class(transport=httpx.MockTransport(respond), **kw))
    adapter = ZetarisAdapter(Settings(_env_file=None, zetaris_base_url="http://test.invalid",
                                     zetaris_api_key="fixture", zetaris_org_id="fixture"))
    assert (await adapter.execute("SELECT 1 AS value")).rows == [{"value": "1"}]
    with pytest.raises(ValueError):
        await adapter.execute("DELETE FROM monthly_sales")
    assert len(calls) == 1


@pytest.mark.parametrize("model_fails", [False, True])
def test_live_workflow_uses_remote_queries_and_model_without_fallback(tmp_path, model_fails):
    services = build_services(Settings(_env_file=None, database_path=str(tmp_path / "live-test.db")))
    class TestZetaris:
        async def execute(self, sql):
            result = services.sql.execute(sql)
            result.provenance.adapter = "test_zetaris"
            return result
    class TestModel:
        last_response_metadata = {"response_id": "fixture-response", "endpoint_host": "test.invalid"}
        last_usage = {"total_tokens": 42}
        async def structured_completion(self, system, user, output_model, **kwargs):
            if model_fails:
                raise ModelUnavailableError("fixture model failure")
            evidence = json.loads(user)["evidence"]
            return ModelSynthesis(executive_summary="Test-only grounded analysis of the supplied evidence.",
                                  evidence_ids=[evidence[0]["evidence_id"]], uncertainty=["Synthetic fixture"])
    services.workflow.zetaris = TestZetaris()
    services.workflow.nemotron = TestModel()
    result = services.workflow.run(InvestigationRequest(question="Why did sales decrease in September 2025?", mode="live"))
    if model_fails:
        assert result.status == "failed"
        assert result.report is None
        assert not services.hmem.retrieve("sales September").retrieved
        assert any(stage.status == "failed" for stage in result.stages)
    else:
        assert result.status == "completed"
        assert {q.provenance.adapter for q in result.queries} == {"test_zetaris"}
        assert result.report.model_provenance["response_id"] == "fixture-response"
        assert result.report.executive_summary.startswith("Test-only")
