#!/usr/bin/env python3
"""Run a deterministic single-stock core backtest from daily OHLCV CSV."""

import argparse
import csv
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.services.backtest_service import (  # noqa: E402
    TRADE_FIELDS,
    BacktestConfig,
    run_backtest,
    write_backtest_outputs,
)
from app.services.signals_service import BENCHMARK_CODE  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="回測單一股票的 core 日線訊號（D 日收盤、D+1 開盤成交）"
    )
    parser.add_argument("--code", required=True, help="股票代碼")
    parser.add_argument("--as-of", default=None, help="最後資料日 YYYY-MM-DD")
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--lot-size", type=int, default=1)
    parser.add_argument("--force-close", action="store_true")
    parser.add_argument(
        "--ohlcv-path",
        type=Path,
        default=_BACKEND / "data" / "ohlcv.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_BACKEND / "out",
    )
    return parser.parse_args(argv)


def _load_rows(path: Path, as_of: str | None) -> dict[str, list[dict]]:
    if not path.exists():
        raise ValueError(f"OHLCV file not found: {path}")
    grouped: dict[str, list[dict]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row_date = str(raw.get("date") or "")
            if as_of and row_date > as_of:
                continue
            code = str(raw.get("code") or "").strip().upper()
            if not code:
                continue
            try:
                row = {
                    "date": row_date,
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "volume": float(raw["volume"]),
                }
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid OHLCV row for {code} on {row_date}") from exc
            grouped.setdefault(code, []).append(row)
    return grouped


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    code = args.code.strip().upper()
    try:
        grouped = _load_rows(args.ohlcv_path, args.as_of)
        rows = grouped.get(code)
        if not rows:
            raise ValueError(f"stock code not found in OHLCV: {code}")
        result = run_backtest(
            code,
            rows,
            grouped.get(BENCHMARK_CODE, []),
            config=BacktestConfig(
                initial_cash=args.initial_cash,
                slippage_bps=args.slippage_bps,
                lot_size=args.lot_size,
                force_close=args.force_close,
            ),
        )
        summary_path, trades_path = write_backtest_outputs(result, args.out_dir)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print(f"Backtest {code}: {summary['start_date']} -> {summary['end_date']}")
    print(
        f"Trades: {summary['closed_trade_count']} | "
        f"Return: {summary['total_return_pct']}% | "
        f"Max DD: {summary['max_drawdown_pct']}% | "
        f"Buy & hold: {summary['buy_and_hold_return_pct']}%"
    )
    print(f"Fees: {summary['total_fees']} | Tax: {summary['total_tax']}")
    print(f"Summary: {summary_path}")
    print(f"Trades: {trades_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
