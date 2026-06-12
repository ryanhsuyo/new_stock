"""leaders.json 讀寫層。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
LEADERS_PATH = _DATA / "leaders.json"


def load_leaders_raw() -> Any:
    if not LEADERS_PATH.exists():
        return {}
    try:
        return json.loads(LEADERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_leaders_raw(data: Any) -> None:
    atomic_write_text(
        LEADERS_PATH,
        json.dumps(data, ensure_ascii=False, indent=2),
    )
