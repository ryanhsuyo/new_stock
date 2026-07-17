"""Date-range validation adapter for the two approved US observation strategies."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from app.services.us_strategy_replay_service import RULE_TREND_PROTECT, run_replay
from app.services.us_wbottom_service import run_wbottom_replay
from app.storage.us_market_store import load_us_leaders, load_us_ohlcv


def _validate_range(start: str, end: str, available_dates: list[str]) -> tuple[str, str]:
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("日期格式必須是 YYYY-MM-DD") from exc
    if start_dt > end_dt:
        raise ValueError("開始日期不可晚於結束日期")
    dates = [day for day in available_dates if start <= day <= end]
    if not dates:
        raise ValueError("所選區間沒有可用的美股交易資料")
    return dates[0], dates[-1]


def _enrich_trade(trade: dict, names: dict[str, str], strategy: str) -> dict:
    item = dict(trade)
    code = str(item.get("code") or "")
    item.update({"name": names.get(code, code), "market": "US", "currency": "USD", "strategy": strategy,
                 "tradingview_url": f"https://www.tradingview.com/chart/?symbol={quote(code, safe='')}"})
    return item


def run_us_strategy_validation(start: str, end: str) -> dict:
    """Run both approved US strategy replays for an explicit signal window."""
    ohlcv, leaders = load_us_ohlcv(), load_us_leaders()
    all_dates = sorted({row["date"] for rows in ohlcv.values() for row in rows})
    actual_start, actual_end = _validate_range(start, end, all_dates)
    names = {str(item["code"]): str(item.get("name") or item["code"]) for item in leaders}
    trend = run_replay(actual_start, actual_end, ohlcv=ohlcv, leaders=leaders)
    wbottom = run_wbottom_replay(actual_start, actual_end, ohlcv=ohlcv, leaders=leaders)
    return {"region": "US", "currency": "USD", "requested_start": start, "requested_end": end,
            "start_date": actual_start, "end_date": actual_end,
            "method": "逐筆等權策略回放；不是 100 萬投組淨值，兩策略不可直接相加",
            "results": {
                "us_trend_follow": {"strategy": "us_trend_follow", "strategy_label": "趨勢延續",
                    "exit_rule": RULE_TREND_PROTECT, "summary": trend["summary"][RULE_TREND_PROTECT],
                    "trades": [_enrich_trade(item, names, "us_trend_follow") for item in trend["trades"][RULE_TREND_PROTECT]],
                    "limitations": trend["limitations"]},
                "us_wbottom_target": {"strategy": "us_wbottom_target", "strategy_label": "W 底突破 + 量幅目標",
                    "exit_rule": "target_or_pattern_low", "summary": wbottom["summary"],
                    "trades": [_enrich_trade(item, names, "us_wbottom_target") for item in wbottom["trades"]],
                    "limitations": wbottom["limitations"]}}}
