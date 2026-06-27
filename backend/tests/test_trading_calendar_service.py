from datetime import date

from app import utils
from app.services import trading_calendar_service as svc


def test_weekends_are_not_trading_days_without_calendar_file(tmp_path):
    calendar = svc.load_trading_calendar(tmp_path / "missing.json")

    assert svc.is_trading_day(date(2026, 6, 20), calendar) is False
    assert svc.is_trading_day(date(2026, 6, 22), calendar) is True
    assert svc.count_missed_trading_days_since(
        date(2026, 6, 19),
        today=date(2026, 6, 23),
        calendar=calendar,
    ) == 1


def test_configured_holiday_is_not_counted_as_missed_trading_day(tmp_path):
    path = tmp_path / "trading_calendar.json"
    path.write_text(
        '{"market":"TW","holidays":["2026-06-22"],"makeup_trading_days":[]}',
        encoding="utf-8",
    )
    calendar = svc.load_trading_calendar(path)

    assert svc.is_trading_day(date(2026, 6, 22), calendar) is False
    assert svc.count_missed_trading_days_since(
        date(2026, 6, 19),
        today=date(2026, 6, 23),
        calendar=calendar,
    ) == 0


def test_configured_makeup_day_is_counted_as_trading_day(tmp_path):
    path = tmp_path / "trading_calendar.json"
    path.write_text(
        '{"market":"TW","holidays":[],"makeup_trading_days":["2026-06-20"]}',
        encoding="utf-8",
    )
    calendar = svc.load_trading_calendar(path)

    assert svc.is_trading_day(date(2026, 6, 20), calendar) is True
    assert svc.count_missed_trading_days_since(
        date(2026, 6, 19),
        today=date(2026, 6, 21),
        calendar=calendar,
    ) == 1


def test_previous_trading_day_respects_holidays_and_weekends(tmp_path):
    path = tmp_path / "trading_calendar.json"
    path.write_text(
        '{"market":"TW","holidays":["2026-06-19"],"makeup_trading_days":[]}',
        encoding="utf-8",
    )
    calendar = svc.load_trading_calendar(path)

    assert svc.previous_trading_day(date(2026, 6, 22), calendar) == date(2026, 6, 18)


def test_malformed_calendar_falls_back_to_weekday_logic(tmp_path):
    path = tmp_path / "trading_calendar.json"
    path.write_text("{broken", encoding="utf-8")
    calendar = svc.load_trading_calendar(path)

    assert calendar["holidays"] == set()
    assert calendar["makeup_trading_days"] == set()
    assert svc.is_trading_day(date(2026, 6, 22), calendar) is True


def test_utils_count_missed_trading_days_uses_default_calendar(monkeypatch, tmp_path):
    path = tmp_path / "trading_calendar.json"
    path.write_text(
        '{"market":"TW","holidays":["2026-06-22"],"makeup_trading_days":[]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "TRADING_CALENDAR_PATH", path)

    assert utils.count_missed_trading_days(
        date(2026, 6, 19),
        today=date(2026, 6, 23),
    ) == 0
