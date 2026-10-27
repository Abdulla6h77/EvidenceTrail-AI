import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.integrations.nemotron import ModelUnavailableError, NemotronAdapter
from app.integrations.zetaris import ZetarisAdapter, ZetarisError


class Output(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_live_adapters_fail_explicitly_when_not_configured():
    settings = Settings(database_path="/tmp/evidencetrail-adapter-test.db")
    zetaris = ZetarisAdapter(settings)
    assert zetaris.configured is False
    assert (await zetaris.health())["status"] == "not_configured"
    with pytest.raises(ZetarisError, match="not configured"):
        await zetaris.execute("SELECT 1")

    nemotron = NemotronAdapter(settings)
    assert nemotron.status()["status"] == "not_configured"
    with pytest.raises(ModelUnavailableError, match="not configured"):
        await nemotron.structured_completion("system", "user", Output)
