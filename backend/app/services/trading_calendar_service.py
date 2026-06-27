"""Trading calendar helpers for Taiwan market data freshness checks."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent.parent.parent
TRADING_CALENDAR_PATH = _BACKEND / "data" / "trading_calendar.json"


def _parse_date_set(values: Any) -> set[date]:
    parsed: set[date] = set()
    if not isinstance(values, list):
        return parsed
    for value in values:
        try:
            parsed.add(date.fromisoformat(str(value)))
        except ValueError:
            continue
    return parsed


def _empty_calendar() -> dict[str, set[date]]:
    return {
        "holidays": set(),
        "makeup_trading_days": set(),
    }


def load_trading_calendar(path: Path | str | None = None) -> dict[str, set[date]]:
    """Load optional local holiday/makeup trading-day overrides.

    Missing or malformed files intentionally fall back to weekday-only logic so
    data freshness checks remain available even before a calendar is configured.
    """
    calendar_path = Path(path) if path is not None else TRADING_CALENDAR_PATH
    try:
        raw = json.loads(calendar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_calendar()
    if not isinstance(raw, dict):
        return _empty_calendar()
    return {
        "holidays": _parse_date_set(raw.get("holidays")),
        "makeup_trading_days": _parse_date_set(raw.get("makeup_trading_days")),
    }


def is_trading_day(day: date, calendar: dict[str, set[date]] | None = None) -> bool:
    """Return whether `day` should be treated as a completed trading session."""
    local_calendar = calendar if calendar is not None else load_trading_calendar()
    holidays = local_calendar.get("holidays", set())
    makeup_days = local_calendar.get("makeup_trading_days", set())
    if day in makeup_days:
        return True
    if day in holidays:
        return False
    return day.weekday() < 5


def previous_trading_day(day: date, calendar: dict[str, set[date]] | None = None) -> date:
    """Return the trading day immediately before `day`."""
    local_calendar = calendar if calendar is not None else load_trading_calendar()
    cursor = day - timedelta(days=1)
    while not is_trading_day(cursor, local_calendar):
        cursor -= timedelta(days=1)
    return cursor


def count_missed_trading_days_since(
    data_date: date,
    *,
    today: date | None = None,
    calendar: dict[str, set[date]] | None = None,
) -> int:
    """Count trading days after `data_date` and before `today`."""
    current_date = today or date.today()
    if data_date >= current_date:
        return 0
    local_calendar = calendar if calendar is not None else load_trading_calendar()
    count = 0
    cursor = data_date + timedelta(days=1)
    while cursor < current_date:
        if is_trading_day(cursor, local_calendar):
            count += 1
        cursor += timedelta(days=1)
    return count
