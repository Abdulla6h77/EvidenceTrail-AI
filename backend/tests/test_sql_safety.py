import pytest

from app.core.config import Settings
from app.core.container import build_services
from app.integrations.sql import QueryValidationError


def test_read_only_executor_adds_bound_and_rejects_writes(tmp_path):
    settings = Settings(database_path=str(tmp_path / "sql.db"))
    services = build_services(settings)

    result = services.sql.execute("SELECT * FROM products")
    assert result.error is None
    assert len(result.rows) == 6
    assert "LIMIT" in result.provenance.sql.upper()

    with pytest.raises(QueryValidationError):
        services.sql.execute("DELETE FROM products")
    with pytest.raises(QueryValidationError):
        services.sql.execute("SELECT * FROM products; SELECT * FROM suppliers")
