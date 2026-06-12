"""追蹤清單 leaders.json 的安全維護邏輯。"""

from __future__ import annotations

from pathlib import Path

from app.services.signals_service import _flatten_codes
from app.storage.leaders_store import load_leaders_raw, save_leaders_raw
from app.storage.name_store import load_stock_names, save_stock_names

MANUAL_GROUP = "手動追蹤"
BACKFILL_COMMAND = "python3 scripts/daily_update.py --months 12"
BACKEND_DIR = Path(__file__).resolve().parents[2]
BACKFILL_COPY_COMMAND = f"cd {BACKEND_DIR}\n{BACKFILL_COMMAND}"


def _clean_code(code: str) -> str:
    cleaned = code.strip().upper()
    if not cleaned:
        raise ValueError("股票代碼不可空白")
    if not cleaned.replace(".", "").isalnum():
        raise ValueError("股票代碼只能包含英數字或小數點")
    return cleaned


def _clean_name(name: str | None, code: str) -> str:
    cleaned = (name or "").strip()
    return cleaned or code


def add_stock_to_tracking(code: str, name: str | None = None, group: str = MANUAL_GROUP) -> dict:
    cleaned_code = _clean_code(code)
    cleaned_name = _clean_name(name, cleaned_code)
    group_name = (group or MANUAL_GROUP).strip() or MANUAL_GROUP

    raw = load_leaders_raw()
    if not isinstance(raw, dict):
        raw = {MANUAL_GROUP: _flatten_codes(raw)}

    existing_codes = set(_flatten_codes(raw))
    added = cleaned_code not in existing_codes
    if added:
        group_codes = raw.get(group_name)
        if not isinstance(group_codes, list):
            group_codes = []
        group_codes.append(cleaned_code)
        raw[group_name] = group_codes
        save_leaders_raw(raw)

    names = load_stock_names()
    if names.get(cleaned_code) != cleaned_name:
        names[cleaned_code] = cleaned_name
        save_stock_names(names)

    try:
        from app.services import signals_service

        signals_service._reload_name_cache()
    except Exception:
        pass

    return {
        "code": cleaned_code,
        "name": cleaned_name,
        "group": group_name,
        "added": added,
        "message": "已加入追蹤清單" if added else "此股票已在追蹤清單",
        "next_action_label": "回補日線資料",
        "next_action_command": BACKFILL_COMMAND,
        "next_action_copy_command": BACKFILL_COPY_COMMAND,
        "signals_refresh_required": True,
    }
