"""把系統自己發出過的 BUY 訊號前推，算出它們實際上表現如何。

前視偏誤是這個模組唯一真正的難點：快照的 as_of 是資料日，generated_at 才是訊號
實際存在的時點，兩者最多差 4 天。用 as_of 當進場基準會拿到當時還不存在的訊號。
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from app.services.signal_snapshot_service import SNAPSHOT_DIR_NAME
from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"

VALIDATION_FILENAME = "signal_forward_validation.json"
WINDOW_DAYS = 30
BUY_SIGNAL = "BUY"
US_TRACKABLE_BUCKET = "enter"

MARKET_TW = "tw"
MARKET_US = "us"
# 兩個市場的樣本不得混算：基準不同、訊號密度差一個量級
_MARKET_CONFIG = {
    MARKET_TW: {"snapshot_dir": "signal_snapshots", "benchmark": "0050",
                "glob": "signal_snapshot_*.json"},
    MARKET_US: {"snapshot_dir": "us_signal_snapshots", "benchmark": "SPY",
                "glob": "us_signal_snapshot_*.json"},
}
BENCHMARK_CODE = _MARKET_CONFIG[MARKET_TW]["benchmark"]

NO_STOP_DEFINED = "no_stop_defined"
EXIT_STOP = "stop"
EXIT_OPEN = "open_at_data_end"


def _parse_stop(text: Any) -> float | None:
    """失效條件是「跌破 2318.93」這種人看的字串，取其中的數字。"""
    match = re.search(r"(\d+(?:\.\d+)?)", str(text or ""))
    return float(match.group(1)) if match else None


def _next_market_day(market_days: list[str], after: str) -> str | None:
    for day in market_days:
        if day > after:
            return day
    return None


def _load_snapshots(snapshot_dir: Path, pattern: str = "signal_snapshot_*.json") -> list[dict[str, Any]]:
    if not snapshot_dir.exists():
        return []
    snapshots: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob(pattern)):
        try:
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return snapshots


def _window_start(as_of: str, window_days: int) -> str:
    return (date.fromisoformat(as_of) - timedelta(days=window_days)).isoformat()


def _us_stop_price(item: dict[str, Any]) -> float | None:
    """美股失效條件是「收盤跌破型態低 197.97；頸線進場停損 -7.5%」這種字串。

    只取第一個數字（型態低）。不用量幅目標當停利：紙上追蹤沒有定義停利動作，
    加一條當時不存在的規則會把贏家封頂、輸家留到停損，系統性美化績效。
    """
    return _parse_stop(item.get("invalidation"))


def collect_us_trackable_signals(
    snapshots: list[dict[str, Any]], window_start: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """只有「可紙上追蹤」桶計分；觀望名單沒有發生過進場，不能拿來充樣本。"""
    signals: list[dict[str, Any]] = []
    covered: list[str] = []
    for snapshot in snapshots:
        as_of = str(snapshot.get("as_of") or "")
        if not as_of or as_of < window_start:
            continue
        covered.append(as_of)
        available_at = str(snapshot.get("generated_at") or as_of)[:10]
        gates = snapshot.get("market_gates") or {}
        for item in snapshot.get("items") or []:
            if item.get("bucket") != US_TRACKABLE_BUCKET:
                continue
            signals.append({
                "code": str(item.get("code") or ""),
                "name": item.get("label"),
                "signal_date": as_of,
                "available_at": available_at,
                "stop_price": _us_stop_price(item),
                "invalidation_text": item.get("invalidation"),
                "market_filter": gates.get("trend_bias"),
                "market_regime": None,
                "pre_market_risk": None,
                "risk_source": "snapshot",
            })
    return signals, sorted(set(covered))


def collect_buy_signals(
    snapshots: list[dict[str, Any]], window_start: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """回傳窗口內的 BUY 訊號，以及實際有快照的日子。

    available_at 用 generated_at 而不是 as_of：訊號在產出之前不存在，
    拿 as_of 當可用時點等於偷看未來。
    """
    signals: list[dict[str, Any]] = []
    covered: list[str] = []
    for snapshot in snapshots:
        as_of = str(snapshot.get("as_of") or "")
        if not as_of or as_of < window_start:
            continue
        covered.append(as_of)
        available_at = str(snapshot.get("generated_at") or as_of)[:10]
        stored_risk = (snapshot.get("pre_market_risk") or {}).get("level")
        for item in snapshot.get("items") or []:
            if item.get("signal") != BUY_SIGNAL:
                continue
            signals.append({
                "code": str(item.get("code") or ""),
                "name": item.get("name"),
                "signal_date": as_of,
                "available_at": available_at,
                "stop_price": _parse_stop(item.get("daily_invalidation")),
                "invalidation_text": item.get("daily_invalidation"),
                # 舊快照沒存風控欄位；標成 rebuilt 才不會把事後重算當成當時記錄
                "market_filter": item.get("old_wang_market_filter"),
                "market_regime": item.get("old_wang_market_regime"),
                "pre_market_risk": stored_risk,
                "risk_source": "snapshot" if stored_risk else "rebuilt",
            })
    return signals, sorted(set(covered))


def _forward_trade(
    signal: dict[str, Any], prices: dict[str, dict[str, dict[str, float]]], market_days: list[str]
) -> dict[str, Any] | None:
    code = signal["code"]
    bars = prices.get(code) or {}
    if not bars:
        return None
    entry_day = _next_market_day([d for d in market_days if d in bars], signal["available_at"])
    if not entry_day:
        return None
    entry_price = bars[entry_day]["open"]
    held = [d for d in market_days if d >= entry_day and d in bars]

    exit_day, exit_price, exit_reason = held[-1], bars[held[-1]]["close"], EXIT_OPEN
    stop = signal["stop_price"]
    if stop is None:
        exit_reason = NO_STOP_DEFINED
    else:
        for day in held:
            if bars[day]["close"] < stop:
                nxt = _next_market_day([d for d in market_days if d in bars], day)
                exit_day = nxt or day
                exit_price = bars[nxt]["open"] if nxt else bars[day]["close"]
                exit_reason = EXIT_STOP
                break

    return {
        **signal,
        "entry_date": entry_day,
        "entry_price": round(entry_price, 4),
        "exit_date": exit_day,
        "exit_price": round(exit_price, 4),
        "exit_reason": exit_reason,
        "return_pct": round((exit_price - entry_price) / entry_price * 100, 2),
        "closed": exit_reason == EXIT_STOP,
    }


def _stats(returns: list[float]) -> dict[str, Any]:
    if not returns:
        return {"n": 0, "win_rate_pct": None, "avg_return_pct": None, "median_return_pct": None}
    wins = [value for value in returns if value > 0]
    return {
        "n": len(returns),
        "win_rate_pct": round(len(wins) / len(returns) * 100, 1),
        "avg_return_pct": round(sum(returns) / len(returns), 2),
        "median_return_pct": round(median(returns), 2),
    }


def _period_return(bars: dict[str, dict[str, float]], days: list[str]) -> float | None:
    usable = [d for d in days if d in bars]
    if len(usable) < 2:
        return None
    return (bars[usable[-1]]["close"] - bars[usable[0]]["open"]) / bars[usable[0]]["open"] * 100


def _market_reference(
    prices: dict[str, dict[str, dict[str, float]]],
    market_days: list[str],
    start: str,
    end: str,
    benchmark_code: str = BENCHMARK_CODE,
) -> dict[str, Any]:
    """策略報酬單看沒有意義：跌段裡「少跌」和「賺錢」長得完全不一樣。"""
    window = [d for d in market_days if start <= d <= end]
    returns = []
    for code, bars in prices.items():
        if code in {"TSE", "OTC"}:
            continue
        value = _period_return(bars, window)
        if value is not None:
            returns.append(value)
    benchmark = _period_return(prices.get(benchmark_code) or {}, window)
    return {
        "start": window[0] if window else None,
        "end": window[-1] if window else None,
        "universe_count": len(returns),
        "median_return_pct": round(median(returns), 2) if returns else None,
        "falling_ratio_pct": round(sum(1 for r in returns if r < 0) / len(returns) * 100, 1) if returns else None,
        "benchmark_code": benchmark_code,
        "benchmark_return_pct": round(benchmark, 2) if benchmark is not None else None,
    }


def build_signal_forward_validation(
    prices: dict[str, dict[str, dict[str, float]]],
    market_days: list[str],
    snapshot_dir: Path | None = None,
    window_days: int = WINDOW_DAYS,
    as_of: str | None = None,
    market: str = MARKET_TW,
) -> dict[str, Any]:
    config = _MARKET_CONFIG.get(market, _MARKET_CONFIG[MARKET_TW])
    snapshot_dir = snapshot_dir or (_OUT / config["snapshot_dir"])
    snapshots = _load_snapshots(snapshot_dir, config["glob"])
    data_as_of = as_of or (market_days[-1] if market_days else None)
    if not data_as_of:
        return _empty_result(window_days, None, "沒有可用的市場資料日", market=market)

    window_start = _window_start(data_as_of, window_days)
    collect = collect_us_trackable_signals if market == MARKET_US else collect_buy_signals
    signals, covered_days = collect(snapshots, window_start)
    if not signals:
        return _empty_result(
            window_days, data_as_of,
            "本窗口沒有可紙上追蹤的訊號" if market == MARKET_US else "本窗口無訊號",
            covered_days, window_start, market=market,
        )

    trades = [t for t in (_forward_trade(s, prices, market_days) for s in signals) if t]
    # 沒有失效價的訊號無從判斷出場，補值只會製造出一個不存在的規則
    scored = [t for t in trades if t["exit_reason"] != NO_STOP_DEFINED]
    returns = [t["return_pct"] for t in scored]

    return {
        "market": market,
        "as_of": data_as_of,
        "window_days": window_days,
        "window_start": window_start,
        "covered_snapshot_days": len(covered_days),
        "covered_dates": covered_days,
        "signal_count": len(signals),
        "evaluated_count": len(scored),
        "closed_count": sum(1 for t in scored if t["closed"]),
        "open_count": sum(1 for t in scored if not t["closed"]),
        "no_stop_defined_count": len(trades) - len(scored),
        "risk_source_counts": {
            source: sum(1 for t in trades if t["risk_source"] == source)
            for source in ("snapshot", "rebuilt")
        },
        "stats": _stats(returns),
        "market_reference": _market_reference(
            prices, market_days, window_start, data_as_of, config["benchmark"]
        ),
        "trades": trades,
        "note": "進場基準為快照 generated_at 之後的第一個交易日開盤；出場條件取訊號當日記錄的失效價。",
    }


def write_signal_forward_validation(
    result: dict[str, Any], out_dir: Path | None = None
) -> Path:
    out_dir = out_dir or _OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / VALIDATION_FILENAME
    atomic_write_text(path, json.dumps(result, ensure_ascii=False, indent=2))
    return path


def _empty_result(
    window_days: int,
    as_of: str | None,
    reason: str,
    covered: list[str] | None = None,
    window_start: str | None = None,
    market: str = MARKET_TW,
) -> dict[str, Any]:
    return {
        "market": market,
        "as_of": as_of,
        "window_days": window_days,
        "window_start": window_start,
        "covered_snapshot_days": len(covered or []),
        "covered_dates": covered or [],
        "signal_count": 0,
        "evaluated_count": 0,
        "closed_count": 0,
        "open_count": 0,
        "no_stop_defined_count": 0,
        "risk_source_counts": {"snapshot": 0, "rebuilt": 0},
        "stats": _stats([]),
        "market_reference": {},
        "trades": [],
        "note": reason,
    }
