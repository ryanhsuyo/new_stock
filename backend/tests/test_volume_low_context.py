from app.services.signals_service import _volume_low_context


def _row(day: int, low: float, close: float, volume: int) -> dict:
    return {
        "date": f"2026-05-{day:02d}",
        "open": close,
        "high": close,
        "low": low,
        "close": close,
        "volume": volume,
    }


def test_volume_low_uses_largest_absolute_volume_among_explosive_candidates():
    rows = []
    for day in range(1, 21):
        rows.append(_row(day, low=100.0 + day, close=180.0, volume=1_000_000))
    rows.append(_row(21, low=1770.0, close=3630.0, volume=22_780_413))
    rows.extend(_row(day, low=2000.0 + day, close=3630.0, volume=18_000_000) for day in range(22, 36))
    rows.append(_row(36, low=3155.0, close=3630.0, volume=39_638_460))
    rows.append(_row(37, low=3320.0, close=3630.0, volume=8_572_000))

    result = _volume_low_context(rows, ma5=3301.0)

    assert result["price"] == 3155.0
    assert result["date"] == "2026-05-36"
    assert result["volume"] == 39_638_460
