#!/usr/bin/env python3
"""
replay_tw_old_wang.py — 台股 old_wang 推薦桶 walk-forward 回放（evaluation-only）。

用法：
    cd backend
    python3.11 scripts/replay_tw_old_wang.py                        # 預設 2025-05-02..2026-06-30
    python3.11 scripts/replay_tw_old_wang.py --start 2025-05-02 --end 2026-06-30

方法：
    - 候選判定 = **production 訊號管線本身**（`signals_service._run_signal_batch`，
      `_load_ohlcv(as_of)` 逐日截斷資料重算，零複製規則）。以同步 pool 取代
      multiprocessing（評估用，放棄逾時保護換速度）。
    - 進場：D 日在 old_wang 桶（`old_wang_flag` 且 data_ok）→ D+1 open。
    - 兩套 evaluation-only 退出（觸發後下一交易日 open 出）：
        A bucket_exit：第一次掉出桶。
        B wang_protect：收盤 < 進場價 −8%，或連續 2 日收盤 < MA10。
    - 已知資料限制：TWSE 原始價**不還原企業行動**。預設排除污染 codes
      （0050/0052 分割、2603/6269 大額除息 >10% 假跳動）；其餘個股的除息缺口
      （<10%）會**低估**報酬（股息未入帳），屬保守偏誤。
    - 對照：0050 buy&hold（2025-06-18 1:4 分割已修正）。

**非推薦、非買賣建議、不下單、不改 production 規則、不做參數最佳化。**
結論見 docs/ai/strategy-evaluation-ledger.md 與 docs/ai/handoff-log.md（2026-07-12）。
"""

import argparse
import csv as csv_mod
import json
import statistics
import sys
from bisect import bisect_right
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services import signals_service as ss  # noqa: E402

OUT_DIR = _BACKEND / "out"
# 企業行動污染（單日 |漲跌| > 10% 的假跳動來源），評估時排除
EXCLUDED_CODES = ("0050", "0052", "2603", "6269")
ROUND_TRIP_COST_PCT = 0.585   # 台股一趟：手續費 0.1425%×2 + 證交稅 0.3%
STOP_PCT = 0.92
MA10_EXIT_DAYS = 2


class _SyncResult:
    def __init__(self, v): self.v = v
    def get(self, timeout=None): return self.v


class _SyncPool:
    """同步執行版 pool（評估用；production 用 spawn pool + 逾時保護，勿替換）。"""
    def apply_async(self, fn, args): return _SyncResult(fn(*args))
    def close(self): pass
    def join(self): pass
    def terminate(self): pass


def _load_price_series() -> dict[str, dict]:
    by_code: dict[str, dict] = {}
    with (_BACKEND / "data" / "ohlcv.csv").open(newline="", encoding="utf-8") as f:
        for r in csv_mod.DictReader(f):
            if r["code"] in EXCLUDED_CODES:
                continue
            e = by_code.setdefault(r["code"], {"date": [], "open": [], "high": [], "low": [], "close": []})
            e["date"].append(r["date"]); e["open"].append(float(r["open"]))
            e["high"].append(float(r["high"])); e["low"].append(float(r["low"]))
            e["close"].append(float(r["close"]))
    for e in by_code.values():
        order = sorted(range(len(e["date"])), key=lambda i: e["date"][i])
        for k in e:
            e[k] = [e[k][i] for i in order]
    return by_code


def _daily_buckets(eval_days: list[str]) -> dict[str, set]:
    """逐日呼叫 production 訊號管線（as-of 截斷）取得 old_wang 桶。"""
    codes = ss._load_leaders()
    groups = ss._load_leader_groups()
    stock_markets = ss.load_stock_markets()
    fundamentals = ss.load_fundamentals()
    buckets: dict[str, set] = {}
    for i, day in enumerate(eval_days):
        ohlcv = ss._load_ohlcv(day)
        ctx = ss._market_context(ohlcv)
        ctx["stock_markets"] = stock_markets
        ctx["sector_rotation"] = ss._sector_rotation_context(groups, ohlcv)
        ctx["fundamentals"] = fundamentals
        sigs = ss._run_signal_batch(codes, ohlcv, {}, ctx, timeout_seconds=999, pool_factory=_SyncPool)
        buckets[day] = {s["code"] for s in sigs if s.get("old_wang_flag") and s.get("data_ok", True)}
        if i % 50 == 0:
            print(f"  [{day}] {len(buckets[day])} 檔候選", flush=True)
    return buckets


def _simulate(rule: str, by_code: dict, buckets: dict[str, set],
              sig_start: str, sig_end: str) -> list[dict]:
    trades: list[dict] = []
    for code, e in by_code.items():
        d, o, c = e["date"], e["open"], e["close"]
        n = len(d)
        holding = None
        below = 0
        for i in range(n):
            day = d[i]
            if day not in buckets:
                continue
            if holding:
                reason = None
                if rule == "bucket_exit":
                    if code not in buckets[day]:
                        reason = "left_bucket"
                else:
                    if c[i] < holding["entry"] * STOP_PCT:
                        reason = "stop_-8%"
                    elif i >= 9:
                        ma10 = sum(c[i - 9:i + 1]) / 10
                        below = below + 1 if c[i] < ma10 else 0
                        if below >= MA10_EXIT_DAYS:
                            reason = "ma10_break_2d"
                if reason:
                    if i + 1 < n:
                        ret = (o[i + 1] - holding["entry"]) / holding["entry"] * 100
                        trades.append({"code": code, "signal_date": holding["sig"],
                                       "entry_date": holding["in"], "entry_price": holding["entry"],
                                       "exit_date": d[i + 1], "exit_price": o[i + 1],
                                       "holding_trading_days": i + 1 - holding["i"],
                                       "return_pct": round(ret, 2), "exit_reason": reason,
                                       "unresolved": False})
                    else:
                        trades.append({"code": code, "signal_date": holding["sig"],
                                       "entry_date": holding["in"], "entry_price": holding["entry"],
                                       "exit_date": None, "exit_price": None,
                                       "holding_trading_days": None, "return_pct": None,
                                       "exit_reason": f"{reason}_no_next_open", "unresolved": True})
                    holding = None
                    below = 0
                continue
            if not (sig_start <= day <= sig_end):
                continue
            if code in buckets[day]:
                j = bisect_right(e["date"], day)
                if j >= n:
                    continue
                holding = {"entry": o[j], "i": j, "in": d[j], "sig": day}
                below = 0
        if holding:
            trades.append({"code": code, "signal_date": holding["sig"], "entry_date": holding["in"],
                           "entry_price": holding["entry"], "exit_date": None, "exit_price": None,
                           "holding_trading_days": None, "return_pct": None,
                           "exit_reason": "open_at_data_end", "unresolved": True})
    trades.sort(key=lambda t: (t["signal_date"], t["code"]))
    return trades


def _summary(trades: list[dict]) -> dict:
    done = [t for t in trades if not t["unresolved"]]
    rets = sorted(t["return_pct"] for t in done)
    if not rets:
        return {"signals": len(trades), "completed_trades": 0}
    contrib: Counter = Counter()
    for t in done:
        contrib[t["code"]] += t["return_pct"]
    top5 = [c for c, _ in contrib.most_common(5)]
    rest = [t["return_pct"] for t in done if t["code"] not in top5]
    return {
        "signals": len(trades), "completed_trades": len(done),
        "unresolved_trades": len(trades) - len(done),
        "win_rate_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
        "avg_pct": round(statistics.mean(rets), 2),
        "median_pct": round(statistics.median(rets), 2),
        "sum_pct": round(sum(rets), 1),
        "avg_after_cost_pct": round(statistics.mean(rets) - ROUND_TRIP_COST_PCT, 2),
        "avg_holding_trading_days": round(statistics.mean(t["holding_trading_days"] for t in done), 1),
        "top5_contributors": [(c, round(v, 1)) for c, v in contrib.most_common(5)],
        "avg_without_top5_pct": round(statistics.mean(rest), 2) if rest else None,
        "exit_reason_counts": dict(Counter(t["exit_reason"] for t in trades)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="台股 old_wang 桶 walk-forward 回放（evaluation-only）")
    parser.add_argument("--start", default="2025-05-02")
    parser.add_argument("--end", default="2026-06-30")
    args = parser.parse_args()

    by_code = _load_price_series()
    all_days = sorted({day for e in by_code.values() for day in e["date"]})
    eval_days = [day for day in all_days if day >= args.start]
    if not eval_days:
        print("[ERROR] 區間內無資料", file=sys.stderr)
        return 2
    print(f"評估 {len(eval_days)} 個交易日（{eval_days[0]}..{eval_days[-1]}）；"
          f"排除污染 codes：{','.join(EXCLUDED_CODES)}", flush=True)

    buckets = _daily_buckets(eval_days)
    result = {
        "config": {"strategy": "tw_old_wang_bucket_replay",
                   "signal_window": [args.start, args.end],
                   "excluded_codes": list(EXCLUDED_CODES),
                   "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                   "note": "evaluation-only：候選判定=production 管線；非推薦、非買賣建議、不下單"},
        "rules": {}, "limitations": [
            "TWSE 原始價未還原企業行動：除息缺口（<10%）低估報酬（保守偏誤）",
            "資料僅約 14 個月且為超級多頭年；無空頭段",
            "leaders.json 於 2026-06 建立：universe 事後選擇偏誤（妖股是漲完才進清單）",
            "逐筆等權加總非投組報酬；未計滑價",
        ],
    }
    for rule in ("bucket_exit", "wang_protect"):
        trades = _simulate(rule, by_code, buckets, args.start, args.end)
        result["rules"][rule] = {"summary": _summary(trades), "trades": trades}
        print(f"\n=== {rule} ===")
        for k, v in result["rules"][rule]["summary"].items():
            print(f"  {k}: {v}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"tw_old_wang_replay_{args.start}_{args.end}"
    (OUT_DIR / f"{stem}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[WRITE] {OUT_DIR / (stem + '.json')}")
    print("[NOTE] evaluation-only：非推薦、非買賣建議、不下單；限制見 JSON limitations。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
