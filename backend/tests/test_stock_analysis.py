"""
test_stock_analysis.py — 單檔股票分析 API 與服務層測試

覆蓋：
  GET /api/stocks/{code}/analysis
    - schema 欄位齊全
    - support_lines / resistance_lines 結構正確
    - uptrend_line / downtrend_line 結構正確
    - signal 為 7 狀態之一
    - 資料不足時 data_ok=False，不拋 500
    - as_of 查詢參數可接受

  analysis_service（固定測資驗證）
    - _find_swing_lows 在已知上升走勢中能找出低點
    - _find_swing_highs 在已知下降走勢中能找出高點
    - _build_support_lines / _build_resistance_lines 欄位完整
    - 資料不足時回傳空 list
"""

import csv
import io
from datetime import date, timedelta

import pytest

# ---------------------------------------------------------------------------
# 固定測資工廠
# ---------------------------------------------------------------------------

def _make_rows(n: int, start_price: float = 100.0, trend: str = "up") -> list[dict]:
    """
    產生 n 筆合成 OHLCV rows（純 dict，不含 code 欄位）。
    trend="up"  → 收盤價緩步上升，每日 +0.3
    trend="down"→ 收盤價緩步下降，每日 -0.3
    trend="flat"→ 收盤價水平震盪
    """
    rows = []
    d = date(2025, 1, 2)
    price = start_price
    step = {"up": 0.3, "down": -0.3, "flat": 0.0}[trend]

    for i in range(n):
        while d.weekday() >= 5:       # 跳過週末
            d += timedelta(days=1)

        noise = (i % 5 - 2) * 0.5    # ±1 震盪製造擺盪點
        close = round(price + noise, 2)
        rows.append({
            "date":   d.isoformat(),
            "open":   round(close - 0.5, 2),
            "high":   round(close + 2.0, 2),
            "low":    round(close - 2.0, 2),
            "close":  close,
            "volume": 1000 + i * 10,
        })
        price += step
        d += timedelta(days=1)

    return rows


# ---------------------------------------------------------------------------
# API 整合測試（使用真實 ohlcv.csv + leaders.json）
# ---------------------------------------------------------------------------

class TestStockAnalysisAPI:

    def test_returns_200_for_known_code(self, client):
        """2330 有足夠 OHLCV 資料，應回 200。"""
        resp = client.get("/api/stocks/2330/analysis")
        assert resp.status_code == 200

    def test_schema_fields_present(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        required = (
            "code", "name", "as_of", "data_ok", "data_missing_reason",
            "data_diagnostic",
            "is_stale", "stale_days",
            "close", "ma5", "ma20", "ma60", "rsi14", "vol_ratio",
            "long_trend", "short_trend",
            "signal", "score", "reasons", "risk_notes", "no_buy_reason",
            "trend_score", "entry_score", "risk_score",
            "market_regime", "market_filter", "relative_strength_score",
            "relative_strength_60d", "relative_strength_120d", "stage",
            "entry_price_low", "entry_price_high",
            "stop_price", "target_price", "risk_pct", "reward_pct",
            "reward_risk_ratio", "price_plan_note",
            "daily_action", "daily_action_label", "daily_checklist",
            "support_lines", "resistance_lines",
            "uptrend_line", "downtrend_line",
            "pattern",
        )
        for f in required:
            assert f in body, f"欄位缺失: {f}"

    def test_data_diagnostic_marks_latest_close_not_intraday_price(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        diagnostic = body["data_diagnostic"]

        assert diagnostic["price_basis"] == "latest_close"
        assert diagnostic["price_basis_label"] == "最新收盤價"
        assert "不是盤中即時市價" in diagnostic["price_basis_note"]
        assert diagnostic["last_data_as_of"] == body["as_of"]
        assert diagnostic["row_count"] >= 60
        assert diagnostic["status"] == "ok"
        assert diagnostic["next_action_command"] == ""

    def test_data_ok_is_true_for_known_code(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        assert body["data_ok"] is True
        assert body["data_missing_reason"] == ""

    def test_support_lines_structure(self, client):
        lines = client.get("/api/stocks/2330/analysis").json()["support_lines"]
        assert len(lines) >= 1
        for line in lines:
            assert "label" in line
            assert "price" in line
            assert "type" in line
            assert line["type"] in ("static", "dynamic")
            assert isinstance(line["price"], (int, float))

    def test_resistance_lines_structure(self, client):
        lines = client.get("/api/stocks/2330/analysis").json()["resistance_lines"]
        assert len(lines) >= 1
        for line in lines:
            assert "label" in line
            assert "price" in line
            assert line["type"] in ("static", "dynamic")

    def test_trend_line_structure(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        for key in ("uptrend_line", "downtrend_line"):
            tl = body[key]
            assert "valid" in tl
            assert "note" in tl
            assert isinstance(tl["valid"], bool)
            if tl["valid"]:
                assert "p1" in tl and "p2" in tl
                assert tl["p1"]["date"] and tl["p1"]["price"] > 0
                assert tl["p2"]["date"] and tl["p2"]["price"] > 0

    def test_signal_is_7state(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        valid = {
            "entry_confirmed", "ready_to_enter", "watchlist", "hold",
            "take_profit_warning", "exit_warning", "invalidated", "DATA_MISSING",
        }
        assert body["signal"] in valid, f"signal={body['signal']} 不在 7 狀態集合"

    def test_score_in_range(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        assert 0 <= body["score"] <= 100

    def test_professional_scores_in_range(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        for field in ("trend_score", "entry_score", "risk_score"):
            assert 0 <= body[field] <= 100

    def test_stage_value_is_valid(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        assert body["stage"] in {"stage_1", "stage_2", "stage_3", "stage_4", "unknown"}

    def test_reasons_is_nonempty_list(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        assert isinstance(body["reasons"], list)
        assert len(body["reasons"]) > 0

    def test_risk_notes_is_list(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        assert isinstance(body["risk_notes"], list)

    def test_unknown_code_returns_data_not_ok(self, client):
        """不在 OHLCV 的代碼應回 200 + data_ok=False，不拋 500。"""
        resp = client.get("/api/stocks/9999/analysis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_ok"] is False
        assert body["data_missing_reason"] != ""
        assert body["signal"] == "DATA_MISSING"
        assert body["support_lines"] == []
        assert body["resistance_lines"] == []
        assert body["uptrend_line"]["valid"] is False
        assert body["downtrend_line"]["valid"] is False
        diagnostic = body["data_diagnostic"]
        assert diagnostic["status"] in {"not_tracked", "no_ohlcv_data", "insufficient_rows"}
        assert diagnostic["row_count"] == 0
        assert diagnostic["required_rows"] == 60
        assert diagnostic["last_data_as_of"] == body["as_of"]
        assert "python3 scripts/daily_update.py --months 12" in diagnostic["next_action_command"]
        assert diagnostic["next_action_copy_command"].endswith(
            "backend\npython3 scripts/daily_update.py --months 12"
        )

    def test_as_of_query_param(self, client):
        resp = client.get("/api/stocks/2330/analysis?as_of=2025-12-31")
        assert resp.status_code == 200
        assert resp.json()["as_of"] == "2025-12-31"

    def test_pattern_structure(self, client):
        """pattern 物件欄位結構正確，值在合法集合內。"""
        body   = client.get("/api/stocks/2330/analysis").json()
        pat    = body["pattern"]
        valid_types   = {"none", "w_bottom", "m_top", "head_and_shoulders_bottom"}
        valid_statuses = {"none", "forming", "confirmed", "failed"}
        assert "pattern_type"   in pat
        assert "pattern_status" in pat
        assert "neckline"       in pat
        assert "note"           in pat
        assert pat["pattern_type"]   in valid_types,   f"非法 pattern_type: {pat['pattern_type']}"
        assert pat["pattern_status"] in valid_statuses, f"非法 pattern_status: {pat['pattern_status']}"
        assert isinstance(pat["note"], str)
        if pat["pattern_type"] == "none":
            assert pat["neckline"] is None
        else:
            assert isinstance(pat["neckline"], (int, float))

    def test_unknown_code_pattern_is_none(self, client):
        """資料不足時 pattern_type 應為 none。"""
        body = client.get("/api/stocks/9999/analysis").json()
        assert body["pattern"]["pattern_type"] == "none"
        assert body["pattern"]["pattern_status"] == "none"

    def test_existing_routes_unaffected(self, client):
        """確認新 endpoint 不破壞 /api/stocks/recommendations。"""
        resp = client.get("/api/stocks/recommendations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_intraday_monitor_schema(self, client):
        """盤中監控 endpoint 回傳健康/警戒/風險，不污染正式 signal。"""
        resp = client.get("/api/stocks/2330/intraday-monitor")
        assert resp.status_code == 200
        body = resp.json()
        required = (
            "stock_id", "name", "mode", "latest_closed_date", "data_ok",
            "current_price", "baseline_close", "ma5", "ma10", "ma20", "ma60",
            "support_state", "ma_break_count", "previous_high_risk",
            "volume_low_price", "gap_type", "monitor_signal",
            "invalidates_daily_plan", "action", "warnings", "notes",
            "official_signal_note",
        )
        for f in required:
            assert f in body, f"欄位缺失: {f}"
        assert body["mode"] == "intraday_monitor"
        assert body["monitor_signal"] in {"healthy", "caution", "risk", "data_missing"}
        assert "不產生正式買賣訊號" in body["official_signal_note"]

    def test_intraday_monitor_low_price_invalidates_daily_plan(self, client):
        """盤中若價格極端跌破 5/10/20/60，應標示為風險監控，而不是正式 SELL。"""
        resp = client.get("/api/stocks/2330/intraday-monitor?price=1&low=1&high=1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["monitor_signal"] == "risk"
        assert body["previous_high_risk"] is True
        assert body["invalidates_daily_plan"] is True

    def test_daily_checklist_schema(self, client):
        body = client.get("/api/stocks/2330/analysis").json()
        checklist = body["daily_checklist"]
        assert isinstance(checklist, list)
        assert {"market", "setup", "risk", "action"}.issubset(
            {item["category"] for item in checklist}
        )
        for item in checklist:
            assert item["status"] in {"pass", "warn", "fail", "info"}
            assert item["label"]
            assert item["detail"]


# ---------------------------------------------------------------------------
# 服務層單元測試（固定測資，不依賴真實網路）
# ---------------------------------------------------------------------------

from app.services.analysis_service import (
    _build_resistance_lines,
    _build_support_lines,
    _build_downtrend_line,
    _build_uptrend_line,
    _find_swing_highs,
    _find_swing_lows,
)


class TestSwingDetection:

    def test_find_swing_lows_uptrend(self):
        """上升走勢中，每隔 5 根應有一個擺盪低點。"""
        rows = _make_rows(80, trend="up")
        swings = _find_swing_lows(rows, window=3)
        assert len(swings) >= 1
        for s in swings:
            assert "date" in s and "price" in s
            assert isinstance(s["price"], float)

    def test_find_swing_highs_downtrend(self):
        """下降走勢中能偵測到擺盪高點。"""
        rows = _make_rows(80, trend="down")
        swings = _find_swing_highs(rows, window=3)
        assert len(swings) >= 1

    def test_swing_lows_prices_are_local_minimums(self):
        """每個偵測到的擺盪低點，其 price 應 ≤ 相鄰 window 根的 low。"""
        rows = _make_rows(80, trend="up")
        swings = _find_swing_lows(rows, window=3)
        lows = [r["low"] for r in rows]
        dates = [r["date"] for r in rows]
        for s in swings:
            idx = dates.index(s["date"])
            for j in range(1, 4):
                if idx - j >= 0:
                    assert s["price"] <= lows[idx - j] + 1e-9
                if idx + j < len(lows):
                    assert s["price"] <= lows[idx + j] + 1e-9

    def test_insufficient_rows_no_swing(self):
        """資料不足 window*2+1 時，擺盪點應為空。"""
        rows = _make_rows(5, trend="up")
        swings = _find_swing_lows(rows, window=5)
        assert swings == []


class TestTrendLines:

    def test_uptrend_line_valid_in_uptrend(self):
        """70 根上升走勢：應能找到有效上升趨勢線。"""
        rows = _make_rows(80, trend="up")
        result = _build_uptrend_line(rows, window=3)
        assert result.valid is True
        assert result.p1 is not None and result.p2 is not None
        assert result.p2.price > result.p1.price   # 低點遞增

    def test_downtrend_line_valid_in_downtrend(self):
        """70 根下降走勢：應能找到有效下降趨勢線。"""
        rows = _make_rows(80, trend="down")
        result = _build_downtrend_line(rows, window=3)
        assert result.valid is True
        assert result.p2.price < result.p1.price   # 高點遞減

    def test_uptrend_line_has_note(self):
        rows = _make_rows(80, trend="up")
        result = _build_uptrend_line(rows, window=3)
        assert result.note != ""


class TestSupportResistanceLines:

    def test_support_lines_present_with_enough_data(self):
        rows = _make_rows(80, trend="up")
        ma20 = round(sum(r["close"] for r in rows[-20:]) / 20, 2)
        ma60 = round(sum(r["close"] for r in rows[-60:]) / 60, 2)
        lines = _build_support_lines(rows, ma20, ma60)
        assert len(lines) >= 2      # 至少近20日支撐 + MA20

    def test_resistance_lines_present_with_enough_data(self):
        rows = _make_rows(80, trend="up")
        lines = _build_resistance_lines(rows, None, None)
        assert len(lines) >= 1

    def test_support_lines_empty_with_few_rows(self):
        rows = _make_rows(5, trend="up")
        lines = _build_support_lines(rows, None, None)
        # 不到21筆，近20日視窗應為空；ma20/ma60 為 None → 只有可能的近20日支撐
        # 主要確認不拋錯
        assert isinstance(lines, list)

    def test_support_line_types_valid(self):
        rows = _make_rows(80, trend="up")
        ma20 = 100.0
        ma60 = 95.0
        for line in _build_support_lines(rows, ma20, ma60):
            assert line.type in ("static", "dynamic")

    def test_resistance_price_gte_support_price(self):
        rows = _make_rows(80, trend="up")
        support = _build_support_lines(rows, None, None)
        resist  = _build_resistance_lines(rows, None, None)
        if support and resist:
            # 靜態壓力 ≥ 靜態支撐（基本合理性）
            static_sup = [l for l in support if l.type == "static"]
            static_res = [l for l in resist  if l.type == "static"]
            if static_sup and static_res:
                assert static_res[0].price >= static_sup[0].price


# ---------------------------------------------------------------------------
# 資料新鮮度測試（is_stale / stale_days）
# ---------------------------------------------------------------------------

from datetime import date as _date, timedelta as _td

from app.services.analysis_service import analyse_stock
import app.services.signals_service as _svc


def _csv_content(rows: list[dict]) -> str:
    """把 rows（list of dict）轉成 CSV 文字（帶 header）。"""
    import csv, io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["date", "code", "open", "high", "low", "close", "volume"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


class TestDataFreshness:

    def _make_ohlcv_with_last_date(self, last_date: str, n: int = 80) -> list[dict]:
        """產生 n 筆假 OHLCV，最後一筆日期為 last_date。"""
        rows = _make_rows(n, trend="up")
        # 重新指定日期：讓最後一筆落在 last_date
        end = _date.fromisoformat(last_date)
        # 倒推 n 個交易日
        dates = []
        d = end
        while len(dates) < n:
            if d.weekday() < 5:
                dates.append(d.isoformat())
            d -= _td(days=1)
        dates.reverse()
        for i, row in enumerate(rows):
            row["date"] = dates[i]
            row["code"] = "TEST"
        return rows

    def test_fresh_data_not_stale(self, tmp_path, monkeypatch):
        """最後一筆為最近交易日 → is_stale=False；週末執行時 stale_days 可大於 0。"""
        today = _date.today().isoformat()
        rows = self._make_ohlcv_with_last_date(today)

        csv_text = _csv_content(rows)
        csv_path = tmp_path / "ohlcv.csv"
        csv_path.write_text(csv_text, encoding="utf-8")

        monkeypatch.setattr(_svc, "OHLCV_PATH", csv_path)

        result = analyse_stock("TEST")
        expected_last_trading_date = rows[-1]["date"]
        assert result.as_of == expected_last_trading_date
        assert result.stale_days == (_date.today() - _date.fromisoformat(expected_last_trading_date)).days
        assert result.is_stale is False

    def test_stale_data_detected(self, tmp_path, monkeypatch):
        """最後一筆超過 5 天前 → is_stale=True, stale_days>5。"""
        stale_date = (_date.today() - _td(days=19)).isoformat()
        rows = self._make_ohlcv_with_last_date(stale_date)

        csv_text = _csv_content(rows)
        csv_path = tmp_path / "ohlcv.csv"
        csv_path.write_text(csv_text, encoding="utf-8")

        monkeypatch.setattr(_svc, "OHLCV_PATH", csv_path)

        result = analyse_stock("TEST")
        # stale_date 可能為週末，實際最後一筆是前一個交易日，故允許 >=19
        assert result.stale_days >= 19
        assert result.is_stale is True

    def test_stale_days_in_api_response(self, client):
        """API 回傳含 is_stale / stale_days 欄位，且型別正確。"""
        body = client.get("/api/stocks/2330/analysis").json()
        assert "is_stale" in body
        assert "stale_days" in body
        assert isinstance(body["is_stale"], bool)
        assert isinstance(body["stale_days"], int)
        assert body["stale_days"] >= 0

    def test_is_stale_consistent_with_trading_days(self, client):
        """is_stale 必須以交易日（週一～週五）判斷，與 count_missed_trading_days 一致。"""
        from datetime import date
        from app.utils import count_missed_trading_days
        body = client.get("/api/stocks/2330/analysis").json()
        as_of = body.get("as_of")
        if as_of:
            expected = count_missed_trading_days(date.fromisoformat(as_of)) > 0
            assert body["is_stale"] == expected

    def test_as_of_reflects_actual_data_date(self, client):
        """as_of 應回傳資料實際最後一筆日期（ohlcv.csv 的最新日），而非今日。"""
        import csv as _csv
        from pathlib import Path as _Path
        ohlcv_path = _Path(__file__).resolve().parent.parent / "data" / "ohlcv.csv"
        last_date_2330 = ""
        with ohlcv_path.open() as f:
            for row in _csv.DictReader(f):
                if row["code"] == "2330":
                    last_date_2330 = row["date"]
        body = client.get("/api/stocks/2330/analysis").json()
        assert body["as_of"] == last_date_2330
