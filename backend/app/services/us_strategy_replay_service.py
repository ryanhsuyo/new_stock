"""
us_strategy_replay_service.py — us_trend_follow 歷史逐日回放（evaluation-only）。

**評估工具，非交易系統**：不下單、不推薦、不改 production 策略規則、不做參數最佳化。
用既有 ohlcv_us.csv 做 walk-forward 回放，檢查候選進出邏輯是否有問題（抖動 / 守門 /
邊界過緊），產出證據供人工判讀。

Walk-forward 保證：對每個交易日 D，指標一律由 `date <= D` 的切片重新計算
（_build_asof_item 只吃 rows_asof），不預先用全量資料算 rolling 再切日期。
候選條件直接呼叫 production 的 classify_trend_follow（單一規則來源，不複製）。

成交時點：D 日收盤成為 candidate → 模擬進場用 D+1 交易日的 open；
無下一交易日 open → unresolved（絕不用 D 日 close 假裝成交）。

兩套 evaluation-only 退出規則（皆於觸發日的下一交易日 open 退出）：
  A. candidate_exit    ：第一次不再符合 candidate。
  B. trend_protect_exit：gate 轉 inactive / close < MA60 / 連續 2 日 close < MA20。
overheated 只代表不追高，不會觸發退出；不加任意停損停利。

已知限制（報告需揭露）：Yahoo 非官方資料源、未計股息與滑價、以日線 open 模擬成交、
無 NYSE 完整假日曆（交易日 = 資料中出現的日期）。
"""

from __future__ import annotations

import statistics
from bisect import bisect_right

from app.services.us_analysis_service import (
    _closes,
    _dist_pct,
    _pct_change,
    _rsi,
    _sma,
    classify_status,
)
from app.services.us_strategy_service import classify_trend_follow
from app.services.us_watch_signal_service import _market_context
from app.storage.us_market_store import load_us_leaders, load_us_ohlcv

RULE_CANDIDATE_EXIT = "candidate_exit"
RULE_TREND_PROTECT = "trend_protect_exit"
CONSECUTIVE_BELOW_MA20 = 2      # trend_protect：連續 N 日收盤跌破 MA20
REENTRY_WINDOW_DAYS = 3         # 摘要統計：退出後 N 個交易日內再入選


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rows_asof(rows: list[dict], day: str) -> list[dict]:
    """rows 已依日期排序；回傳 date <= day 的前綴切片（walk-forward 邊界）。"""
    dates = [r["date"] for r in rows]
    return rows[: bisect_right(dates, day)]


def _build_asof_item(code: str, name: str, category: str, rows_asof: list[dict]) -> dict:
    """以 date <= D 的切片計算單檔指標，欄位對齊 get_us_analysis 供 classify 使用。"""
    closes = _closes(rows_asof)
    row_count = len(closes)
    last_close = closes[-1] if closes else None
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    rsi = _rsi(closes)
    dist20 = _dist_pct(last_close, ma20)
    return {
        "code": code, "name": name, "category": category,
        "row_count": row_count,
        "last_data_as_of": rows_asof[-1]["date"] if rows_asof else None,
        "last_close": last_close, "ma20": ma20, "ma60": ma60, "rsi14": rsi,
        "change_20d_pct": _pct_change(closes, 20),
        "dist_ma20_pct": dist20,
        "status": classify_status(row_count, last_close, ma20, ma60, rsi, dist20),
    }


def _next_row_after(rows: list[dict], day: str) -> dict | None:
    dates = [r["date"] for r in rows]
    i = bisect_right(dates, day)
    return rows[i] if i < len(rows) else None


def _mfe_mae(rows: list[dict], start: str, end: str, entry_price: float) -> tuple[float | None, float | None]:
    """entry_date..end（含）期間相對進場價的最大有利 / 不利幅度（%）。"""
    highs = [_num(r.get("high")) for r in rows if start <= r["date"] <= end]
    lows = [_num(r.get("low")) for r in rows if start <= r["date"] <= end]
    highs = [h for h in highs if h is not None]
    lows = [x for x in lows if x is not None]
    if not highs or not lows or not entry_price:
        return None, None
    mfe = round((max(highs) - entry_price) / entry_price * 100, 2)
    mae = round((min(lows) - entry_price) / entry_price * 100, 2)
    return mfe, mae


def run_replay(
    signal_start: str,
    signal_end: str,
    *,
    ohlcv: dict[str, list[dict]] | None = None,
    leaders: list[dict] | None = None,
) -> dict:
    """
    逐日回放：signal_start..signal_end 產生訊號，退出觀察到資料最後一天。
    回傳 {config, snapshots, trades: {rule: [...]}, summary: {rule: {...}}, limitations}。
    相同輸入必產生相同輸出（無隨機性、排序固定）。
    """
    ohlcv = ohlcv if ohlcv is not None else load_us_ohlcv()
    leaders = leaders if leaders is not None else load_us_leaders()

    all_dates = sorted({r["date"] for rows in ohlcv.values() for r in rows})
    eval_dates = [d for d in all_dates if d >= signal_start]
    signal_dates = [d for d in all_dates if signal_start <= d <= signal_end]
    date_index = {d: i for i, d in enumerate(all_dates)}

    # ── 每日 walk-forward 狀態（指標一律由 date<=D 切片重算）────────────────
    day_state: dict[str, dict] = {}
    for d in eval_dates:
        items = {
            it["code"]: _build_asof_item(it["code"], it["name"], it.get("category", ""),
                                         _rows_asof(ohlcv.get(it["code"], []), d))
            for it in leaders
        }
        bias, _ = _market_context(items)
        gate_active = bias in ("bullish", "mixed")
        cls = {code: classify_trend_follow(it, bias) for code, it in items.items()}
        day_state[d] = {"bias": bias, "gate_active": gate_active, "items": items, "cls": cls}

    def is_candidate(d: str, code: str) -> bool:
        s = day_state[d]
        return s["gate_active"] and s["cls"][code]["bucket"] == "candidate"

    # ── 每日快照（訊號區間）＋ churn ────────────────────────────────────────
    snapshots: list[dict] = []
    prev_cands: set[str] | None = None
    for d in signal_dates:
        s = day_state[d]
        cands = sorted(c for c in s["cls"] if s["gate_active"] and s["cls"][c]["bucket"] == "candidate")
        added = sorted(set(cands) - prev_cands) if prev_cands is not None else []
        removed = sorted(prev_cands - set(cands)) if prev_cands is not None else []
        snapshots.append({
            "date": d,
            "market_bias": s["bias"],
            "gate_active": s["gate_active"],
            "candidates": cands,
            "excluded_count": len(s["cls"]) - len(cands),
            "added_vs_prev": added,
            "removed_vs_prev": removed,
            "reasons": {c: {"state": r["state"], "bucket": r["bucket"], "reasons": r["reasons"]}
                        for c, r in sorted(s["cls"].items())},
        })
        prev_cands = set(cands)

    # ── 兩套退出規則各自模擬 ─────────────────────────────────────────────────
    def simulate(rule: str) -> list[dict]:
        trades: list[dict] = []
        holding: dict[str, dict] = {}   # code → open position
        below_ma20: dict[str, int] = {}  # trend_protect：連續跌破 MA20 計數

        for d in eval_dates:
            s = day_state[d]
            # 1) 持有中：檢查退出觸發（以 D 收盤資訊判斷，下一交易日 open 退出）
            for code in list(holding):
                pos = holding[code]
                if d < pos["entry_date"]:
                    continue  # 尚未成交
                it = s["items"][code]
                reason = None
                if rule == RULE_CANDIDATE_EXIT:
                    if not is_candidate(d, code):
                        reason = "not_candidate"
                else:
                    close, ma20, ma60 = it["last_close"], it["ma20"], it["ma60"]
                    if not s["gate_active"]:
                        reason = "gate_inactive"
                    elif close is not None and ma60 is not None and close < ma60:
                        reason = "close_below_ma60"
                    else:
                        if close is not None and ma20 is not None and close < ma20:
                            below_ma20[code] = below_ma20.get(code, 0) + 1
                        else:
                            below_ma20[code] = 0
                        if below_ma20.get(code, 0) >= CONSECUTIVE_BELOW_MA20:
                            reason = f"close_below_ma20_{CONSECUTIVE_BELOW_MA20}d"
                if reason is None:
                    continue
                rows = ohlcv.get(code, [])
                nxt = _next_row_after(rows, d)
                exit_price = _num(nxt.get("open")) if nxt else None
                if nxt is not None and exit_price is not None:
                    entry_price = pos["entry_price"]
                    mfe, mae = _mfe_mae(rows, pos["entry_date"], nxt["date"], entry_price)
                    trades.append({**pos, "exit_date": nxt["date"], "exit_price": exit_price,
                                   "exit_rule": rule, "exit_reason": reason,
                                   "holding_trading_days": date_index[nxt["date"]] - date_index[pos["entry_date"]],
                                   "return_pct": round((exit_price - entry_price) / entry_price * 100, 2),
                                   "mfe_pct": mfe, "mae_pct": mae, "unresolved": False})
                else:
                    # 觸發了但沒有下一交易日 open：不得用當日 close 假裝成交
                    mfe, mae = _mfe_mae(rows, pos["entry_date"], all_dates[-1], pos["entry_price"])
                    trades.append({**pos, "exit_date": None, "exit_price": None,
                                   "exit_rule": rule, "exit_reason": f"{reason}_no_next_open",
                                   "holding_trading_days": None, "return_pct": None,
                                   "mfe_pct": mfe, "mae_pct": mae, "unresolved": True})
                del holding[code]
                below_ma20.pop(code, None)

            # 2) 訊號：只在訊號區間、gate 啟用、當日 candidate、未持有
            if d in set(signal_dates):
                for code in sorted(s["cls"]):
                    if code in holding or not is_candidate(d, code):
                        continue
                    rows = ohlcv.get(code, [])
                    nxt = _next_row_after(rows, d)
                    entry_price = _num(nxt.get("open")) if nxt else None
                    base = {
                        "code": code, "category": s["items"][code]["category"],
                        "signal_date": d,
                        "market_bias_at_entry": s["bias"],
                        "entry_reasons": list(s["cls"][code]["reasons"]),
                    }
                    if nxt is None or entry_price is None:
                        trades.append({**base, "entry_date": None, "entry_price": None,
                                       "exit_date": None, "exit_price": None, "exit_rule": rule,
                                       "exit_reason": "no_next_open_for_entry",
                                       "holding_trading_days": None, "return_pct": None,
                                       "mfe_pct": None, "mae_pct": None, "unresolved": True})
                        continue
                    holding[code] = {**base, "entry_date": nxt["date"], "entry_price": entry_price}
                    below_ma20[code] = 0

        # 3) 資料结束仍持有 → unresolved（誠實揭露，不以最後 close 結算）
        for code, pos in sorted(holding.items()):
            rows = ohlcv.get(code, [])
            mfe, mae = _mfe_mae(rows, pos["entry_date"], all_dates[-1], pos["entry_price"])
            trades.append({**pos, "exit_date": None, "exit_price": None, "exit_rule": rule,
                           "exit_reason": "open_at_data_end", "holding_trading_days": None,
                           "return_pct": None, "mfe_pct": mfe, "mae_pct": mae, "unresolved": True})

        trades.sort(key=lambda t: (t["signal_date"], t["code"]))
        return trades

    trades_by_rule = {RULE_CANDIDATE_EXIT: simulate(RULE_CANDIDATE_EXIT),
                      RULE_TREND_PROTECT: simulate(RULE_TREND_PROTECT)}

    # ── 摘要 ─────────────────────────────────────────────────────────────────
    def summarize(trades: list[dict]) -> dict:
        done = [t for t in trades if not t["unresolved"]]
        rets = [t["return_pct"] for t in done]
        reentry = 0
        by_code: dict[str, list[dict]] = {}
        for t in trades:
            by_code.setdefault(t["code"], []).append(t)
        for seq in by_code.values():
            for prev, nxt in zip(seq, seq[1:]):
                if prev.get("exit_date") and nxt["signal_date"] in date_index:
                    if date_index[nxt["signal_date"]] - date_index[prev["exit_date"]] <= REENTRY_WINDOW_DAYS:
                        reentry += 1
        reasons: dict[str, int] = {}
        for t in trades:
            reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
        return {
            "signals": len(trades),
            "completed_trades": len(done),
            "unresolved_trades": len(trades) - len(done),
            "win_rate_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1) if rets else None,
            "avg_return_pct": round(statistics.mean(rets), 2) if rets else None,
            "median_return_pct": round(statistics.median(rets), 2) if rets else None,
            "best_trade_pct": max(rets) if rets else None,
            "worst_trade_pct": min(rets) if rets else None,
            "avg_holding_trading_days": round(statistics.mean(
                [t["holding_trading_days"] for t in done]), 1) if done else None,
            "avg_mfe_pct": round(statistics.mean(
                [t["mfe_pct"] for t in done if t["mfe_pct"] is not None]), 2) if done else None,
            "avg_mae_pct": round(statistics.mean(
                [t["mae_pct"] for t in done if t["mae_pct"] is not None]), 2) if done else None,
            "reentry_within_3d": reentry,
            "exit_reason_counts": dict(sorted(reasons.items())),
        }

    churn = {
        "daily_added": sum(len(s["added_vs_prev"]) for s in snapshots),
        "daily_removed": sum(len(s["removed_vs_prev"]) for s in snapshots),
        "days_with_change": sum(1 for s in snapshots if s["added_vs_prev"] or s["removed_vs_prev"]),
        "snapshot_days": len(snapshots),
    }

    return {
        "config": {
            "strategy": "us_trend_follow",
            "signal_window": [signal_start, signal_end],
            "data_last_date": all_dates[-1] if all_dates else None,
            "tickers": len(leaders),
            "entry": "signal 於 D 收盤成立，成交用 D+1 交易日 open；無則 unresolved",
            "exit_rules": [RULE_CANDIDATE_EXIT, RULE_TREND_PROTECT],
            "note": "evaluation-only：非推薦、非買賣建議、不下單、不改 production 規則、不做參數最佳化",
        },
        "snapshots": snapshots,
        "candidate_churn": churn,
        "trades": trades_by_rule,
        "summary": {rule: summarize(ts) for rule, ts in trades_by_rule.items()},
        "limitations": [
            "Yahoo Finance 非官方資料源（best-effort），價格未經第二來源核對",
            "未計股息、滑價、手續費；以日線 open 模擬成交（實際開盤價可能跳空偏離）",
            "交易日曆 = 資料中出現的日期（無 NYSE 完整假日曆）",
            "訊號窗僅 11 個交易日、樣本極小，統計數字只能看方向不能下結論",
            "walk-forward 僅保證不用未來價格；策略規則本身是用近期行情設計的（規則層後見之明無法排除）",
        ],
    }
