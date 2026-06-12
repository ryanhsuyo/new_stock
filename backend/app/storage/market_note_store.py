"""
market_note_store.py — 人工盤後筆記 JSON 存取。
"""

import json
from pathlib import Path

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parent.parent.parent
MARKET_NOTES_PATH = _BACKEND / "data" / "market_notes.json"


def load_market_notes() -> list[dict]:
    if not MARKET_NOTES_PATH.exists():
        return []
    try:
        raw = json.loads(MARKET_NOTES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def save_market_notes(notes: list[dict]) -> None:
    MARKET_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        MARKET_NOTES_PATH,
        json.dumps(notes, ensure_ascii=False, indent=2),
    )
