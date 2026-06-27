from datetime import date, timedelta

import pytest

import app.services.analysis_service as analysis_service
from app.services.analysis_service import _select_multi_touch_pair


def _rows(count: int = 10) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {"date": (start + timedelta(days=index)).isoformat()}
        for index in range(count)
    ]


def _swing(rows: list[dict], index: int, price: float) -> dict:
    return {"date": rows[index]["date"], "price": price}


def test_selects_three_touch_ascending_support():
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        _swing(rows, 4, 14.0),
    ]

    result = _select_multi_touch_pair(rows, swings, direction="up")

    assert result == (swings[0], swings[2], 3)


def test_selects_three_touch_descending_resistance():
    rows = _rows()
    swings = [
        _swing(rows, 0, 20.0),
        _swing(rows, 2, 18.0),
        _swing(rows, 4, 16.0),
    ]

    result = _select_multi_touch_pair(rows, swings, direction="down")

    assert result == (swings[0], swings[2], 3)


def test_rejects_ascending_support_broken_by_later_low():
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        _swing(rows, 4, 10.0),
    ]

    assert _select_multi_touch_pair(rows, swings, direction="up") is None


def test_rejects_descending_resistance_broken_by_later_high():
    rows = _rows()
    swings = [
        _swing(rows, 0, 20.0),
        _swing(rows, 2, 18.0),
        _swing(rows, 4, 22.0),
    ]

    assert _select_multi_touch_pair(rows, swings, direction="down") is None


def test_prefers_more_touches_over_newer_two_point_pair():
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        _swing(rows, 4, 14.0),
        _swing(rows, 6, 16.0),
        _swing(rows, 8, 30.0),
    ]

    result = _select_multi_touch_pair(rows, swings, direction="up")

    assert result == (swings[0], swings[3], 4)


def test_returns_none_when_swing_date_is_unknown():
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        {"date": "2025-12-01", "price": 14.0},
    ]

    assert _select_multi_touch_pair(rows, swings, direction="up") is None


def test_returns_none_for_non_positive_swing_price():
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        _swing(rows, 4, 0.0),
    ]

    assert _select_multi_touch_pair(rows, swings, direction="up") is None


def test_uptrend_builder_reports_multi_touch_confirmation(monkeypatch):
    rows = _rows()
    swings = [
        _swing(rows, 0, 10.0),
        _swing(rows, 2, 12.0),
        _swing(rows, 4, 14.0),
    ]
    monkeypatch.setattr(analysis_service, "_find_swing_lows", lambda *_: swings)

    result = analysis_service._build_uptrend_line(rows)

    assert result.valid is True
    assert result.p1.date == swings[0]["date"]
    assert result.p2.date == swings[2]["date"]
    assert result.note == "連接遞增擺盪低點，多點確認（3 個有效觸點）"


def test_downtrend_builder_reports_multi_touch_confirmation(monkeypatch):
    rows = _rows()
    swings = [
        _swing(rows, 0, 20.0),
        _swing(rows, 2, 18.0),
        _swing(rows, 4, 16.0),
    ]
    monkeypatch.setattr(analysis_service, "_find_swing_highs", lambda *_: swings)

    result = analysis_service._build_downtrend_line(rows)

    assert result.valid is True
    assert result.p1.date == swings[0]["date"]
    assert result.p2.date == swings[2]["date"]
    assert result.note == "連接遞減擺盪高點，多點確認（3 個有效觸點）"


@pytest.mark.parametrize(
    ("builder_name", "finder_name", "prices", "expected_note"),
    [
        (
            "_build_uptrend_line",
            "_find_swing_lows",
            (10.0, 12.0),
            "連接兩個遞增擺盪低點（上升趨勢線）",
        ),
        (
            "_build_downtrend_line",
            "_find_swing_highs",
            (20.0, 18.0),
            "連接兩個遞減擺盪高點（下降趨勢線）",
        ),
    ],
)
def test_builder_keeps_existing_two_point_fallback_note(
    monkeypatch,
    builder_name,
    finder_name,
    prices,
    expected_note,
):
    rows = _rows()
    swings = [
        _swing(rows, 0, prices[0]),
        _swing(rows, 2, prices[1]),
    ]
    monkeypatch.setattr(analysis_service, finder_name, lambda *_: swings)

    result = getattr(analysis_service, builder_name)(rows)

    assert result.valid is True
    assert result.note == expected_note
