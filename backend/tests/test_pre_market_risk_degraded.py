import pytest

from app.services import pre_market_risk_service as risk


def _signal(code: str, change_pct: float | None, points: int = 0) -> dict:
    return {"code": code, "label": code, "change_pct": change_pct, "points": points,
            "status": "ok" if change_pct is not None else "missing"}


def test_all_inputs_missing_lands_on_defensive_not_normal():
    # 什麼都不知道時預設 normal，等於讓資料中斷自動變成放行
    result = risk.estimate_pre_market_risk(
        [_signal("QQQ", None), _signal("TSM", None), _signal("SPY", None)], score=0
    )

    assert result["level"] == "defensive"
    assert result["degraded"] is True
    assert set(result["missing_inputs"]) == {"QQQ", "TSM", "SPY"}


def test_single_usable_input_floors_at_watch():
    result = risk.estimate_pre_market_risk(
        [_signal("QQQ", -0.1), _signal("TSM", None), _signal("SPY", None)], score=0
    )

    assert result["level"] == "watch"
    assert result["usable_count"] == 1
    assert result["missing_inputs"] == ["TSM", "SPY"]


def test_two_usable_inputs_do_not_get_an_artificial_floor():
    result = risk.estimate_pre_market_risk(
        [_signal("QQQ", -0.1), _signal("TSM", -0.2), _signal("SPY", None)], score=0
    )

    assert result["level"] == "normal"


@pytest.mark.parametrize("score,expected", [(2, "watch"), (4, "defensive"), (8, "extreme")])
def test_known_score_wins_when_it_is_more_severe_than_the_floor(score, expected):
    result = risk.estimate_pre_market_risk(
        [_signal("QQQ", -5.0), _signal("TSM", -5.0), _signal("SPY", -5.0)], score=score
    )

    assert result["level"] == expected


@pytest.mark.parametrize("usable_count", [0, 1, 2, 3])
@pytest.mark.parametrize("score", [0, 2, 4, 8])
def test_estimate_is_never_more_lenient_than_the_available_data_supports(usable_count, score):
    """缺資料不得產生比較安全的結論——這是整個降級推估唯一不能破的約束。"""
    signals = [_signal(code, -0.1 if i < usable_count else None)
               for i, code in enumerate(("QQQ", "TSM", "SPY"))]

    result = risk.estimate_pre_market_risk(signals, score=score)
    supported, _label, _exposure, _ok = risk._classification(score)

    assert risk._RISK_SEVERITY[result["level"]] >= risk._RISK_SEVERITY[supported]


def test_estimate_never_returns_unknown():
    for usable in range(4):
        signals = [_signal(code, -0.1 if i < usable else None)
                   for i, code in enumerate(("QQQ", "TSM", "SPY"))]
        assert risk.estimate_pre_market_risk(signals, score=0)["level"] != "unknown"


def test_reason_names_the_missing_inputs():
    result = risk.estimate_pre_market_risk(
        [_signal("QQQ", -0.1), _signal("TSM", None), _signal("SPY", None)], score=0
    )

    assert "TSM" in result["reason"] and "SPY" in result["reason"]
    assert "缺資料不下修風險" in result["reason"]
