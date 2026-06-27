from datetime import date, timedelta

import pytest

import app.services.backtest_service as backtest_service
import app.services.signals_service as signals_service
from app.services.backtest_service import (
    BacktestConfig,
    _core_signal_callback,
    _affordable_shares,
    _apply_slippage,
    _max_drawdown,
    _validate_config,
    _validate_rows,
    run_backtest,
)
from app.services.trade_service import calculate_trade_amounts


TRADING_SETTINGS = {
    "brokerage_fee_rate": 0.001425,
    "brokerage_discount": 1.0,
    "min_brokerage_fee": 0.0,
    "sell_transaction_tax_rate": 0.003,
}


def _rows(count: int = 3) -> list[dict]:
    start = date(2026, 1, 2)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 100.0 + index,
            "high": 102.0 + index,
            "low": 99.0 + index,
            "close": 101.0 + index,
            "volume": 1_000 + index,
        }
        for index in range(count)
    ]


@pytest.mark.parametrize(
    "config",
    [
        BacktestConfig(initial_cash=0),
        BacktestConfig(slippage_bps=-1),
        BacktestConfig(lot_size=0),
        BacktestConfig(minimum_history=59),
    ],
)
def test_validate_config_rejects_invalid_values(config):
    with pytest.raises(ValueError):
        _validate_config(config)


def test_validate_rows_rejects_duplicate_or_unsorted_dates():
    rows = _rows()
    rows[2]["date"] = rows[1]["date"]

    with pytest.raises(ValueError, match="date"):
        _validate_rows(rows)


def test_validate_rows_rejects_invalid_ohlc_geometry():
    rows = _rows()
    rows[1]["high"] = 90.0

    with pytest.raises(ValueError, match=rows[1]["date"]):
        _validate_rows(rows)


def test_slippage_always_moves_fill_against_strategy():
    assert _apply_slippage(100.0, "buy", 10) == pytest.approx(100.1)
    assert _apply_slippage(100.0, "sell", 10) == pytest.approx(99.9)


def test_trade_amounts_accept_injected_settings():
    settings = {**TRADING_SETTINGS, "brokerage_discount": 0.5}

    buy = calculate_trade_amounts("buy", 100.0, 1_000, settings=settings)
    sell = calculate_trade_amounts("sell", 100.0, 1_000, settings=settings)

    assert buy == {
        "gross_amount": 100_000.0,
        "fee": 71.0,
        "tax": 0.0,
        "net_amount": 100_071.0,
    }
    assert sell == {
        "gross_amount": 100_000.0,
        "fee": 71.0,
        "tax": 300.0,
        "net_amount": 99_629.0,
    }


def test_affordable_shares_respects_fee_and_lot_size():
    assert _affordable_shares(100_100.0, 100.0, 1_000, TRADING_SETTINGS) == 0
    assert _affordable_shares(100_200.0, 100.0, 1_000, TRADING_SETTINGS) == 1_000


def test_max_drawdown_uses_prior_equity_peak():
    assert _max_drawdown([100.0, 120.0, 90.0, 99.0]) == 25.0


def _backtest_rows(count: int = 63) -> list[dict]:
    rows = _rows(count)
    for row in rows:
        row.update({"open": 100.0, "high": 121.0, "low": 79.0, "close": 100.0})
    return rows


def _signal_for_lengths(states: dict[int, str], seen: list | None = None):
    def callback(stock_rows, benchmark_rows, is_holding):
        if seen is not None:
            seen.append((len(stock_rows), len(benchmark_rows), is_holding))
        return {
            "data_ok": True,
            "internal_signal": states.get(len(stock_rows), "watchlist"),
            "data_as_of": stock_rows[-1]["date"],
            "reasons": ["fixed test signal"],
            "risk_note": "—",
            "no_buy_reason": "",
        }

    return callback


def test_signal_at_close_fills_at_next_open_and_exit_does_the_same():
    rows = _backtest_rows()
    rows[60]["open"] = 100.0
    rows[61]["open"] = 110.0
    callback = _signal_for_lengths({60: "ready_to_enter", 61: "exit_warning"})

    result = run_backtest(
        "TEST",
        rows,
        config=BacktestConfig(initial_cash=10_000, slippage_bps=0),
        trading_settings={**TRADING_SETTINGS, "brokerage_fee_rate": 0.0, "sell_transaction_tax_rate": 0.0},
        signal_callback=callback,
    )

    assert [(trade["side"], trade["signal_date"], trade["fill_date"]) for trade in result["trades"]] == [
        ("buy", rows[59]["date"], rows[60]["date"]),
        ("sell", rows[60]["date"], rows[61]["date"]),
    ]
    assert result["trades"][0]["fill_price"] == 100.0
    assert result["trades"][1]["fill_price"] == 110.0
    assert result["summary"]["final_equity"] == 11_000.0
    assert result["summary"]["total_return_pct"] == 10.0
    assert result["summary"]["closed_trade_count"] == 1
    assert result["summary"]["win_rate_pct"] == 100.0


def test_callback_only_receives_historical_stock_and_benchmark_prefixes():
    rows = _backtest_rows()
    benchmark = _backtest_rows(70)
    seen = []

    run_backtest(
        "TEST",
        rows,
        benchmark,
        trading_settings=TRADING_SETTINGS,
        signal_callback=_signal_for_lengths({}, seen),
    )

    assert seen[0][:2] == (60, 60)
    assert seen[-1][0] == len(rows)
    assert all(benchmark_count <= stock_count for stock_count, benchmark_count, _ in seen)


def test_repeated_entry_states_create_only_one_buy():
    rows = _backtest_rows()
    callback = _signal_for_lengths({60: "ready_to_enter", 61: "entry_confirmed", 62: "ready_to_enter"})

    result = run_backtest(
        "TEST",
        rows,
        config=BacktestConfig(initial_cash=10_000, slippage_bps=0),
        trading_settings={**TRADING_SETTINGS, "brokerage_fee_rate": 0.0},
        signal_callback=callback,
    )

    assert [trade["side"] for trade in result["trades"]] == ["buy"]
    assert result["summary"]["skipped_actions"]["already_holding"] == 2


def test_open_position_is_valued_net_of_estimated_sell_costs():
    rows = _backtest_rows()
    rows[-1]["close"] = 120.0

    result = run_backtest(
        "TEST",
        rows,
        config=BacktestConfig(initial_cash=10_000, slippage_bps=0),
        trading_settings={**TRADING_SETTINGS, "brokerage_fee_rate": 0.0, "sell_transaction_tax_rate": 0.01},
        signal_callback=_signal_for_lengths({60: "ready_to_enter"}),
    )

    assert [trade["side"] for trade in result["trades"]] == ["buy"]
    assert result["summary"]["open_position"]["shares"] == 100
    assert result["summary"]["final_equity"] == 11_880.0


def test_force_close_records_final_close_sell():
    rows = _backtest_rows()
    rows[-1]["close"] = 120.0

    result = run_backtest(
        "TEST",
        rows,
        config=BacktestConfig(initial_cash=10_000, slippage_bps=0, force_close=True),
        trading_settings={**TRADING_SETTINGS, "brokerage_fee_rate": 0.0, "sell_transaction_tax_rate": 0.0},
        signal_callback=_signal_for_lengths({60: "ready_to_enter"}),
    )

    assert [trade["side"] for trade in result["trades"]] == ["buy", "sell"]
    assert result["trades"][-1]["trigger_state"] == "forced_close"
    assert result["trades"][-1]["fill_date"] == rows[-1]["date"]
    assert result["summary"]["open_position"] is None


def test_insufficient_history_is_explainable_completed_result():
    result = run_backtest(
        "TEST",
        _backtest_rows(59),
        trading_settings=TRADING_SETTINGS,
        signal_callback=_signal_for_lengths({}),
    )

    assert result["summary"]["status"] == "insufficient_history"
    assert result["summary"]["closed_trade_count"] == 0
    assert result["summary"]["win_rate_pct"] is None
    assert result["trades"] == []


def test_signal_data_as_of_mismatch_fails_loudly():
    rows = _backtest_rows()

    def stale_callback(stock_rows, benchmark_rows, is_holding):
        return {
            "data_ok": True,
            "internal_signal": "watchlist",
            "data_as_of": "2020-01-01",
            "reasons": [],
            "risk_note": "—",
            "no_buy_reason": "",
        }

    with pytest.raises(ValueError, match="data_as_of"):
        run_backtest(
            "TEST",
            rows,
            trading_settings=TRADING_SETTINGS,
            signal_callback=stale_callback,
        )


def test_insufficient_cash_skips_entry_without_negative_cash():
    rows = _backtest_rows()

    result = run_backtest(
        "TEST",
        rows,
        config=BacktestConfig(initial_cash=50, slippage_bps=0, lot_size=1),
        trading_settings=TRADING_SETTINGS,
        signal_callback=_signal_for_lengths({60: "ready_to_enter"}),
    )

    assert result["trades"] == []
    assert result["summary"]["final_equity"] == 50.0
    assert result["summary"]["skipped_actions"]["insufficient_cash"] == 1


def test_identical_inputs_are_reproducible_except_generated_timestamp():
    rows = _backtest_rows()
    kwargs = {
        "config": BacktestConfig(initial_cash=10_000, slippage_bps=0),
        "trading_settings": {**TRADING_SETTINGS, "brokerage_fee_rate": 0.0},
        "signal_callback": _signal_for_lengths({60: "ready_to_enter", 61: "exit_warning"}),
    }

    first = run_backtest("TEST", rows, **kwargs)
    second = run_backtest("TEST", rows, **kwargs)
    first["summary"].pop("generated_at")
    second["summary"].pop("generated_at")

    assert first == second


def test_core_adapter_passes_isolated_context_and_returns_approved_fields(monkeypatch):
    rows = _backtest_rows(60)
    benchmark = _backtest_rows(60)
    captured = {}

    def fake_compute(code, stock_rows, positions, context):
        captured.update(
            code=code,
            rows=stock_rows,
            positions=positions,
            context=context,
        )
        return {
            "data_ok": True,
            "internal_signal": "hold",
            "data_as_of": stock_rows[-1]["date"],
            "reasons": ["core reason"],
            "risk_note": "—",
            "no_buy_reason": "holding",
            "old_wang_score": 99,
        }

    monkeypatch.setattr(signals_service, "_compute_signal", fake_compute)

    result = _core_signal_callback("TEST", rows, benchmark, True)

    assert set(result) == {
        "data_ok", "internal_signal", "data_as_of", "reasons",
        "risk_note", "no_buy_reason",
    }
    assert captured["rows"] == rows
    assert "TEST" in captured["positions"]["holdings"]
    assert captured["context"]["core_backtest"] is True
    assert captured["context"]["benchmark_rows"] == benchmark
    assert captured["context"]["fundamentals"] == {}
    assert captured["context"]["sector_rotation"] == {}


def test_core_adapter_uses_neutral_market_without_benchmark(monkeypatch):
    rows = _backtest_rows(60)
    captured = {}

    def fake_compute(code, stock_rows, positions, context):
        captured.update(context)
        return {
            "data_ok": True,
            "internal_signal": "watchlist",
            "data_as_of": stock_rows[-1]["date"],
            "reasons": [],
            "risk_note": "—",
            "no_buy_reason": "neutral",
        }

    monkeypatch.setattr(signals_service, "_compute_signal", fake_compute)

    _core_signal_callback("TEST", rows, [], False)

    assert captured["market_regime"] == "unknown"
    assert captured["market_filter"] == "neutral"
    assert captured["benchmark_rows"] == []


def test_core_adapter_does_not_read_current_chip_data(monkeypatch):
    rows = _backtest_rows(80)
    benchmark = _backtest_rows(80)

    def fail_chip_read(code):
        raise AssertionError(f"current chip data read for {code}")

    monkeypatch.setattr(signals_service, "get_chip_metrics", fail_chip_read)

    result = _core_signal_callback("TEST", rows, benchmark, False)

    assert result["data_as_of"] == rows[-1]["date"]
    assert result["internal_signal"]


def test_run_backtest_uses_core_adapter_by_default(monkeypatch):
    rows = _backtest_rows()
    calls = []

    def fake_core(code, stock_rows, benchmark_rows, is_holding):
        calls.append((code, len(stock_rows), is_holding))
        return _signal_for_lengths({60: "ready_to_enter"})(
            stock_rows, benchmark_rows, is_holding
        )

    monkeypatch.setattr(backtest_service, "_core_signal_callback", fake_core)

    result = run_backtest(
        "TEST",
        rows,
        trading_settings={**TRADING_SETTINGS, "brokerage_fee_rate": 0.0},
    )

    assert calls[0] == ("TEST", 60, False)
    assert result["trades"][0]["side"] == "buy"
