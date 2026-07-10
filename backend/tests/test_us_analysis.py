"""
test_us_analysis.py — 美股 Phase 2：基本技術指標與描述性狀態。

用 fixture ohlcv_us.csv（monkeypatch）驗證「有資料時算出指標」，並以受控輸入
驗證六種狀態分類（trend_up / recovering / pullback_watch / overheated / weak /
no_data）。不打真網路。
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


# ── 狀態分類（受控輸入，涵蓋六種）──────────────────────────────────────────

def test_status_no_data_when_insufficient_rows():
    assert ua.classify_status(10, 100, None, None, None, None) == "no_data"


def test_status_no_data_when_ma20_or_close_missing():
    # 筆數夠但算不出 MA20 / 無收盤 → 仍是「無法計算」，不是弱勢
    assert ua.classify_status(65, 100, None, 140, 50, None) == "no_data"
    assert ua.classify_status(65, None, 150, 140, 50, None) == "no_data"


def test_status_overheated_by_rsi_or_distance():
    assert ua.classify_status(65, 200, 150, 140, 75, 10) == "overheated"   # RSI>=70
    assert ua.classify_status(65, 200, 150, 140, 50, 20) == "overheated"   # 距 MA20>=15%


def test_status_trend_up():
    assert ua.classify_status(65, 160, 150, 140, 55, 6.7) == "trend_up"


def test_status_trend_up_without_ma60():
    # 尚無 MA60（20 <= rows < 60）但站上 MA20 → trend_up（維持既有行為）
    assert ua.classify_status(30, 160, 150, None, 55, 6.7) == "trend_up"


def test_status_pullback_watch():
    assert ua.classify_status(65, 145, 150, 140, 45, -3.3) == "pullback_watch"


def test_status_pullback_watch_without_ma60():
    assert ua.classify_status(30, 145, 150, None, 45, -3.3) == "pullback_watch"


def test_status_weak_when_below_ma60():
    # 跌破 MA60 → weak（真正弱勢），**不是** no_data
    assert ua.classify_status(65, 130, 150, 140, 40, -13) == "weak"


def test_status_weak_even_when_above_ma20_but_below_ma60():
    # 站上 MA20 卻仍在 MA60 下方 → 長線偏弱
    assert ua.classify_status(65, 145, 140, 150, 50, 3.6) == "weak"


def test_status_recovering_above_both_ma_but_ma20_below_ma60():
    # 收盤同時站上 MA20 與 MA60，但 MA20 < MA60（均線未翻多）→ recovering
    assert ua.classify_status(65, 160, 145, 150, 55, 10.3) == "recovering"


def test_status_recovering_real_world_meta_and_tsla():
    """
    真實 27 檔回補後浮現的案例：close > MA20 且 close > MA60，但 MA20 < MA60。
    舊邏輯落入 weak_or_no_data（前端顯示「弱勢 / 資料不足」，語意誤導）。
    """
    # META 2026-07-10: close=669.40 ma20=584.62 ma60=612.63 rsi=69 dist_ma20=+14.5%
    assert ua.classify_status(256, 669.40, 584.62, 612.63, 69.0, 14.5) == "recovering"
    # TSLA 2026-07-10: close=410.11 ma20=400.99 ma60=405.25 rsi=53 dist_ma20=+2.3%
    assert ua.classify_status(256, 410.11, 400.99, 405.25, 53.0, 2.3) == "recovering"


def test_status_labels_cover_every_status():
    for s in ("trend_up", "recovering", "pullback_watch", "overheated", "weak", "no_data"):
        assert ua.STATUS_LABELS[s]
    # 混合桶已移除
    assert "weak_or_no_data" not in ua.STATUS_LABELS


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

    # 其他 ticker 無資料 → 指標 null、no_data（**不是 weak**）
    other = next(x for x in items if x["code"] != "AAPL")
    assert other["row_count"] == 0
    assert other["ma20"] is None and other["rsi14"] is None
    assert other["status"] == "no_data"
    assert other["status_label"] == "資料不足"


# ── HTTP 端點 ─────────────────────────────────────────────────────────────────

def test_us_analysis_endpoint_schema():
    res = client.get("/api/markets/us/analysis")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    valid = {"trend_up", "recovering", "pullback_watch", "overheated", "weak", "no_data"}
    for item in items:
        assert item["region"] == "US"
        assert item["status"] in valid
        assert item["status_label"] == ua.STATUS_LABELS[item["status"]]
        for key in ("ma20", "ma60", "rsi14", "change_20d_pct",
                    "dist_ma20_pct", "dist_ma60_pct", "days_since_last",
                    "status_label", "last_close"):
            assert key in item


def test_analysis_endpoint_no_data_status_implies_missing_indicators():
    """資料完整的股票不得被標成 no_data；no_data 必定是真的算不出來。"""
    items = client.get("/api/markets/us/analysis").json()
    for item in items:
        if item["status"] == "no_data":
            assert item["ma20"] is None or item["row_count"] < ua.MIN_ROWS
        else:
            assert item["last_close"] is not None and item["ma20"] is not None
