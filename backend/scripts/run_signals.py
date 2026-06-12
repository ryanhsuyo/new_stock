#!/usr/bin/env python3
"""
run_signals.py — 執行日訊號計算並列印摘要

用法：
    python3 backend/scripts/run_signals.py
    python3 backend/scripts/run_signals.py --as-of 2026-03-01

輸出（寫入 backend/out/）：
    summary.json          — 含 signal_counts / no_buy_reason_counts
    universe_report.csv   — 每支股票的完整分析結果
    daily_brief.json      — 每日作戰表
    daily_check.json      — PM Daily Check 快照

前置條件：
    backend/data/leaders.json   — 股票代碼清單
    backend/data/ohlcv.csv      — 日 OHLCV 歷史資料（先跑 backfill_ohlcv_twse.py）
"""

import argparse
import sys
from pathlib import Path

_HERE    = Path(__file__).resolve().parent   # backend/scripts/
_BACKEND = _HERE.parent                      # backend/
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_BACKEND))

from app.services.signals_service import run_daily_signals
from daily_check import build_daily_summary, write_daily_summary
from doctor import build_doctor_report

# 訊號中文標籤
_SIGNAL_LABELS: dict[str, str] = {
    "entry_confirmed":    "入場確認",
    "ready_to_enter":     "準備入場",
    "watchlist":          "觀察中  ",
    "hold":               "可續抱  ",
    "take_profit_warning": "停利注意",
    "exit_warning":       "出場警示",
    "invalidated":        "訊號失效",
    "DATA_MISSING":       "資料不足",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="計算全宇宙股票日訊號，輸出至 backend/out/"
    )
    parser.add_argument(
        "--as-of",
        metavar="YYYY-MM-DD",
        default=None,
        help="計算基準日（預設：今日）",
    )
    return parser.parse_args()


def print_summary(result: dict) -> None:
    sep = "=" * 55
    print(sep)
    print(f"  訊號摘要  {result['as_of']}  (產生於 {result['generated_at']})")
    print(sep)
    print(f"  宇宙總數  : {result['universe_size']} 支")
    print(f"  資料完整  : {result['data_ok_count']} 支")
    print(f"  資料不足  : {result['data_missing_count']} 支")
    market = result.get("market_context") or {}
    if market:
        print(
            f"  市場濾網  : {market.get('market_regime', 'unknown')} / "
            f"{market.get('market_filter', 'neutral')}  "
            f"({market.get('reason', '')})"
        )
    print()

    # ── 訊號分佈 ──
    print("  ── 訊號分佈 ──")
    counts = result.get("signal_counts", {})
    for key, label in _SIGNAL_LABELS.items():
        cnt = counts.get(key, 0)
        if cnt == 0:
            continue
        bar = "█" * cnt
        print(f"    {label}  {cnt:3d}  {bar}")
    print()

    # ── 未進場原因統計 ──
    reason_counts = result.get("no_buy_reason_counts", {})
    if reason_counts:
        print("  ── 未進場原因統計 ──")
        for reason, cnt in reason_counts.items():
            print(f"    [{cnt:3d}]  {reason}")
        print()

    # ── 入場確認標的 ──
    entries = [s for s in result["signals"] if s.get("internal_signal") == "entry_confirmed"]
    if entries:
        print("  ── 入場確認標的 ──")
        for s in entries:
            print(
                f"    {s['code']} {s['name']:8s}  "
                f"收:{s['close']}  MA20:{s['ma20']}  MA60:{s['ma60']}  "
                f"RSI:{s['rsi14']}  量比:{s['vol_ratio']}  "
                f"進場分:{s.get('entry_score')}  R/R:{s.get('reward_risk_ratio')}"
            )
        print()

    # ── 準備入場標的 ──
    readies = [s for s in result["signals"] if s.get("internal_signal") == "ready_to_enter"]
    if readies:
        print("  ── 準備入場標的 ──")
        for s in readies:
            print(
                f"    {s['code']} {s['name']:8s}  "
                f"收:{s['close']}  支撐:{s['support_price']}  壓力:{s['resistance_price']}  "
                f"RSI:{s['rsi14']}  進場分:{s.get('entry_score')}  R/R:{s.get('reward_risk_ratio')}"
            )
        print()

    # ── 出場警示 / 失效 ──
    warnings = [
        s for s in result["signals"]
        if s.get("internal_signal") in ("exit_warning", "invalidated")
    ]
    if warnings:
        print("  ── 出場警示 / 訊號失效 ──")
        for s in warnings:
            label = "❌失效" if s.get("internal_signal") == "invalidated" else "⚠️出場"
            print(f"    {label} {s['code']} {s['name']:8s}  {s['no_buy_reason']}")
        print()

    _out = _BACKEND / "out"
    print(f"  輸出目錄  : {_out}")
    print("    summary.json  /  universe_report.csv")
    print("    daily_brief.json  /  daily_check.json")
    print(sep)


def write_daily_check_report() -> Path:
    """重算 signals 後刷新 PM Daily Check 快照，供 Dashboard 讀取。"""
    report = build_doctor_report(_BACKEND)
    summary = build_daily_summary(report, limit=3)
    return write_daily_summary(summary, _BACKEND)


def main() -> None:
    args   = parse_args()
    result = run_daily_signals(as_of_date=args.as_of)
    print_summary(result)
    try:
        path = write_daily_check_report()
        print(f"  Daily Check: {path}")
    except Exception as exc:
        print(f"  Daily Check 寫入失敗: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
