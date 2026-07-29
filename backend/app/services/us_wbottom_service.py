"""
us_wbottom_service.py — 美股第二套觀察策略：W 底突破 + 量幅目標（us_wbottom_target）。

**非推薦、非買賣建議、非下單。** 頸線 / 型態低點 / 量幅目標 / 失效價全部是
**觀察用關鍵價位**，不是進出場指令。**不套台股 old_wang / steady_momentum。**

規則（教科書 W 底；參數凍結於 2026-07-12 的 5 年回放評估，不得調參）：
  - swing low：±3 日局部最低，**需 3 個交易日後才確認**（無未來洩漏）
  - 兩低點相距 10–40 交易日、價差 ≤ 3%
  - 頸線 = 兩低點之間的最高 high
  - 突破：收盤首次站上頸線（前一日仍在頸線下），且距第二低點 ≤ 20 個交易日
  - 大盤軟濾網：SPY 或 QQQ 收盤 > 其 MA60
  - 量幅目標 = 頸線 + (頸線 − 型態低點)；失效 = 收盤跌破型態低點

5 年回放成績（2021-09～2026-07，含 2022 空頭；見 docs/ai/us-wbottom-replay-5y.md）：
勝率 62.4%（全部測試最高）、成本後 +1.35%/筆；**已知弱點**：2022 空頭年平均
−5.87%/筆（濾網擋不住假底）、贏家被目標封頂（最大 +29%）、生存者折扣後 +0.48%/筆。
**高勝率 ≠ 高獲利**——採用它買的是「常常對」的紀律結構，不是超額報酬。

本模組同時包含 production 觀察輸出與 evaluation 回放（單一規則來源，兩者共用
find_w_breakout；別把規則複製到第三處）。
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from app.storage.us_market_store import load_us_leaders, load_us_ohlcv

STRATEGY = "us_wbottom_target"
STRATEGY_LABEL = "W 底突破 + 量幅目標（觀察用，勝率型）"

# ── 凍結參數（2026-07-12 定案，不得調參重測）─────────────────────────────────
SWING_WINDOW = 3            # ±3 日局部最低；低點需 3 日後才確認
LOW_GAP_MIN = 10            # 兩低點最小間隔（交易日）
LOW_GAP_MAX = 40            # 兩低點最大間隔
LOW_DIFF_MAX_PCT = 3.0      # 兩低點價差上限（%）
BREAKOUT_MAX_AFTER_LOW = 20 # 突破需在第二低點後 N 個交易日內
PATTERN_LOOKBACK = 60       # 低點回看範圍
TRACK_BARS = 20             # 觀察輸出：追蹤最近 N 根內的突破事件
MARKET_MA = 60              # 大盤軟濾網均線
ETF_CATEGORY = "ETF / Benchmark"
BENCHMARKS = ("SPY", "QQQ")

STATE_LABELS = {
    "breakout_today":       "今日突破頸線",
    "breakout_in_progress": "突破後觀察中",
    "target_reached":       "已達量幅目標",
    "invalidated":          "型態失效",
    "forming":              "型態形成中（未突破）",
}
# 觀察排序：越前面越值得先看
_STATE_ORDER = {"breakout_today": 0, "breakout_in_progress": 1, "forming": 2,
                "target_reached": 3, "invalidated": 4}

_FIXED_RISK_NOTES = [
    "關鍵價位為觀察參考，非下單指令",
    "回放顯示 2022 型空頭年此型態平均為負（假底），大盤軟濾網無法完全保護",
    "量幅目標會封頂贏家：高勝率的代價是贏小賠大的偏態",
]


def _series(rows: list[dict]) -> dict:
    def col(k):
        out = []
        for r in rows:
            try:
                out.append(float(r[k]))
            except (TypeError, ValueError, KeyError):
                out.append(None)
        return out
    return {"date": [r["date"] for r in rows], "open": col("open"), "high": col("high"),
            "low": col("low"), "close": col("close")}


def _swing_lows(low: list, upto: int) -> list[int]:
    """±SWING_WINDOW 日局部最低，且已確認（低點 index <= upto - SWING_WINDOW）。"""
    out = []
    for j in range(SWING_WINDOW, upto - SWING_WINDOW + 1):
        window = low[j - SWING_WINDOW:j + SWING_WINDOW + 1]
        if any(x is None for x in window):
            continue
        if low[j] == min(window):
            out.append(j)
    return out


def _match_pattern(s: dict, i: int, *, require_breakout: bool) -> dict | None:
    """
    在第 i 根收盤偵測 W 底（只讀 index <= i，walk-forward）。
    require_breakout=True：收盤首次突破頸線（前一日仍在頸線下）。
    require_breakout=False：型態成立但尚未突破（收盤 ≤ 頸線且未跌破型態低）。
    """
    l, h, c = s["low"], s["high"], s["close"]
    if i < LOW_GAP_MIN + 2 * SWING_WINDOW or c[i] is None or (i >= 1 and c[i - 1] is None):
        return None
    lows = [j for j in _swing_lows(l, i) if i - j <= PATTERN_LOOKBACK]
    for k in range(len(lows) - 1, 0, -1):
        j2 = lows[k]
        if i - j2 > BREAKOUT_MAX_AFTER_LOW:
            break
        for j1 in reversed(lows[:k]):
            gap = j2 - j1
            if gap < LOW_GAP_MIN:
                continue
            if gap > LOW_GAP_MAX:
                break
            lo1, lo2 = l[j1], l[j2]
            if abs(lo2 - lo1) / lo1 * 100 > LOW_DIFF_MAX_PCT:
                continue
            neck_window = h[j1:j2 + 1]
            if any(x is None for x in neck_window):
                continue
            neck = max(neck_window)
            plow = min(lo1, lo2)
            hit = (c[i] > neck and c[i - 1] <= neck) if require_breakout \
                else (c[i] <= neck and c[i] >= plow)
            if hit:
                return {"neckline": round(neck, 2), "pattern_low": round(plow, 2),
                        "target": round(neck + (neck - plow), 2),
                        "j1": j1, "j2": j2,
                        "low1_date": s["date"][j1], "low2_date": s["date"][j2]}
    return None


def find_w_breakout(s: dict, i: int) -> dict | None:
    """第 i 根收盤是否為「剛突破頸線的 W 底」。production 與 replay 共用。"""
    return _match_pattern(s, i, require_breakout=True)


def _soft_gate(ohlcv: dict[str, list[dict]]) -> dict:
    """大盤軟濾網現況：SPY 或 QQQ 收盤 > MA60（各用自己序列的最後一根）。"""
    detail = {}
    for b in BENCHMARKS:
        s = _series(ohlcv.get(b, []))
        c = [x for x in s["close"] if x is not None]
        above = len(c) >= MARKET_MA and c[-1] > sum(c[-MARKET_MA:]) / MARKET_MA
        detail[b] = above
    active = any(detail.values())
    return {
        "active": active,
        "detail": detail,
        "note": ("SPY 或 QQQ 在 MA60 上方，型態觀察啟用" if active
                 else "SPY 與 QQQ 皆低於 MA60（或資料不足）——回放中此狀態的突破不計入，僅列型態供參考"),
    }


def get_us_wbottom(as_of: str | None = None) -> dict:
    """
    W 底型態觀察總表（唯讀、描述性）。每檔非 ETF 股票掃描最近 TRACK_BARS 根內的
    突破事件並分類；無突破則看是否有「形成中」型態。無型態者只計數不逐檔列出
    （多數股票多數時間沒有 W 底，缺席是常態不是錯誤）。
    """
    ohlcv = load_us_ohlcv()
    if as_of:
        ohlcv = {
            code: [row for row in rows if row["date"] <= as_of]
            for code, rows in ohlcv.items()
        }
    leaders = load_us_leaders()
    stocks = [it for it in leaders if it.get("category") != ETF_CATEGORY]
    gate = _soft_gate(ohlcv)

    patterns: list[dict] = []
    no_pattern = 0
    dates_all: list[str] = []
    for it in stocks:
        rows = ohlcv.get(it["code"], [])
        s = _series(rows)
        n = len(s["date"])
        if n:
            dates_all.append(s["date"][-1])
        if n < LOW_GAP_MIN + 2 * SWING_WINDOW + 2:
            no_pattern += 1
            continue

        # 1) 最近 TRACK_BARS 根內最新的突破事件
        event = None
        for i in range(n - 1, max(n - 1 - TRACK_BARS, LOW_GAP_MIN), -1):
            w = find_w_breakout(s, i)
            if w:
                event = (i, w)
                break

        item = None
        if event:
            i, w = event
            closes_after = [c for c in s["close"][i:] if c is not None]
            last_close = closes_after[-1]
            if any(c >= w["target"] for c in closes_after):
                state = "target_reached"
            elif any(c < w["pattern_low"] for c in closes_after):
                state = "invalidated"
            elif i == n - 1:
                state = "breakout_today"
            else:
                state = "breakout_in_progress"
            reasons = [
                f"{s['date'][i]} 收盤 {s['close'][i]:.2f} 突破頸線 {w['neckline']}"
                f"（雙低 {w['low1_date']} / {w['low2_date']}，型態低 {w['pattern_low']}）",
                f"量幅目標 {w['target']}；失效價 = 型態低 {w['pattern_low']}",
            ]
            if not gate["active"]:
                reasons.append("大盤軟濾網目前關閉：回放評估中此狀態的突破不計入")
            item = {"state": state, "breakout_date": s["date"][i], "last_close": last_close, **w}
        else:
            # 2) 形成中（未突破）
            w = _match_pattern(s, n - 1, require_breakout=False)
            if w:
                last_close = s["close"][n - 1]
                reasons = [
                    f"雙低 {w['low1_date']} / {w['low2_date']}（型態低 {w['pattern_low']}），"
                    f"頸線 {w['neckline']} 尚未突破",
                    f"觀察條件：收盤站上頸線 {w['neckline']}；跌破 {w['pattern_low']} 型態失效",
                ]
                item = {"state": "forming", "breakout_date": None, "last_close": last_close, **w}

        if item is None:
            no_pattern += 1
            continue
        target, close = item["target"], item["last_close"]
        patterns.append({
            "code": it["code"], "name": it["name"], "category": it.get("category", ""),
            "state": item["state"], "state_label": STATE_LABELS[item["state"]],
            "close": close,
            "neckline": item["neckline"], "pattern_low": item["pattern_low"],
            "target_price": target,
            "dist_to_target_pct": round((target - close) / close * 100, 2) if close else None,
            "breakout_date": item["breakout_date"],
            "low_dates": [item["low1_date"], item["low2_date"]],
            "reasons": reasons,
            "risk_notes": list(_FIXED_RISK_NOTES),
        })

    patterns.sort(key=lambda p: (_STATE_ORDER[p["state"]], p["code"]))
    return {
        "as_of": max(dates_all) if dates_all else None,
        "strategy": STRATEGY,
        "strategy_label": STRATEGY_LABEL,
        "market_gate": gate,
        "patterns": patterns,
        "no_pattern_count": no_pattern,
        "note": "觀察用型態掃描：非推薦、非買賣建議、非下單；多數股票多數時間沒有 W 底，空清單是常態。",
    }


# ── evaluation：5 年回放（V1 出場：量幅目標 / 型態低停損）────────────────────

def _market_filter_map(ohlcv: dict[str, list[dict]]) -> dict[str, bool]:
    flags: dict[str, list[bool]] = defaultdict(list)
    for b in BENCHMARKS:
        s = _series(ohlcv.get(b, []))
        c = s["close"]
        for i in range(len(c)):
            ok = (i >= MARKET_MA - 1 and c[i] is not None
                  and all(x is not None for x in c[i - MARKET_MA + 1:i + 1])
                  and c[i] > sum(c[i - MARKET_MA + 1:i + 1]) / MARKET_MA)
            flags[s["date"][i]].append(ok)
    return {d: any(v) for d, v in flags.items()}


def run_wbottom_replay(signal_start: str, signal_end: str | None = None, *,
                       ohlcv: dict[str, list[dict]] | None = None,
                       leaders: list[dict] | None = None) -> dict:
    """
    W 底 V1 回放：突破訊號（D 收盤）→ D+1 open 進場；收盤到量幅目標或跌破型態低
    → 下一交易日 open 出。同檔持有期間不重複進場。相同輸入必產生相同輸出。
    """
    ohlcv = ohlcv if ohlcv is not None else load_us_ohlcv()
    leaders = leaders if leaders is not None else load_us_leaders()
    stocks = [it for it in leaders if it.get("category") != ETF_CATEGORY and it["code"] in ohlcv]
    mkt = _market_filter_map(ohlcv)
    all_dates = sorted({r["date"] for rows in ohlcv.values() for r in rows})
    end = signal_end or (all_dates[-1] if all_dates else signal_start)

    trades: list[dict] = []
    for it in stocks:
        s = _series(ohlcv[it["code"]])
        d, o, c = s["date"], s["open"], s["close"]
        n = len(d)
        held_until = 0
        for i in range(LOW_GAP_MIN + 2 * SWING_WINDOW, n):
            if i < held_until or not (signal_start <= d[i] <= end):
                continue
            if not mkt.get(d[i], False):
                continue
            w = find_w_breakout(s, i)
            if not w:
                continue
            if i + 1 >= n or o[i + 1] is None:
                trades.append({"code": it["code"], "category": it.get("category", ""),
                               "signal_date": d[i], "entry_date": None, "entry_price": None,
                               "exit_date": None, "exit_price": None,
                               "exit_reason": "no_next_open_for_entry",
                               "holding_trading_days": None, "return_pct": None,
                               "target_price": w["target"], "pattern_low": w["pattern_low"],
                               "unresolved": True})
                held_until = n
                continue
            entry_i, entry = i + 1, o[i + 1]
            exit_i, reason = None, None
            for j in range(entry_i, n):
                if c[j] is None:
                    continue
                if c[j] >= w["target"]:
                    exit_i, reason = j, "target"
                elif c[j] < w["pattern_low"]:
                    exit_i, reason = j, "pattern_low_stop"
                if exit_i is not None:
                    break
            base = {"code": it["code"], "category": it.get("category", ""),
                    "signal_date": d[i], "entry_date": d[entry_i], "entry_price": entry,
                    "target_price": w["target"], "pattern_low": w["pattern_low"]}
            if exit_i is None or exit_i + 1 >= n or o[exit_i + 1] is None:
                trades.append({**base, "exit_date": None, "exit_price": None,
                               "exit_reason": "open_at_data_end" if exit_i is None
                               else f"{reason}_no_next_open",
                               "holding_trading_days": None, "return_pct": None,
                               "unresolved": True})
                held_until = n
                continue
            xp = o[exit_i + 1]
            trades.append({**base, "exit_date": d[exit_i + 1], "exit_price": xp,
                           "exit_reason": reason,
                           "holding_trading_days": exit_i + 1 - entry_i,
                           "return_pct": round((xp - entry) / entry * 100, 2),
                           "unresolved": False})
            held_until = exit_i + 1

    trades.sort(key=lambda t: (t["signal_date"], t["code"]))
    done = [t for t in trades if not t["unresolved"]]
    rets = sorted(t["return_pct"] for t in done)
    yearly: dict[str, list[float]] = defaultdict(list)
    for t in done:
        yearly[t["signal_date"][:4]].append(t["return_pct"])

    def _stats(rs: list[float]) -> dict:
        if not rs:
            return {"n": 0}
        return {"n": len(rs),
                "win_rate_pct": round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1),
                "avg_pct": round(statistics.mean(rs), 2),
                "median_pct": round(statistics.median(rs), 2),
                "sum_pct": round(sum(rs), 2),
                "best_pct": max(rs), "worst_pct": min(rs)}

    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
    return {
        "config": {"strategy": STRATEGY, "strategy_label": STRATEGY_LABEL,
                   "signal_window": [signal_start, end],
                   "data_last_date": all_dates[-1] if all_dates else None,
                   "params_frozen": {"swing": SWING_WINDOW, "low_gap": [LOW_GAP_MIN, LOW_GAP_MAX],
                                     "low_diff_max_pct": LOW_DIFF_MAX_PCT,
                                     "breakout_max_after_low": BREAKOUT_MAX_AFTER_LOW,
                                     "market_ma": MARKET_MA, "frozen_at": "2026-07-12"},
                   "note": "evaluation-only：非推薦、非買賣建議、不下單、不調參"},
        "trades": trades,
        "summary": {**_stats(rets), "signals": len(trades),
                    "completed_trades": len(done),
                    "unresolved_trades": len(trades) - len(done),
                    "avg_holding_trading_days": round(statistics.mean(
                        [t["holding_trading_days"] for t in done]), 1) if done else None,
                    "exit_reason_counts": dict(sorted(reasons.items()))},
        "yearly": {y: _stats(rs) for y, rs in sorted(yearly.items())},
        "limitations": [
            "Yahoo Finance 非官方資料源；分割調整、未含股息",
            "未計滑價 / 手續費 / 稅費；D+1 open 成交",
            "逐筆等權加總非投組報酬；universe 為 2026 年所選（生存者偏差）",
            "高勝率來自目標封頂贏家：偏態為贏小賠大；2022 型空頭年平均為負",
        ],
    }
