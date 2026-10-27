from __future__ import annotations

import re
from calendar import month_name

from app.models.domain import ParsedQuestion


MONTH_LOOKUP = {month_name[index].lower(): index for index in range(1, 13)}
MONTH_LOOKUP.update({"sept": 9, "sep": 9, "oct": 10, "nov": 11, "dec": 12})


def parse_question(question: str) -> ParsedQuestion:
    lower = question.lower()
    metric = "revenue" if any(token in lower for token in ("revenue", "sales", "selling")) else "units_sold"
    entities: list[str] = []
    for entity in ("stockout", "inventory", "supplier", "price", "pricing", "product", "category", "demand"):
        if entity in lower:
            entities.append(entity)

    period = _parse_period(lower)
    comparison = _previous_period(period) if period else "2025-08"
    intent = "explain_change"
    if "which" in lower or "top" in lower:
        intent = "rank_drivers"
    if "supplier" in lower:
        intent = "supplier_disruption"
    if "stockout" in lower or "inventory" in lower:
        intent = "availability_impact"
    if "price" in lower or "pricing" in lower:
        intent = "pricing_impact"

    keywords = sorted({token for token in re.findall(r"[a-z0-9]+", lower) if len(token) > 3})[:20]
    return ParsedQuestion(
        metric=metric,
        entities=entities,
        period=period or "2025-09",
        comparison_period=comparison,
        intent=intent,
        keywords=keywords,
    )


def _parse_period(question: str) -> str | None:
    year_match = re.search(r"\b(20\d{2})\b", question)
    year = int(year_match.group(1)) if year_match else 2025
    for name, number in MONTH_LOOKUP.items():
        if re.search(rf"\b{name}\b", question):
            return f"{year:04d}-{number:02d}"
    numeric = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", question)
    if numeric:
        return f"{numeric.group(1)}-{int(numeric.group(2)):02d}"
    return None


def _previous_period(period: str | None) -> str | None:
    if not period:
        return None
    year, month = (int(value) for value in period.split("-"))
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"
