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
    assert "訊號摘要" in capsys.readouterr().out


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
    assert "daily_check.json" in out
