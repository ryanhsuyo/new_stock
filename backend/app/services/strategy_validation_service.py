"""Read-only adapter for generated Taiwan strategy portfolio replays."""

from __future__ import annotations

import json
import csv
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from app.storage.atomic_write import atomic_write_text

from app.services import signals_service as ss
from app.services.trade_service import calculate_trade_amounts
from app.storage.settings_store import load_trading_settings
from scripts.replay_tw_old_wang import _SyncPool


_BACKEND = Path(__file__).resolve().parent.parent.parent
OUT_DIR = _BACKEND / "out"
DATA_DIR = _BACKEND / "data"
REPORT_PATTERN = "tw_portfolio_replay_*.json"

MODE_LABELS = {
    "combined": "兩策略合併",
    "old_wang": "老王短波段",
    "steady_momentum": "穩健動能",
}
INITIAL_CASH = 1_000_000.0
SLIPPAGE_BPS = 10.0
EXCLUDED_CODES = {"0050", "0052", "2603", "6269"}


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _tradingview_url(code: str, market: str) -> str:
    exchange = "TPEX" if market == "TPEX" else "TWSE"
    symbol = quote(f"{exchange}:{code}", safe="")
    return f"https://www.tradingview.com/chart/?symbol={symbol}"


def _enrich_item(item: dict, names: dict[str, str], markets: dict[str, str]) -> dict:
    enriched = dict(item)
    code = str(item.get("code") or "")
    market = str(markets.get(code) or "TWSE")
    enriched.update({
        "name": names.get(code, code),
        "market": market,
        "tradingview_url": _tradingview_url(code, market),
        "analysis_hash": f"#/research/{code}",
    })
    return enriched


def load_strategy_validation_report(
    out_dir: Path = OUT_DIR,
    data_dir: Path = DATA_DIR,
    report_path: Path | None = None,
) -> dict | None:
    """Load the latest generated replay without recalculating strategy signals."""
    candidates = sorted(out_dir.glob(REPORT_PATTERN)) if report_path is None else [report_path]
    if not candidates:
        return None

    path = candidates[-1]
    payload = _load_json(path, None)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
        return None

    names = _load_json(data_dir / "stock_names.json", {})
    markets = _load_json(data_dir / "stock_markets.json", {})
    if not isinstance(names, dict):
        names = {}
    if not isinstance(markets, dict):
        markets = {}

    results: dict[str, dict] = {}
    for mode, raw_result in payload["results"].items():
        if not isinstance(raw_result, dict):
            continue
        result = dict(raw_result)
        result["mode_label"] = MODE_LABELS.get(mode, mode)
        result["trades"] = [
            _enrich_item(item, names, markets)
            for item in raw_result.get("trades", [])
            if isinstance(item, dict)
        ]
        result["open_positions"] = [
            _enrich_item(item, names, markets)
            for item in raw_result.get("open_positions", [])
            if isinstance(item, dict)
        ]
        results[mode] = result

    modified = datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return {
        "report_id": path.stem,
        "generated_at": modified,
        "config": payload.get("config") or {},
        "limitations": payload.get("limitations") or [],
        "results": results,
    }


def _load_prices(data_dir: Path) -> tuple[dict, list[str]]:
    prices: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    market_days: set[str] = set()
    with (data_dir / "ohlcv.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            code, day = row["code"], row["date"]
            if code in {"TSE", "OTC"}:
                market_days.add(day)
            try:
                prices[code][day] = {key: float(row[key]) for key in ("open", "high", "low", "close")}
            except (TypeError, ValueError, KeyError):
                continue
    return dict(prices), sorted(market_days)


def _affordable_shares(budget: float, price: float, settings: dict) -> int:
    low, high = 0, max(0, int(budget // price))
    while low < high:
        middle = (low + high + 1) // 2
        if calculate_trade_amounts("buy", price, middle, settings=settings)["net_amount"] <= budget:
            low = middle
        else:
            high = middle - 1
    return low


def _slipped(bar: dict, side: str) -> float:
    direction = 1 if side == "buy" else -1
    estimate = bar["open"] * (1 + direction * SLIPPAGE_BPS / 10_000)
    return min(bar["high"], max(bar["low"], estimate))


def _qualifies(signal: dict, mode: str) -> bool:
    if signal.get("daily_action") != "enter":
        return False
    return (mode in {"combined", "old_wang"} and bool(signal.get("old_wang_flag"))) or (
        mode in {"combined", "steady_momentum"} and bool(signal.get("steady_momentum_flag"))
    )


def _strategy_tag(signal: dict) -> str:
    tags = [key for key in ("old_wang", "steady_momentum") if signal.get(f"{key}_flag")]
    return "+".join(tags) or "none"


def _run_mode(mode: str, days: list[str], portfolio_start: str, prices: dict, settings: dict) -> dict:
    codes, groups = ss._load_leaders(), ss._load_leader_groups()
    stock_markets, fundamentals = ss.load_stock_markets(), ss.load_fundamentals()
    cash, positions, pending, trades, curve = INITIAL_CASH, {}, [], [], []
    total_fees = total_tax = 0.0

    def equity(day: str) -> float:
        value = cash
        for code, position in positions.items():
            bar = prices.get(code, {}).get(day)
            if bar:
                value += calculate_trade_amounts("sell", bar["close"], position["shares"], settings=settings)["net_amount"]
        return value

    for day in days:
        orders, pending = pending, []
        for order in [item for item in orders if item["side"] == "sell"]:
            code, position, bar = order["code"], positions.get(order["code"]), prices.get(order["code"], {}).get(day)
            if not position or not bar:
                continue
            shares = position["shares"] if order["kind"] == "exit" else max(1, position["shares"] // 2)
            fill = _slipped(bar, "sell")
            amounts = calculate_trade_amounts("sell", fill, shares, settings=settings)
            allocated_cost = position["entry_cost"] * shares / position["shares"]
            cash += amounts["net_amount"]
            total_fees += amounts["fee"]
            total_tax += amounts["tax"]
            trades.append({"code": code, "side": "sell", "signal_date": order["signal_date"], "fill_date": day, "fill_price": round(fill, 4), "shares": shares, "fee": amounts["fee"], "tax": amounts["tax"], "realized_pnl": round(amounts["net_amount"] - allocated_cost, 2), "reason": order["reason"], "strategy": position["strategy"]})
            if shares == position["shares"]:
                del positions[code]
            else:
                position["shares"] -= shares
                position["entry_cost"] -= allocated_cost

        current_equity = equity(day)
        entries = sorted((item for item in orders if item["side"] == "buy"), key=lambda item: (-item["priority"], -item["score"], item["code"]))
        for order in entries:
            code, bar = order["code"], prices.get(order["code"], {}).get(day)
            if code in positions or code in EXCLUDED_CODES or not bar:
                continue
            fill = _slipped(bar, "buy")
            shares = _affordable_shares(min(cash, current_equity * order["position_size_pct"] / 100), fill, settings)
            if shares <= 0:
                continue
            amounts = calculate_trade_amounts("buy", fill, shares, settings=settings)
            cash -= amounts["net_amount"]
            total_fees += amounts["fee"]
            positions[code] = {"shares": shares, "entry_cost": amounts["net_amount"], "entry_date": day, "entry_price": fill, "strategy": order["strategy"]}
            trades.append({"code": code, "side": "buy", "signal_date": order["signal_date"], "fill_date": day, "fill_price": round(fill, 4), "shares": shares, "fee": amounts["fee"], "tax": 0.0, "realized_pnl": None, "reason": order["reason"], "strategy": order["strategy"]})

        if day >= portfolio_start:
            curve.append({"date": day, "equity": round(equity(day), 2)})
        ohlcv = ss._load_ohlcv(day)
        context = ss._market_context(ohlcv)
        context.update({"stock_markets": stock_markets, "sector_rotation": ss._sector_rotation_context(groups, ohlcv), "fundamentals": fundamentals})
        portfolio = {"cash": cash, "holdings": {code: {"shares": value["shares"], "avg_cost": value["entry_cost"] / value["shares"]} for code, value in positions.items()}, "source": "replay"}
        signals = ss._run_signal_batch(codes, ohlcv, portfolio, context, timeout_seconds=999, pool_factory=_SyncPool)
        ss._annotate_holding_weights(signals, portfolio)
        ss._annotate_daily_decisions(signals)
        for signal in signals:
            code, action = signal.get("code"), signal.get("daily_action")
            if not code or code in EXCLUDED_CODES:
                continue
            if code in positions and action in {"exit", "reduce"}:
                pending.append({"side": "sell", "kind": action, "code": code, "signal_date": day, "reason": signal.get("daily_action_reason", "")})
            elif code not in positions and _qualifies(signal, mode):
                pending.append({"side": "buy", "code": code, "signal_date": day, "position_size_pct": int(signal.get("position_size_pct") or 0), "priority": int(signal.get("daily_priority") or 0), "score": int(signal.get("score") or 0), "reason": signal.get("daily_action_reason", ""), "strategy": _strategy_tag(signal)})

    final_day, final_equity = days[-1], equity(days[-1])
    peak, max_drawdown = INITIAL_CASH, 0.0
    for point in curve:
        peak = max(peak, point["equity"])
        max_drawdown = max(max_drawdown, (peak - point["equity"]) / peak * 100)
    open_positions = []
    for code, position in sorted(positions.items()):
        close = prices[code][final_day]["close"]
        liquidation = calculate_trade_amounts("sell", close, position["shares"], settings=settings)["net_amount"]
        open_positions.append({"code": code, **position, "close": close, "estimated_liquidation_value": liquidation, "unrealized_pnl_after_exit_cost": round(liquidation - position["entry_cost"], 2)})
    realized = sum(item["realized_pnl"] or 0 for item in trades if item["side"] == "sell")
    return {"mode": mode, "initial_cash": INITIAL_CASH, "start_date": portfolio_start, "end_date": final_day, "final_equity_after_estimated_liquidation_cost": round(final_equity, 2), "net_pnl": round(final_equity - INITIAL_CASH, 2), "return_pct": round((final_equity / INITIAL_CASH - 1) * 100, 4), "max_drawdown_pct": round(max_drawdown, 2), "realized_pnl": round(realized, 2), "total_fees": round(total_fees, 2), "total_tax": round(total_tax, 2), "trade_event_count": len(trades), "buy_count": sum(item["side"] == "buy" for item in trades), "sell_count": sum(item["side"] == "sell" for item in trades), "cash": round(cash, 2), "open_positions": open_positions, "trades": trades, "equity_curve": curve}


def run_strategy_validation(start: str, end: str, out_dir: Path = OUT_DIR, data_dir: Path = DATA_DIR) -> dict:
    """Run and persist a complete D-close/D+1-open replay for a requested date range."""
    try:
        start_dt, end_dt = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("日期格式必須是 YYYY-MM-DD") from exc
    if start_dt > end_dt:
        raise ValueError("開始日期不可晚於結束日期")
    prices, market_days = _load_prices(data_dir)
    in_range = [day for day in market_days if start <= day <= end]
    prior = [day for day in market_days if day < start]
    if not in_range:
        raise ValueError("所選區間沒有可用的市場交易資料")
    if not prior:
        raise ValueError("開始日期之前至少需要一個交易日以產生 D+1 成交")
    signal_days = [prior[-1], *in_range]
    settings = load_trading_settings()
    payload = {"config": {"signal_start": prior[-1], "portfolio_start": in_range[0], "requested_start": start, "requested_end": end, "end": in_range[-1], "initial_cash": INITIAL_CASH, "slippage_bps": SLIPPAGE_BPS, "odd_lot_shares": True, "entry": "D close daily_action=enter and official strategy flag; D+1 open", "exit": "daily_action=exit: all; reduce: half; D+1 open", "excluded_codes": sorted(EXCLUDED_CODES), "final_value": "cash + estimated net liquidation at final close"}, "limitations": ["Paper portfolio, not broker fills.", "Universe and fundamentals use current snapshots; survivor/history bias remains.", "TWSE prices are not fully corporate-action adjusted; known polluted codes excluded.", "No dividends; 10 bps slippage; current fee/tax settings; odd lots allowed."], "results": {}}
    for mode in MODE_LABELS:
        payload["results"][mode] = _run_mode(mode, signal_days, in_range[0], prices, settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"tw_portfolio_replay_{in_range[0]}_{in_range[-1]}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_strategy_validation_report(out_dir, data_dir, path) or payload


# ── 背景執行層 ──────────────────────────────────────────────────────────────
# 全窗口回放要逐日重跑訊號管線（~1-2 秒/交易日，一年 ≈ 數分鐘）。同步 HTTP
# 請求會長時間佔住 threadpool、且瀏覽器/代理容易逾時——因此 POST 只觸發背景
# 執行緒（同 us_update_service 模式），結果由既有 GET 讀持久化報告。

_VALIDATION_LOCK = threading.Lock()
VALIDATION_STATUS_PATH = OUT_DIR / "strategy_validation_status.json"
_EMPTY_VALIDATION_STATUS = {"status": "idle", "started_at": None, "finished_at": None,
                            "error": None, "start": None, "end": None}


def load_validation_status() -> dict:
    try:
        value = json.loads(VALIDATION_STATUS_PATH.read_text(encoding="utf-8"))
        return {**_EMPTY_VALIDATION_STATUS, **value} if isinstance(value, dict) else dict(_EMPTY_VALIDATION_STATUS)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_EMPTY_VALIDATION_STATUS)


def _save_validation_status(status: dict) -> None:
    VALIDATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(VALIDATION_STATUS_PATH,
                      json.dumps({**_EMPTY_VALIDATION_STATUS, **status}, ensure_ascii=False, indent=2))


def _validation_worker(start: str, end: str, started_at: str) -> None:
    try:
        run_strategy_validation(start, end)
        _save_validation_status({"status": "success", "started_at": started_at,
                                 "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                 "start": start, "end": end})
    except Exception as exc:  # 背景邊界：任何失敗都要落到狀態檔，不能無聲消失
        _save_validation_status({"status": "failed", "started_at": started_at,
                                 "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                 "error": str(exc), "start": start, "end": end})
    finally:
        _VALIDATION_LOCK.release()


def trigger_background_validation(start: str, end: str) -> dict:
    """快速驗證參數後啟動背景回放；已在執行中丟 RuntimeError（router 轉 409）。"""
    try:
        start_dt, end_dt = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(end, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("日期格式必須是 YYYY-MM-DD") from exc
    if start_dt > end_dt:
        raise ValueError("開始日期不可晚於結束日期")
    if not _VALIDATION_LOCK.acquire(blocking=False):
        raise RuntimeError("策略驗收回放已在執行中")
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    status = {"status": "running", "started_at": started_at, "start": start, "end": end}
    _save_validation_status(status)
    threading.Thread(target=_validation_worker, args=(start, end, started_at), daemon=True).start()
    return dict(_EMPTY_VALIDATION_STATUS, **status)
