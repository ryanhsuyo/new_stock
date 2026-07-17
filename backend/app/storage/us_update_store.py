"""Persistent status for the US-only background backfill workflow."""

from __future__ import annotations

import json
from pathlib import Path

from app.storage.atomic_write import atomic_write_text

US_UPDATE_STATUS_PATH = Path(__file__).resolve().parent.parent.parent / "out" / "us_update_status.json"
EMPTY_STATUS = {"status": "idle", "started_at": None, "finished_at": None, "error": None, "months": None}


def load_us_update_status() -> dict:
    try:
        value = json.loads(US_UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        return {**EMPTY_STATUS, **value} if isinstance(value, dict) else dict(EMPTY_STATUS)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(EMPTY_STATUS)


def save_us_update_status(status: dict) -> None:
    US_UPDATE_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(US_UPDATE_STATUS_PATH, json.dumps({**EMPTY_STATUS, **status}, ensure_ascii=False, indent=2))
