import logging
import multiprocessing
from pathlib import Path

import app.services.signals_service as svc
import pytest


def _rows(count: int = 60) -> list[dict]:
    return [
        {
            "date": f"2026-01-{(index % 28) + 1:02d}",
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 1000,
        }
        for index in range(count)
    ]


def test_stock_timeout_defaults_to_twenty_seconds():
    assert svc._resolve_stock_timeout_seconds({}) == 20.0


def test_stock_timeout_accepts_positive_float():
    assert svc._resolve_stock_timeout_seconds(
        {"SIGNAL_STOCK_TIMEOUT_SECONDS": "2.5"}
    ) == 2.5


def test_stock_timeout_invalid_value_falls_back_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        value = svc._resolve_stock_timeout_seconds(
            {"SIGNAL_STOCK_TIMEOUT_SECONDS": "slow"}
        )

    assert value == 20.0
    assert "SIGNAL_STOCK_TIMEOUT_SECONDS" in caplog.text


def test_stock_timeout_non_positive_value_falls_back(caplog):
    with caplog.at_level(logging.WARNING):
        value = svc._resolve_stock_timeout_seconds(
            {"SIGNAL_STOCK_TIMEOUT_SECONDS": "0"}
        )

    assert value == 20.0
    assert "positive" in caplog.text


def test_timeout_row_is_non_tradable_and_preserves_latest_bar(monkeypatch):
    monkeypatch.setattr(svc, "_stock_name", lambda code: "測試股票")
    rows = _rows()
    reason = "訊號計算逾時（超過 2.5 秒）"

    row = svc._build_unavailable_signal(
        "2330",
        rows,
        {},
        reason=reason,
        calculation_status="timeout",
        calculation_error=reason,
    )

    assert row["code"] == "2330"
    assert row["name"] == "測試股票"
    assert row["data_ok"] is False
    assert row["data_missing"] is True
    assert row["signal"] == "DATA_MISSING"
    assert row["internal_signal"] == "DATA_MISSING"
    assert row["score"] == 0
    assert row["position_size_pct"] == 0
    assert row["calculation_status"] == "timeout"
    assert row["calculation_error"] == reason
    assert row["no_buy_reason"] == reason
    assert row["risk_note"] == "計算未完成，不可使用此列做交易判斷"
    assert row["reasons"] == [reason]
    assert row["data_as_of"] == rows[-1]["date"]
    assert row["close"] == rows[-1]["close"]
    assert row["volume"] == rows[-1]["volume"]


def test_short_history_row_is_marked_data_missing(monkeypatch):
    monkeypatch.setattr(svc, "_stock_name", lambda code: "測試股票")
    monkeypatch.setattr(svc, "evaluate_fundamental_guard", lambda code, data: {})

    row = svc._compute_signal("2330", _rows(10), {}, {})

    assert row["calculation_status"] == "data_missing"
    assert "資料不足" in row["calculation_error"]


class _FakeAsyncResult:
    def __init__(self, outcome):
        self.outcome = outcome
        self.timeouts = []

    def get(self, timeout):
        self.timeouts.append(timeout)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class _FakePool:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.submissions = []
        self.closed = False
        self.terminated = False
        self.joined = False

    def apply_async(self, fn, args):
        self.submissions.append((fn, args))
        return _FakeAsyncResult(self.outcomes.pop(0))

    def close(self):
        self.closed = True

    def terminate(self):
        self.terminated = True

    def join(self):
        self.joined = True


def _ok_row(code):
    return {
        "code": code,
        "data_ok": True,
        "signal": "HOLD",
        "no_buy_reason": "等待買點",
        "calculation_status": "ok",
        "calculation_error": "",
    }


def test_signal_batch_preserves_order_and_closes_healthy_pool():
    pool = _FakePool([_ok_row("1111"), _ok_row("2222")])

    signals = svc._run_signal_batch(
        ["1111", "2222"],
        {"1111": _rows(), "2222": _rows()},
        {},
        {},
        timeout_seconds=1.0,
        pool_factory=lambda: pool,
    )

    assert [row["code"] for row in signals] == ["1111", "2222"]
    assert pool.closed is True
    assert pool.joined is True
    assert pool.terminated is False


def test_signal_batch_replaces_timed_out_pool_and_continues(monkeypatch, caplog):
    monkeypatch.setattr(svc, "_stock_name", lambda code: code)
    first_pool = _FakePool([multiprocessing.TimeoutError()])
    second_pool = _FakePool([_ok_row("2222")])
    pools = iter([first_pool, second_pool])

    with caplog.at_level(logging.ERROR):
        signals = svc._run_signal_batch(
            ["1111", "2222"],
            {"1111": _rows(), "2222": _rows()},
            {},
            {},
            timeout_seconds=1.0,
            pool_factory=lambda: next(pools),
        )

    assert [row["code"] for row in signals] == ["1111", "2222"]
    assert signals[0]["calculation_status"] == "timeout"
    assert signals[1]["calculation_status"] == "ok"
    assert first_pool.terminated is True
    assert first_pool.joined is True
    assert second_pool.closed is True
    assert second_pool.joined is True
    assert "1111" in caplog.text
    assert "compute_signal" in caplog.text
    assert "continue" in caplog.text


def test_signal_batch_propagates_unexpected_worker_error():
    pool = _FakePool([RuntimeError("indicator failed")])

    with pytest.raises(RuntimeError, match="indicator failed"):
        svc._run_signal_batch(
            ["1111"],
            {"1111": _rows()},
            {},
            {},
            timeout_seconds=1.0,
            pool_factory=lambda: pool,
        )

    assert pool.terminated is True
    assert pool.joined is True
    assert pool.closed is False


def test_universe_report_has_calculation_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "_OUT", tmp_path)

    svc._write_universe_report([_ok_row("1111")])

    header = (tmp_path / "universe_report.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "calculation_status" in header.split(",")
    assert "calculation_error" in header.split(",")


def test_run_daily_signals_uses_batch_and_reports_timeouts(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "_stock_name", lambda code: code)
    rows = _rows()
    reason = "訊號計算逾時（超過 2 秒）"
    timeout_row = svc._build_unavailable_signal(
        "1111",
        rows,
        {},
        reason=reason,
        calculation_status="timeout",
        calculation_error=reason,
    )
    calls = []

    monkeypatch.setattr(svc, "_reload_name_cache", lambda: None)
    monkeypatch.setattr(svc, "get_summary", lambda: None)
    monkeypatch.setattr(svc, "_load_leaders", lambda: ["1111"])
    monkeypatch.setattr(svc, "_load_leader_groups", lambda: {})
    monkeypatch.setattr(svc, "_load_ohlcv", lambda as_of: {"1111": rows})
    monkeypatch.setattr(svc, "_load_positions", lambda: {})
    monkeypatch.setattr(svc, "_market_context", lambda ohlcv: {})
    monkeypatch.setattr(svc, "_sector_rotation_context", lambda groups, ohlcv: {})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {})
    monkeypatch.setattr(svc, "_latest_data_date", lambda codes, ohlcv: "2026-01-28")
    monkeypatch.setattr(svc, "_resolve_stock_timeout_seconds", lambda: 2.0)

    def fake_batch(codes, ohlcv, positions, context, *, timeout_seconds):
        calls.append((codes, timeout_seconds))
        return [timeout_row]

    monkeypatch.setattr(svc, "_run_signal_batch", fake_batch)
    monkeypatch.setattr(
        svc,
        "_compute_signal",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("direct loop used")),
    )
    monkeypatch.setattr(svc, "_annotate_holding_weights", lambda signals, positions: None)
    monkeypatch.setattr(svc, "_annotate_daily_decisions", lambda signals: None)
    monkeypatch.setattr(svc, "_market_note_for_date", lambda as_of: None)
    monkeypatch.setattr(svc, "_write_previous_summary", lambda previous: None)
    monkeypatch.setattr(svc, "_write_summary", lambda result: Path(tmp_path / "summary.json"))
    monkeypatch.setattr(svc, "_write_universe_report", lambda signals: Path(tmp_path / "universe_report.csv"))
    monkeypatch.setattr(svc, "write_daily_brief", lambda result, out: Path(tmp_path / "daily_brief.json"))
    monkeypatch.setattr(svc, "write_priority_fill_csv", lambda out: Path(tmp_path / "priority.csv"))
    monkeypatch.setattr(svc, "write_fundamentals_report", lambda out: Path(tmp_path / "fundamentals.json"))

    result = svc.run_daily_signals(as_of_date="2026-01-28")

    assert calls == [(["1111"], 2.0)]
    assert result["calculation_timeout_seconds"] == 2.0
    assert result["calculation_timeout_count"] == 1
    assert result["calculation_timeout_codes"] == ["1111"]
