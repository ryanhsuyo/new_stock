import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_run_signals_main_refreshes_daily_check(monkeypatch, capsys):
    import run_signals

    calls = []

    monkeypatch.setattr(run_signals, "parse_args", lambda: type("Args", (), {"as_of": None})())
    monkeypatch.setattr(run_signals, "write_daily_check_report", lambda: calls.append("daily_check"))
    monkeypatch.setattr(run_signals, "run_daily_signals", lambda as_of_date=None: {
        "as_of": "2026-05-29",
        "generated_at": "2026-05-29T15:00:00",
        "universe_size": 1,
        "data_ok_count": 1,
        "data_missing_count": 0,
        "market_context": {},
        "signal_alert_count": 0,
        "signal_counts": {"watchlist": 1},
        "no_buy_reason_counts": {},
        "signals": [{
            "code": "2330",
            "name": "台積電",
            "internal_signal": "watchlist",
        }],
    })

    run_signals.main()

    assert calls == ["daily_check"]


def test_run_signals_daily_check_refresh_includes_today_scan_and_alerts(monkeypatch):
    import run_signals

    captured = {}

    monkeypatch.setattr(run_signals, "build_doctor_report", lambda backend: {"overall_status": "ok"})
    monkeypatch.setattr(run_signals, "load_signal_alerts", lambda out_dir: {"alert_count": 1})
    monkeypatch.setattr(run_signals, "load_today_scan_report", lambda out_dir: {"as_of": "2026-06-26"})
    monkeypatch.setattr(
        run_signals,
        "build_daily_summary",
        lambda report, **kwargs: captured.setdefault("kwargs", kwargs) or {"overall_status": "ok"},
    )
    monkeypatch.setattr(run_signals, "write_daily_summary", lambda summary, backend: backend / "out" / "daily_check.json")

    path = run_signals.write_daily_check_report()

    assert path.name == "daily_check.json"
    assert captured["kwargs"]["signal_alerts"] == {"alert_count": 1}
    assert captured["kwargs"]["today_scan"] == {"as_of": "2026-06-26"}


def test_run_signals_daily_check_refresh_includes_manual_market_note_summary(monkeypatch):
    import run_signals

    captured = {}
    signals_summary = {
        "manual_market_note": {
            "date": "2026-05-27",
            "is_stale": True,
            "update_required": True,
        }
    }

    monkeypatch.setattr(run_signals, "build_doctor_report", lambda backend: {"overall_status": "ok"})
    monkeypatch.setattr(run_signals, "load_signal_alerts", lambda out_dir: None)
    monkeypatch.setattr(run_signals, "load_today_scan_report", lambda out_dir: None)
    monkeypatch.setattr(run_signals, "load_summary_for_daily_check", lambda backend: signals_summary, raising=False)
    monkeypatch.setattr(
        run_signals,
        "build_daily_summary",
        lambda report, **kwargs: captured.setdefault("kwargs", kwargs) or {"overall_status": "ok"},
    )
    monkeypatch.setattr(run_signals, "write_daily_summary", lambda summary, backend: backend / "out" / "daily_check.json")

    run_signals.write_daily_check_report()

    assert captured["kwargs"]["signals_summary"] == signals_summary


def test_run_signals_summary_lists_all_primary_outputs(capsys):
    import run_signals

    run_signals.print_summary({
        "as_of": "2026-05-29",
        "generated_at": "2026-05-29T15:00:00",
        "universe_size": 1,
        "data_ok_count": 1,
        "data_missing_count": 0,
        "market_context": {},
        "signal_counts": {"watchlist": 1},
        "no_buy_reason_counts": {},
        "signals": [{"code": "2330", "name": "台積電", "internal_signal": "watchlist"}],
    })

    out = capsys.readouterr().out

    assert "summary.json" in out
    assert "universe_report.csv" in out
    assert "daily_brief.json" in out
    assert "today_scan.json" in out
    assert "daily_check.json" in out
    assert "signal_snapshot_review.json" in out
    assert "signal_alerts.json" in out
    assert "signal_snapshots" in out
    assert "快照警示" in out


def test_run_signals_summary_prints_timeout_codes(capsys):
    import run_signals

    run_signals.print_summary({
        "as_of": "2026-05-29",
        "generated_at": "2026-05-29T15:00:00",
        "universe_size": 2,
        "data_ok_count": 1,
        "data_missing_count": 1,
        "calculation_timeout_seconds": 2.0,
        "calculation_timeout_count": 1,
        "calculation_timeout_codes": ["1111"],
        "market_context": {},
        "signal_counts": {"watchlist": 1, "DATA_MISSING": 1},
        "no_buy_reason_counts": {"訊號計算逾時（超過 2 秒）": 1},
        "signals": [],
    })

    out = capsys.readouterr().out
    assert "計算逾時" in out
    assert "1111" in out
    assert "2" in out
