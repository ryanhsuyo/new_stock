"""
update_store.py — 讀寫 backend/out/update_status.json

update_status.json 格式：
    {
        "last_run_started_at":  "2026-04-09T08:00:00",
        "last_run_finished_at": "2026-04-09T08:02:10",
        "last_run_status":      "success",   # success | failed | running | stale
        "last_error":           null,
        "last_warning":         null,
        "last_data_as_of":      "2026-04-09"
    }
"""

import json
from pathlib import Path

from app.storage.atomic_write import atomic_write_text

_OUT = Path(__file__).resolve().parent.parent.parent / "out"
UPDATE_STATUS_PATH = _OUT / "update_status.json"

_EMPTY: dict = {
    "last_run_started_at": None,
    "last_run_finished_at": None,
    "last_run_status": None,
    "last_error": None,
    "last_error_summary": None,
    "last_warning": None,
    "last_warning_summary": None,
    "last_data_as_of": None,
}


def load_update_status() -> dict:
    if not UPDATE_STATUS_PATH.exists():
        return dict(_EMPTY)
    try:
        return json.loads(UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(_EMPTY)


def save_update_status(status: dict) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        UPDATE_STATUS_PATH,
        json.dumps(status, ensure_ascii=False, indent=2),
    )
