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


# ── 推定臨時休市（reconcile_presumed_closures）──────────────────────────────

def _dates(*values):
    from datetime import date
    return {date.fromisoformat(v) for v in values}


def test_reconcile_presumes_missing_weekday_as_closure(tmp_path):
    # 2026-07-10（週五颱風假情境）：窗口內平日、全市場無資料 → 推定休市
    from datetime import date
    path = tmp_path / "trading_calendar.json"
    market = _dates("2026-07-08", "2026-07-09", "2026-07-13")

    changes = svc.reconcile_presumed_closures(
        market, window_start=date(2026, 7, 6), today=date(2026, 7, 14), path=path)

    assert changes["added"] == ["2026-07-10"]
    calendar = svc.load_trading_calendar(path)
    assert date(2026, 7, 10) in calendar["holidays"]  # 推定日參與新鮮度判定
    assert svc.count_missed_trading_days_since(
        date(2026, 7, 9), today=date(2026, 7, 13), calendar=calendar) == 0  # 假警報消失


def test_reconcile_heals_when_data_arrives_late(tmp_path):
    import json
    from datetime import date
    path = tmp_path / "trading_calendar.json"
    path.write_text(json.dumps({"presumed_closures": ["2026-07-10"]}), encoding="utf-8")
    market = _dates("2026-07-09", "2026-07-10")  # 資料晚到，07-10 出現了

    changes = svc.reconcile_presumed_closures(
        market, window_start=date(2026, 7, 6), today=date(2026, 7, 14), path=path)

    assert changes["removed"] == ["2026-07-10"]
    assert date(2026, 7, 10) not in svc.load_trading_calendar(path)["holidays"]


def test_reconcile_skips_weekends_today_and_human_holidays(tmp_path):
    import json
    from datetime import date
    path = tmp_path / "trading_calendar.json"
    path.write_text(json.dumps({"holidays": ["2026-07-15"]}), encoding="utf-8")
    # 07-11/12 是週末、07-15 是人工假日、07-17 = today → 都不推定；07-16 缺 → 推定
    market = _dates("2026-07-09", "2026-07-10", "2026-07-13", "2026-07-14")

    changes = svc.reconcile_presumed_closures(
        market, window_start=date(2026, 7, 9), today=date(2026, 7, 17), path=path)

    assert changes["added"] == ["2026-07-16"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["holidays"] == ["2026-07-15"]  # 人工假日不被觸碰


def test_reconcile_no_market_data_is_noop(tmp_path):
    from datetime import date
    path = tmp_path / "trading_calendar.json"
    changes = svc.reconcile_presumed_closures(
        set(), window_start=date(2026, 7, 6), today=date(2026, 7, 14), path=path)
    assert changes == {"added": [], "removed": []}
    assert not path.exists()  # 沒變更就不寫檔
