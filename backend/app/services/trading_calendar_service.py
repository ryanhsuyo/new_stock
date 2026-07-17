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
        "presumed_closures": set(),
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
    presumed = _parse_date_set(raw.get("presumed_closures"))
    return {
        # 推定休市（見 reconcile_presumed_closures）視同 holiday 參與新鮮度判定
        "holidays": _parse_date_set(raw.get("holidays")) | presumed,
        "makeup_trading_days": _parse_date_set(raw.get("makeup_trading_days")),
        "presumed_closures": presumed,
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


def reconcile_presumed_closures(
    market_dates: set[date],
    *,
    window_start: date,
    today: date | None = None,
    path: Path | str | None = None,
) -> dict[str, list[str]]:
    """成功更新後呼叫：以「全市場整天無資料」推定臨時休市（颱風假等），並自我修復。

    - 加入：window_start ≤ D < today、平日、非既有假日/推定，且 D 不在 market_dates
      （資料源已成功抓過該窗口仍一列都沒有 → 幾乎確定休市）。
    - 移除：既有推定日後來出現資料（資料源晚到）→ 撤銷推定。
    人工維護的 holidays / makeup_trading_days 不受影響。失敗不 raise（呼叫端 best-effort）。
    """
    current = today or date.today()
    calendar_path = Path(path) if path is not None else TRADING_CALENDAR_PATH
    try:
        raw = json.loads(calendar_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, json.JSONDecodeError):
        raw = {}

    holidays = _parse_date_set(raw.get("holidays"))
    makeup = _parse_date_set(raw.get("makeup_trading_days"))
    presumed = _parse_date_set(raw.get("presumed_closures"))

    removed = sorted(d.isoformat() for d in presumed if d in market_dates)
    presumed = {d for d in presumed if d not in market_dates}

    added: list[str] = []
    if market_dates:
        cursor = max(window_start, min(market_dates))
        while cursor < current:
            base_trading_day = cursor in makeup or (cursor.weekday() < 5 and cursor not in holidays)
            if base_trading_day and cursor not in market_dates and cursor not in presumed:
                presumed.add(cursor)
                added.append(cursor.isoformat())
            cursor += timedelta(days=1)

    if added or removed:
        raw["presumed_closures"] = sorted(d.isoformat() for d in presumed)
        raw.setdefault(
            "note_presumed_closures",
            "由更新流程自動推定：全市場整天無資料的平日（如颱風假）。資料晚到會自動撤銷；人工假日請維護 holidays。",
        )
        try:
            calendar_path.parent.mkdir(parents=True, exist_ok=True)
            calendar_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return {"added": [], "removed": []}
    return {"added": added, "removed": removed}
