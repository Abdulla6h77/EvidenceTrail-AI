"""Deterministic synthetic retail data with known investigation scenarios."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


MONTHS = [
    ("2025-01", 1),
    ("2025-02", 2),
    ("2025-03", 3),
    ("2025-04", 4),
    ("2025-05", 5),
    ("2025-06", 6),
    ("2025-07", 7),
    ("2025-08", 8),
    ("2025-09", 9),
    ("2025-10", 10),
    ("2025-11", 11),
    ("2025-12", 12),
]


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    category: str
    supplier_id: str
    base_price: float
    seasonal_multiplier: float


PRODUCTS = [
    Product("P-100", "Trail Running Shoes", "Footwear", "S-10", 120.0, 1.15),
    Product("P-200", "Everyday Sneakers", "Footwear", "S-20", 80.0, 1.05),
    Product("P-300", "Insulated Jacket", "Apparel", "S-10", 150.0, 1.35),
    Product("P-400", "Cotton T-Shirt", "Apparel", "S-30", 25.0, 1.10),
    Product("P-500", "Hiking Backpack", "Accessories", "S-20", 95.0, 1.20),
    Product("P-600", "Stainless Bottle", "Accessories", "S-30", 30.0, 1.00),
]

SUPPLIERS = [
    ("S-10", "Northstar Outfitters", "United States"),
    ("S-20", "Summit Supply Co.", "Canada"),
    ("S-30", "Urban Goods Manufacturing", "Vietnam"),
]


def _price(product: Product, month: int) -> float:
    if product.product_id == "P-100" and month >= 8:
        return 132.0
    if product.product_id == "P-500" and month >= 6:
        return 105.0
    return product.base_price


def _units(product: Product, month: int) -> int:
    seasonal = {11: 1.35, 12: 1.5, 1: 0.82, 2: 0.86}.get(month, 1.0)
    base = {
        "P-100": 140,
        "P-200": 170,
        "P-300": 95,
        "P-400": 320,
        "P-500": 125,
        "P-600": 250,
    }[product.product_id]
    demand = base * seasonal * product.seasonal_multiplier
    if product.product_id == "P-100" and month in {8, 9, 10}:
        demand *= {8: 0.88, 9: 0.70, 10: 0.78}[month]
    if product.product_id == "P-500" and month in {6, 7, 8}:
        demand *= 0.88
    return max(8, round(demand))


def _inventory(product: Product, month: int, units: int) -> tuple[int, int]:
    stockout_days = 0
    ending = max(10, units * 2)
    if product.product_id == "P-100" and month in {8, 9, 10}:
        stockout_days = {8: 4, 9: 11, 10: 8}[month]
        ending = {8: 24, 9: 7, 10: 16}[month]
    if product.product_id == "P-300" and month == 12:
        stockout_days = 3
        ending = 22
    if product.product_id == "P-500" and month in {6, 7}:
        stockout_days = 5 if month == 6 else 7
        ending = 18 if month == 6 else 12
    return ending, stockout_days


def build_rows() -> dict[str, list[dict[str, object]]]:
    products = [
        {
            "product_id": p.product_id,
            "name": p.name,
            "category": p.category,
            "supplier_id": p.supplier_id,
            "base_price": p.base_price,
        }
        for p in PRODUCTS
    ]
    monthly_sales: list[dict[str, object]] = []
    inventory: list[dict[str, object]] = []
    stockouts: list[dict[str, object]] = []
    purchase_orders: list[dict[str, object]] = []
    supplier_delays: list[dict[str, object]] = []

    for month_label, month in MONTHS:
        for product in PRODUCTS:
            units = _units(product, month)
            price = _price(product, month)
            ending, stockout_days = _inventory(product, month, units)
            monthly_sales.append(
                {
                    "month": month_label,
                    "product_id": product.product_id,
                    "units_sold": units,
                    "unit_price": price,
                    "revenue": round(units * price, 2),
                }
            )
            inventory.append(
                {
                    "month": month_label,
                    "product_id": product.product_id,
                    "ending_inventory": ending,
                    "stockout_days": stockout_days,
                }
            )
            if stockout_days:
                stockouts.append(
                    {
                        "event_id": f"SO-{product.product_id}-{month_label}",
                        "month": month_label,
                        "product_id": product.product_id,
                        "days": stockout_days,
                        "reason": "supplier delay" if product.product_id in {"P-100", "P-500"} else "demand spike",
                    }
                )
            if month in {6, 7, 8, 9, 10} and product.product_id in {"P-100", "P-500"}:
                purchase_orders.append(
                    {
                        "po_id": f"PO-{product.product_id}-{month_label}",
                        "month": month_label,
                        "product_id": product.product_id,
                        "supplier_id": product.supplier_id,
                        "ordered_units": 180 if product.product_id == "P-100" else 140,
                        "expected_days": 12,
                        "actual_days": 24 if product.product_id == "P-100" and month in {8, 9} else 19,
                    }
                )
        for supplier_id, _, _ in SUPPLIERS:
            if supplier_id == "S-10" and month in {8, 9, 10}:
                supplier_delays.append(
                    {
                        "delay_id": f"DL-{supplier_id}-{month_label}",
                        "month": month_label,
                        "supplier_id": supplier_id,
                        "delay_days": {8: 8, 9: 13, 10: 7}[month],
                        "affected_pos": 2,
                    }
                )
            elif supplier_id == "S-20" and month in {6, 7}:
                supplier_delays.append(
                    {
                        "delay_id": f"DL-{supplier_id}-{month_label}",
                        "month": month_label,
                        "supplier_id": supplier_id,
                        "delay_days": 6 if month == 6 else 9,
                        "affected_pos": 1,
                    }
                )

    return {
        "products": products,
        "suppliers": [
            {"supplier_id": sid, "name": name, "country": country}
            for sid, name, country in SUPPLIERS
        ],
        "monthly_sales": monthly_sales,
        "inventory": inventory,
        "stockouts": stockouts,
        "purchase_orders": purchase_orders,
        "supplier_delays": supplier_delays,
    }


SCHEMA = {
    "products": "product_id TEXT PRIMARY KEY, name TEXT, category TEXT, supplier_id TEXT, base_price REAL",
    "suppliers": "supplier_id TEXT PRIMARY KEY, name TEXT, country TEXT",
    "monthly_sales": "month TEXT, product_id TEXT, units_sold INTEGER, unit_price REAL, revenue REAL",
    "inventory": "month TEXT, product_id TEXT, ending_inventory INTEGER, stockout_days INTEGER",
    "stockouts": "event_id TEXT PRIMARY KEY, month TEXT, product_id TEXT, days INTEGER, reason TEXT",
    "purchase_orders": "po_id TEXT PRIMARY KEY, month TEXT, product_id TEXT, supplier_id TEXT, ordered_units INTEGER, expected_days INTEGER, actual_days INTEGER",
    "supplier_delays": "delay_id TEXT PRIMARY KEY, month TEXT, supplier_id TEXT, delay_days INTEGER, affected_pos INTEGER",
}


def seed_database(database_path: Path) -> Path:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        for table, definition in SCHEMA.items():
            connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.execute(f"CREATE TABLE {table} ({definition})")
            columns = list(rows[table][0].keys())
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                [[row[column] for column in columns] for row in rows[table]],
            )
        connection.commit()
    return database_path


def export_csv(output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    for table, table_rows in build_rows().items():
        if not table_rows:
            continue
        with (output_directory / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table_rows[0].keys()))
            writer.writeheader()
            writer.writerows(table_rows)


if __name__ == "__main__":
    from app.core.config import get_settings

    path = seed_database(get_settings().database_file)
    export_csv(Path(__file__).resolve().parents[3] / "data" / "synthetic_retail")
    print(f"Seeded synthetic retail database at {path}")
