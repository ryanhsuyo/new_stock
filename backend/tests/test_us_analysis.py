"""
test_us_analysis.py — 美股 Phase 2：基本技術指標與描述性狀態。

用 fixture ohlcv_us.csv（monkeypatch）驗證「有資料時算出指標」，並以受控輸入
驗證四種狀態分類。不打真網路。
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import us_analysis_service as ua
from app.storage import us_market_store

client = TestClient(app)


# ── 指標數學 ─────────────────────────────────────────────────────────────────

def test_sma():
    assert ua._sma([1, 2, 3, 4], 2) == 3.5
    assert ua._sma([1, 2], 5) is None


def test_pct_change():
    assert ua._pct_change([10, 11, 12], 2) == 20.0
    assert ua._pct_change([10, 11], 5) is None


def test_rsi_all_gains_is_100():
    assert ua._rsi(list(range(1, 20))) == 100.0


def test_rsi_balanced_is_50():
    closes = [10 + (i % 2) for i in range(15)]  # 10,11,10,11,... → 漲跌相抵
    assert ua._rsi(closes) == 50.0


def test_dist_pct():
    assert ua._dist_pct(110, 100) == 10.0
    assert ua._dist_pct(110, None) is None


# ── 狀態分類（受控輸入，涵蓋四種）──────────────────────────────────────────

def test_status_weak_when_insufficient_rows():
    assert ua.classify_status(10, 100, None, None, None, None) == "weak_or_no_data"


def test_status_overheated_by_rsi_or_distance():
    assert ua.classify_status(65, 200, 150, 140, 75, 10) == "overheated"   # RSI>=70
    assert ua.classify_status(65, 200, 150, 140, 50, 20) == "overheated"   # 距 MA20>=15%


def test_status_trend_up():
    assert ua.classify_status(65, 160, 150, 140, 55, 6.7) == "trend_up"


def test_status_pullback_watch():
    assert ua.classify_status(65, 145, 150, 140, 45, -3.3) == "pullback_watch"


def test_status_weak_when_below_ma60():
    assert ua.classify_status(65, 130, 150, 140, 40, -13) == "weak_or_no_data"


# ── fixture 端到端：有資料 → 指標算得出 ──────────────────────────────────────

def _write_fixture(path, code="AAPL", n=65):
    start = date(2026, 1, 1)
    lines = ["date,code,open,high,low,close,volume"]
    for i in range(n):
        d = (start + timedelta(days=i)).isoformat()
        px = 100 + i  # 線性上升 → 全為漲 → RSI=100 → overheated（確定值）
        lines.append(f"{d},{code},{px},{px+1},{px-1},{px},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_analysis_computes_indicators_with_fixture(tmp_path, monkeypatch):
    csv_path = tmp_path / "ohlcv_us.csv"
    _write_fixture(csv_path, "AAPL", 65)
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", csv_path)

    items = ua.get_us_analysis()
    by_code = {x["code"]: x for x in items}

    aapl = by_code["AAPL"]
    assert aapl["row_count"] == 65
    assert isinstance(aapl["ma20"], float) and isinstance(aapl["ma60"], float)
    assert isinstance(aapl["rsi14"], float)
    assert aapl["ma20"] > aapl["ma60"]                 # 上升 → 短均在長均之上
    assert aapl["last_close"] == 164.0
    assert aapl["status"] == "overheated"              # 全漲 RSI=100
    assert aapl["status_label"] == "過熱"
    assert isinstance(aapl["days_since_last"], int)

    # 其他 ticker 無資料 → 指標 null、weak_or_no_data
    other = next(x for x in items if x["code"] != "AAPL")
    assert other["row_count"] == 0
    assert other["ma20"] is None and other["rsi14"] is None
    assert other["status"] == "weak_or_no_data"


# ── HTTP 端點 ─────────────────────────────────────────────────────────────────

def test_us_analysis_endpoint_schema():
    res = client.get("/api/markets/us/analysis")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    valid = {"trend_up", "pullback_watch", "overheated", "weak_or_no_data"}
    for item in items:
        assert item["region"] == "US"
        assert item["status"] in valid
        for key in ("ma20", "ma60", "rsi14", "change_20d_pct",
                    "dist_ma20_pct", "dist_ma60_pct", "days_since_last",
                    "status_label", "last_close"):
            assert key in item
