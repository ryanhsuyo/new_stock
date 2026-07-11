"""
us_breakout_replay_service.py — 老王美股版突破策略回放（evaluation-only）。

**評估工具，非交易系統、非推薦、非買賣建議、不下單、不套台股 old_wang 程式。**
規則骨架借台股老王「有拼有止損」精神，全部用 OHLCV 可算欄位落地：

  進場（D 收盤訊號，全部成立）：
    - 大盤軟濾網：SPY 或 QQQ 收盤在其 MA60 上方（as-of D，walk-forward）
    - 收盤創 20 日新高（> 前 20 日收盤最大值）
    - 量能確認：成交量 >= 1.5 × 前 20 日均量
    - 結構：收盤 > MA20
  成交：D+1 交易日 open；無下一 open → unresolved。
  出場（先檢查止損，觸發後 D+1 open 出）：
    - 硬止損：收盤 < 進場價 × 0.92（-8%）
    - 波段線：連續 2 個交易日收盤 < MA10（讓利潤跑，跌破波段線才走）

**參數凍結聲明**：STOP_PCT / VOL_X / LOOKBACK / MA10_DAYS 於 2026-07-11 依老王精神
一次寫死並在一年資料上首測；本模組不得調參後重測（避免過擬合）。加長資料重跑
屬於樣本外驗證；改參數屬於重新設計，需明確記錄為新策略。

Walk-forward 保證：所有窗口（20 日高、均量、MA10/MA20/MA60）只用 index <= i 的
資料；有測試證明竄改未來 bar 不影響 as-of 訊號。

已知限制：Yahoo 非官方資料源、未計股息 / 滑價 / 稅費、逐筆等權加總非投組報酬、
交易日曆 = 資料出現日期、規則設計時看過 2025-10 之後的行情（該段非嚴格樣本外）。
"""

from __future__ import annotations

import statistics

from app.storage.us_market_store import load_us_leaders, load_us_ohlcv

STRATEGY = "us_wang_breakout"
STRATEGY_LABEL = "老王美股版：突破 + 量能進場、MA10 波段、-8% 硬止損（evaluation-only）"

# ── 凍結參數（2026-07-11 定案，不得調參重測）─────────────────────────────────
STOP_PCT = 0.92            # 硬止損：收盤 < 進場價 × 0.92
VOL_X = 1.5                # 量能確認倍數（vs 前 20 日均量）
LOOKBACK_HIGH = 20         # 收盤創 N 日新高
MA10_EXIT_DAYS = 2         # 連續 N 日收盤跌破 MA10 出場
MARKET_MA = 60             # 大盤軟濾網均線
ETF_CATEGORY = "ETF / Benchmark"
BENCHMARKS = ("SPY", "QQQ")


def _series(rows: list[dict]) -> dict:
    def col(key):
        out = []
        for r in rows:
            try:
                out.append(float(r[key]))
            except (TypeError, ValueError, KeyError):
                out.append(None)
        return out
    return {"date": [r["date"] for r in rows], "open": col("open"), "high": col("high"),
            "low": col("low"), "close": col("close"), "volume": col("volume")}


def _market_filter_map(ohlcv: dict[str, list[dict]]) -> dict[str, bool]:
    """每個交易日：SPY 或 QQQ 收盤在 MA60 上方（walk-forward）。基準資料不足 → False（不交易）。"""
    flags: dict[str, list[bool]] = {}
    for code in BENCHMARKS:
        s = _series(ohlcv.get(code, []))
        c = s["close"]
        for i in range(len(c)):
            if i < MARKET_MA - 1 or c[i] is None:
                ok = False
            else:
                window = c[i - MARKET_MA + 1:i + 1]
                ok = all(x is not None for x in window) and c[i] > sum(window) / MARKET_MA
            flags.setdefault(s["date"][i], []).append(ok)
    return {day: any(v) for day, v in flags.items()}


def entry_signal(s: dict, i: int) -> bool:
    """純函式：第 i 根收盤是否成立進場訊號（只讀 index <= i，walk-forward）。"""
    c, v = s["close"], s["volume"]
    if i < LOOKBACK_HIGH + 1 or c[i] is None or v[i] is None:
        return False
    prior_closes = c[i - LOOKBACK_HIGH:i]
    prior_vols = v[i - LOOKBACK_HIGH:i]
    if any(x is None for x in prior_closes) or any(x is None for x in prior_vols):
        return False
    if not c[i] > max(prior_closes):                     # 創 20 日收盤新高
        return False
    if not v[i] >= VOL_X * (sum(prior_vols) / LOOKBACK_HIGH):  # 量能確認
        return False
    ma20 = sum(c[i - 19:i + 1]) / 20                     # 結構：站上 MA20
    return c[i] > ma20


def run_breakout_replay(
    signal_start: str,
    signal_end: str | None = None,
    *,
    ohlcv: dict[str, list[dict]] | None = None,
    leaders: list[dict] | None = None,
) -> dict:
    """
    逐日回放：signal_start..signal_end（含）產生訊號，出場觀察到資料最後一天。
    相同輸入必產生相同輸出。回傳 {config, trades, summary, yearly, market_filter, limitations}。
    """
    ohlcv = ohlcv if ohlcv is not None else load_us_ohlcv()
    leaders = leaders if leaders is not None else load_us_leaders()
    stocks = [it for it in leaders if it.get("category") != ETF_CATEGORY and it["code"] in ohlcv]
    mkt = _market_filter_map(ohlcv)
    all_dates = sorted({r["date"] for rows in ohlcv.values() for r in rows})
    end = signal_end or (all_dates[-1] if all_dates else signal_start)

    trades: list[dict] = []
    blocked_by_market = 0

    for it in stocks:
        code = it["code"]
        s = _series(ohlcv[code])
        d, o, h, l, c = s["date"], s["open"], s["high"], s["low"], s["close"]
        n = len(d)
        holding: dict | None = None
        below = 0

        for i in range(n):
            if holding is not None:
                if c[i] is None:
                    continue
                ma10 = None
                if i >= 9 and all(x is not None for x in c[i - 9:i + 1]):
                    ma10 = sum(c[i - 9:i + 1]) / 10
                reason = None
                if c[i] < holding["entry_price"] * STOP_PCT:
                    reason = "stop_loss"
                elif ma10 is not None:
                    below = below + 1 if c[i] < ma10 else 0
                    if below >= MA10_EXIT_DAYS:
                        reason = "ma10_break"
                if reason is None:
                    continue
                if i + 1 < n and o[i + 1] is not None:
                    ep = holding["entry_price"]
                    exit_price = o[i + 1]
                    seg_h = [x for x in h[holding["entry_i"]:i + 2] if x is not None]
                    seg_l = [x for x in l[holding["entry_i"]:i + 2] if x is not None]
                    trades.append({**holding_public(holding, code, it),
                                   "exit_date": d[i + 1], "exit_price": exit_price,
                                   "exit_reason": reason,
                                   "holding_trading_days": i + 1 - holding["entry_i"],
                                   "return_pct": round((exit_price - ep) / ep * 100, 2),
                                   "mfe_pct": round((max(seg_h) - ep) / ep * 100, 2) if seg_h else None,
                                   "mae_pct": round((min(seg_l) - ep) / ep * 100, 2) if seg_l else None,
                                   "unresolved": False})
                else:
                    trades.append({**holding_public(holding, code, it),
                                   "exit_date": None, "exit_price": None,
                                   "exit_reason": f"{reason}_no_next_open",
                                   "holding_trading_days": None, "return_pct": None,
                                   "mfe_pct": None, "mae_pct": None, "unresolved": True})
                holding = None
                below = 0
                continue

            # 未持有：找訊號（只在訊號區間）
            if not (signal_start <= d[i] <= end):
                continue
            if not entry_signal(s, i):
                continue
            if not mkt.get(d[i], False):
                blocked_by_market += 1
                continue
            if i + 1 >= n or o[i + 1] is None:
                trades.append({"code": code, "category": it.get("category", ""),
                               "signal_date": d[i], "entry_date": None, "entry_price": None,
                               "exit_date": None, "exit_price": None,
                               "exit_reason": "no_next_open_for_entry",
                               "holding_trading_days": None, "return_pct": None,
                               "mfe_pct": None, "mae_pct": None, "unresolved": True})
                continue
            holding = {"signal_date": d[i], "entry_i": i + 1, "entry_date": d[i + 1],
                       "entry_price": o[i + 1]}
            below = 0

        if holding is not None:
            ep = holding["entry_price"]
            seg_h = [x for x in h[holding["entry_i"]:] if x is not None]
            seg_l = [x for x in l[holding["entry_i"]:] if x is not None]
            trades.append({**holding_public(holding, code, stocks_by_code(stocks)[code]),
                           "exit_date": None, "exit_price": None,
                           "exit_reason": "open_at_data_end", "holding_trading_days": None,
                           "return_pct": None,
                           "mfe_pct": round((max(seg_h) - ep) / ep * 100, 2) if seg_h else None,
                           "mae_pct": round((min(seg_l) - ep) / ep * 100, 2) if seg_l else None,
                           "unresolved": True})

    trades.sort(key=lambda t: (t["signal_date"], t["code"]))

    done = [t for t in trades if not t["unresolved"]]
    yearly: dict[str, dict] = {}
    for t in done:
        yearly.setdefault(t["signal_date"][:4], []).append(t["return_pct"])

    return {
        "config": {
            "strategy": STRATEGY, "strategy_label": STRATEGY_LABEL,
            "signal_window": [signal_start, end],
            "data_last_date": all_dates[-1] if all_dates else None,
            "params_frozen": {"stop_pct": STOP_PCT, "vol_x": VOL_X,
                              "lookback_high": LOOKBACK_HIGH, "ma10_exit_days": MA10_EXIT_DAYS,
                              "market_ma": MARKET_MA, "frozen_at": "2026-07-11"},
            "note": "evaluation-only：非推薦、非買賣建議、不下單、不調參",
        },
        "trades": trades,
        "summary": _summarize(trades),
        "yearly": {y: _stats(rs) for y, rs in sorted(yearly.items())},
        "market_filter": {"blocked_signals": blocked_by_market},
        "limitations": [
            "Yahoo Finance 非官方資料源；收盤為分割調整、未含股息",
            "未計滑價 / 手續費 / 稅費；D+1 open 成交，跳空日偏差可能大",
            "逐筆等權加總非投組報酬；無資金配置與同時持倉上限模擬",
            "規則設計時看過 2025-10 之後行情，該段非嚴格樣本外；更早年份為樣本外",
            "部分 ticker（ARM/SNOW/PLTR 等）上市較晚，早年無資料屬正常",
        ],
    }


def holding_public(holding: dict, code: str, it: dict) -> dict:
    return {"code": code, "category": it.get("category", ""),
            "signal_date": holding["signal_date"], "entry_date": holding["entry_date"],
            "entry_price": holding["entry_price"]}


def stocks_by_code(stocks: list[dict]) -> dict[str, dict]:
    return {it["code"]: it for it in stocks}


def _stats(rets: list[float]) -> dict:
    if not rets:
        return {"n": 0}
    srt = sorted(rets)
    return {"n": len(rets),
            "win_rate_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
            "avg_pct": round(statistics.mean(rets), 2),
            "median_pct": round(statistics.median(rets), 2),
            "sum_pct": round(sum(rets), 2),
            "best_pct": srt[-1], "worst_pct": srt[0]}


def _summarize(trades: list[dict]) -> dict:
    done = [t for t in trades if not t["unresolved"]]
    rets = sorted(t["return_pct"] for t in done)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
    out = {"signals": len(trades), "completed_trades": len(done),
           "unresolved_trades": len(trades) - len(done),
           **(_stats(rets) if rets else {"n": 0}),
           "avg_holding_trading_days": round(statistics.mean(
               [t["holding_trading_days"] for t in done]), 1) if done else None,
           "exit_reason_counts": dict(sorted(reasons.items()))}
    if rets:
        total = sum(rets)
        out["tail_top1_share_pct"] = round(rets[-1] / total * 100, 1) if total else None
        out["tail_top5_sum_pct"] = round(sum(rets[-5:]), 2)
        out["sum_without_top5_pct"] = round(total - sum(rets[-5:]), 2)
        # 逐筆等權累計和的最大回落（非投組報酬，僅供韌性參考）
        cum = peak = 0.0
        mdd = 0.0
        for t in done:  # 已依 signal_date 排序
            cum += t["return_pct"]
            peak = max(peak, cum)
            mdd = min(mdd, cum - peak)
        out["cumsum_max_drawdown_pct_points"] = round(mdd, 2)
    return out
