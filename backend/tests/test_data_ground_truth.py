import sqlite3

from app.core.config import Settings
from app.core.container import build_services


def test_synthetic_ground_truth_contains_known_scenarios(tmp_path):
    services = build_services(Settings(database_path=str(tmp_path / "ground-truth.db")))
    with sqlite3.connect(services.database.path) as connection:
        september = connection.execute(
            "SELECT SUM(revenue) FROM monthly_sales WHERE month='2025-09'"
        ).fetchone()[0]
        august = connection.execute(
            "SELECT SUM(revenue) FROM monthly_sales WHERE month='2025-08'"
        ).fetchone()[0]
        p100_stockouts = connection.execute(
            "SELECT stockout_days FROM inventory WHERE product_id='P-100' AND month='2025-09'"
        ).fetchone()[0]
        supplier_delay = connection.execute(
            "SELECT delay_days FROM supplier_delays WHERE supplier_id='S-10' AND month='2025-09'"
        ).fetchone()[0]
        december_units = connection.execute(
            "SELECT SUM(units_sold) FROM monthly_sales WHERE month='2025-12'"
        ).fetchone()[0]
        january_units = connection.execute(
            "SELECT SUM(units_sold) FROM monthly_sales WHERE month='2025-01'"
        ).fetchone()[0]

    assert september < august
    assert p100_stockouts >= 10
    assert supplier_delay >= 7
    assert december_units > january_units
