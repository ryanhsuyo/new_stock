"""Generate data coverage reports for tracked OHLCV symbols."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.services.trading_calendar_service import previous_trading_day
from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parent.parent.parent
LEADERS_PATH = _BACKEND / "data" / "leaders.json"
OHLCV_PATH = _BACKEND / "data" / "ohlcv.csv"
OUT_DIR = _BACKEND / "out"
DATA_COVERAGE_REPORT_NAME = "data_coverage_report.json"


def _flatten_codes(value: Any) -> list[str]:
    codes: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            codes.extend(_flatten_codes(item))
    elif isinstance(value, list):
        for item in value:
            codes.extend(_flatten_codes(item))
    elif isinstance(value, str):
        code = value.strip()
        if code:
            codes.append(code)
    return codes


def _load_tracked_codes(path: Path) -> list[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for code in _flatten_codes(raw):
        if code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _load_ohlcv_index(path: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    by_code: dict[str, dict[str, Any]] = {}
    raw_as_of: str | None = None
    try:
        handle = path.open(newline="", encoding="utf-8-sig")
    except OSError:
        return by_code, raw_as_of
    with handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = str(row.get("code") or "").strip()
            row_date = str(row.get("date") or "").strip()
            if not code or not row_date:
                continue
            try:
                date.fromisoformat(row_date)
            except ValueError:
                continue
            info = by_code.setdefault(code, {"row_count": 0, "last_data_as_of": None})
            info["row_count"] += 1
            if info["last_data_as_of"] is None or row_date > info["last_data_as_of"]:
                info["last_data_as_of"] = row_date
            if raw_as_of is None or row_date > raw_as_of:
                raw_as_of = row_date
    return by_code, raw_as_of


def _symbol_status(
    code: str,
    info: dict[str, Any] | None,
    *,
    expected_trading_day: str,
    minimum_rows: int,
) -> dict[str, Any]:
    if not info:
        return {
            "code": code,
            "row_count": 0,
            "last_data_as_of": None,
            "status": "missing",
            "reason": "ohlcv.csv 無此追蹤代碼資料",
        }
    row_count = int(info.get("row_count") or 0)
    last_data_as_of = info.get("last_data_as_of")
    if row_count < minimum_rows:
        status = "insufficient"
        reason = f"資料筆數 {row_count} 低於最低需求 {minimum_rows}"
    elif str(last_data_as_of or "") < expected_trading_day:
        status = "lagging"
        reason = f"最新資料日 {last_data_as_of or '—'} 落後預期交易日 {expected_trading_day}"
    else:
        status = "ok"
        reason = "資料已覆蓋最新預期交易日"
    return {
        "code": code,
        "row_count": row_count,
        "last_data_as_of": last_data_as_of,
        "status": status,
        "reason": reason,
    }


def build_data_coverage_report(
    *,
    leaders_path: Path = LEADERS_PATH,
    ohlcv_path: Path = OHLCV_PATH,
    batch_id: str | None = None,
    today: date | None = None,
    minimum_rows: int = 60,
) -> dict[str, Any]:
    """Build a generated coverage snapshot for all tracked symbols."""
    current_date = today or date.today()
    expected_day = previous_trading_day(current_date).isoformat()
    codes = _load_tracked_codes(Path(leaders_path))
    ohlcv, raw_as_of = _load_ohlcv_index(Path(ohlcv_path))
    symbols = [
        _symbol_status(
            code,
            ohlcv.get(code),
            expected_trading_day=expected_day,
            minimum_rows=minimum_rows,
        )
        for code in codes
    ]
    ok_count = sum(1 for item in symbols if item["status"] == "ok")
    tracked_count = len(symbols)
    coverage_pct = round((ok_count / tracked_count * 100), 2) if tracked_count else 0.0
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "batch_id": batch_id,
        "expected_trading_day": expected_day,
        "raw_ohlcv_as_of": raw_as_of,
        "tracked_count": tracked_count,
        "ok_count": ok_count,
        "coverage_pct": coverage_pct,
        "symbols": symbols,
    }


def write_data_coverage_report(report: dict[str, Any], out_dir: Path = OUT_DIR) -> Path:
    """Write generated coverage JSON under the given output directory."""
    path = Path(out_dir) / DATA_COVERAGE_REPORT_NAME
    atomic_write_text(path, json.dumps(report, ensure_ascii=False, indent=2))
    return path
