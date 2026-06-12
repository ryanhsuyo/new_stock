"""
name_store.py — stock_names.json 的讀寫層

stock_names.json 格式：{"code": "name", ...}
  - 由 backfill_ohlcv_twse.py 在每次 backfill 結束後寫入
  - 由 signals_service._stock_name() 讀取
"""

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
NAMES_PATH = _DATA / "stock_names.json"


def load_stock_names() -> dict[str, str]:
    if not NAMES_PATH.exists():
        return {}
    try:
        return json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_stock_names(names: dict[str, str]) -> None:
    _DATA.mkdir(parents=True, exist_ok=True)
    NAMES_PATH.write_text(
        json.dumps(names, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
