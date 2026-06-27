import csv
import json
from datetime import date, timedelta

from scripts.run_backtest import TRADE_FIELDS, main


def _write_ohlcv(path, codes=("TEST", "0050"), count=63):
    fields = ("date", "code", "open", "high", "low", "close", "volume")
    start = date(2025, 1, 2)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for code in codes:
            for index in range(count):
                close = 100.0 + index * 0.1
                writer.writerow(
                    {
                        "date": (start + timedelta(days=index)).isoformat(),
                        "code": code,
                        "open": close,
                        "high": close + 1,
                        "low": close - 1,
                        "close": close,
                        "volume": 1_000 + index,
                    }
                )


def test_cli_writes_summary_and_stable_trade_csv(tmp_path):
    ohlcv_path = tmp_path / "ohlcv.csv"
    out_dir = tmp_path / "out"
    _write_ohlcv(ohlcv_path)

    exit_code = main(
        [
            "--code", "TEST",
            "--ohlcv-path", str(ohlcv_path),
            "--out-dir", str(out_dir),
            "--slippage-bps", "0",
        ]
    )

    assert exit_code == 0
    summary_path = out_dir / "backtest_summary.json"
    trades_path = out_dir / "backtest_trades.csv"
    assert summary_path.exists()
    assert trades_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["code"] == "TEST"
    assert summary["lookahead_guard"] is True
    assert "equity_curve" not in summary
    with trades_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == TRADE_FIELDS


def test_cli_reports_unknown_code_without_writing_outputs(tmp_path, capsys):
    ohlcv_path = tmp_path / "ohlcv.csv"
    out_dir = tmp_path / "out"
    _write_ohlcv(ohlcv_path, codes=("0050",))

    exit_code = main(
        [
            "--code", "TEST",
            "--ohlcv-path", str(ohlcv_path),
            "--out-dir", str(out_dir),
        ]
    )

    assert exit_code == 1
    assert "TEST" in capsys.readouterr().err
    assert not (out_dir / "backtest_summary.json").exists()
