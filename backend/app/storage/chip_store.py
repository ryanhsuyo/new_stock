"""
chip_store.py — 籌碼資料讀取

資料來源檔：backend/data/chips.json

第一版只負責讀取，不在 router / service 中硬編資料。
預期格式：
{
  "2330": {
    "data_as_of": "2026-05-06",
    "foreign_net_buy": 1200,
    "investment_trust_net_buy": 300,
    "retail_net_buy": -900,
    "major_investor_net_buy": 600
  }
}
"""

from __future__ import annotations

import json
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent.parent
CHIPS_PATH = _BACKEND / "data" / "chips.json"


def load_chips() -> dict[str, dict]:
    if not CHIPS_PATH.exists():
        return {}
    try:
        raw = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(code): item for code, item in raw.items() if isinstance(item, dict)}


def get_chip_metrics(code: str) -> dict:
    return load_chips().get(code, {})
