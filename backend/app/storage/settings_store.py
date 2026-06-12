"""
settings_store.py — 本地設定讀取。

設定檔選填；不存在時回傳保守預設值。
"""
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "trading": {
        "brokerage_fee_rate": 0.001425,
        "brokerage_discount": 1.0,
        "min_brokerage_fee": 0,
        "sell_transaction_tax_rate": 0.003,
    }
}


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS
    if not isinstance(raw, dict):
        return DEFAULT_SETTINGS
    return _deep_merge(DEFAULT_SETTINGS, raw)


def load_trading_settings() -> dict[str, float]:
    settings = load_settings().get("trading") or {}
    return {
        "brokerage_fee_rate": float(settings.get("brokerage_fee_rate", 0.001425)),
        "brokerage_discount": float(settings.get("brokerage_discount", 1.0)),
        "min_brokerage_fee": float(settings.get("min_brokerage_fee", 0)),
        "sell_transaction_tax_rate": float(settings.get("sell_transaction_tax_rate", 0.003)),
    }
