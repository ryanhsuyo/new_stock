from __future__ import annotations

from copy import deepcopy
from typing import Any

RULES_VERSION = "rules-2026-06-30.1"
STRATEGY_PROFILE = "two_strategy_daily_v1"

_PARAMETERS: dict[str, Any] = {
    "MIN_ROWS": 60,
    "OLD_WANG_MARKET_MIN_ROWS": 10,
    "RSI_PERIOD": 14,
    "SR_LOOKBACK": 20,
    "BENCHMARK_CODE": "0050",
    "DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS": 20.0,
    "OLD_WANG_MA10_TOLERANCE_PCT": 0.002,
}

_STRATEGIES: dict[str, dict[str, Any]] = {
    "old_wang": {
        "id": "old_wang_market_chip_rotation",
        "name": "老王大盤籌碼輪動",
        "role": "短波段攻擊策略",
    },
    "steady_momentum": {
        "id": "steady_momentum_v1",
        "name": "Quality Momentum Lite",
        "role": "價格動能主線 + 輕量基本面避雷",
    },
    "core": {
        "id": "core_technical_v2",
        "name": "核心日線技術判斷",
        "role": "底層風控與買點分類",
    },
}


def build_rules_metadata() -> dict[str, Any]:
    return {
        "version": RULES_VERSION,
        "strategy_profile": STRATEGY_PROFILE,
        "generated_by": "rules_metadata_service",
        "parameters": deepcopy(_PARAMETERS),
        "strategies": deepcopy(_STRATEGIES),
    }
