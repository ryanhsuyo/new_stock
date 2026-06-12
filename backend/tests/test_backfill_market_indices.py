import sys
from datetime import date
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "scripts"))

import backfill_ohlcv_twse as bf  # type: ignore[import]


def test_parse_twse_index_month_merges_ohlc_and_volume():
    hist_payload = {
        "stat": "OK",
        "data": [
            ["115/05/04", "39,228.39", "40,755.52", "39,228.39", "40,705.14"],
            ["115/05/05", "40,708.40", "40,885.05", "40,522.78", "40,769.29"],
        ],
    }
    volume_payload = {
        "stat": "OK",
        "data": [
            ["115/05/04", "12,395,796,663", "1,051,315,643,566", "5,275,383", "40,705.14", "1,778.51"],
            ["115/05/05", "12,853,494,887", "1,049,334,722,789", "5,728,961", "40,769.29", "64.15"],
        ],
    }

    rows = bf._parse_twse_index_month(hist_payload, volume_payload)

    assert rows[0] == {
        "date": "2026-05-04",
        "code": "TSE",
        "open": 39228.39,
        "high": 40755.52,
        "low": 39228.39,
        "close": 40705.14,
        "volume": 12395796663,
    }
    assert rows[1]["volume"] == 12853494887


def test_parse_tpex_index_current_merges_ohlc_and_volume():
    index_payload = [
        {"Date": "20260504", "Open": "385.82", "High": "398.43", "Low": "385.82", "Close": "398.25"},
        {"Date": "20260505", "Open": "398.61", "High": "407.44", "Low": "398.61", "Close": "407.44"},
    ]
    trading_payload = [
        {"Date": "1150504", "TradeVolume": "1199555663", "TPExIndex": "398.25"},
        {"Date": "1150505", "TradeVolume": "1351741307", "TPExIndex": "407.44"},
    ]

    rows = bf._parse_tpex_index_current(index_payload, trading_payload)

    assert rows[0]["code"] == "OTC"
    assert rows[0]["date"] == "2026-05-04"
    assert rows[0]["open"] == 385.82
    assert rows[0]["high"] == 398.43
    assert rows[0]["low"] == 385.82
    assert rows[0]["close"] == 398.25
    assert rows[0]["volume"] == 1199555663


def test_fetch_market_indices_collects_twse_months_and_tpex_current(monkeypatch):
    calls: list[tuple[int, int]] = []

    def mock_twse(year: int, month: int):
        calls.append((year, month))
        return [{
            "date": f"{year}-{month:02d}-01",
            "code": "TSE",
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 100,
        }]

    monkeypatch.setattr(bf, "fetch_twse_index_month", mock_twse)
    monkeypatch.setattr(bf, "fetch_tpex_index_current", lambda: [{
        "date": "2026-05-01",
        "code": "OTC",
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 200,
    }])
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows = bf.fetch_market_indices(2, include_current_month=True, _today=date(2026, 5, 11))

    assert calls == [(2026, 5), (2026, 4)]
    assert [row["code"] for row in rows].count("TSE") == 2
    assert [row["code"] for row in rows].count("OTC") == 1
