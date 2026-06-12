"""
test_holdings.py — 持股分析服務最小測試

覆蓋：
  1. trades.json 為空 → 回傳 []
  2. 正常持股 → 回傳 HoldingAnalysis 列表，欄位齊全
  3. unrealized_pnl / return_rate 計算正確（正報酬 / 負報酬）
  4. 回傳依訊號嚴重程度排序（exit_warning 排前）
  5. signal 為合法 7 狀態之一
  6. analysis 嵌入 StockAnalysis schema

測試策略：
  - analyse_stock 以 monkeypatch 回傳固定 StockAnalysis，隔離 OHLCV 資料依賴
  - load_trades 以 monkeypatch 回傳固定 TradeRecord 列表
"""

import pytest

from app.models.analysis import HoldingAnalysis, PatternResult, StockAnalysis, TrendLine
from app.models.trade import TradeRecord
from app.services.holdings_service import analyse_holdings

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fake_analysis(
    code: str,
    signal: str = "hold",
    close: float = 100.0,
    data_ok: bool = True,
) -> StockAnalysis:
    trend_line = TrendLine(valid=False, p1=None, p2=None, note="")
    return StockAnalysis(
        code=code, stock_id=code, name=f"名稱{code}",
        as_of="2026-03-20",
        data_ok=data_ok,
        data_missing_reason="" if data_ok else "資料不足",
        close=close if data_ok else None,
        ma5=None, ma20=None, ma60=None, rsi14=None, vol_ratio=None,
        long_trend="up" if data_ok else "unknown",
        short_trend="neutral",
        signal=signal,
        score=60,
        reasons=["長線趨勢偏多"],
        risk_notes=[],
        no_buy_reason="持股中，長線趨勢穩定，可續抱" if signal == "hold" else "",
        support_lines=[], resistance_lines=[],
        uptrend_line=trend_line, downtrend_line=trend_line,
        pattern=PatternResult(
            pattern_type="none", pattern_status="none",
            neckline=None, note="未偵測到型態",
        ),
        ohlcv=[],
    )


def _make_trades(specs: list[dict]) -> list[TradeRecord]:
    """
    specs 格式：[{"code": "2330", "shares": 100, "price": 800.0, "type": "buy"}, ...]
    """
    trades = []
    for i, s in enumerate(specs):
        trades.append(TradeRecord(
            id=f"t{i}",
            stock_id=s["code"],
            name=s.get("name", f"名稱{s['code']}"),
            trade_type=s.get("type", "buy"),
            date="2026-01-01",
            price=s["price"],
            shares=s["shares"],
            note="",
            created_at="2026-01-01T00:00:00",
        ))
    return trades


# ---------------------------------------------------------------------------
# 邊界條件
# ---------------------------------------------------------------------------

class TestAnalyseHoldingsEdgeCases:

    def test_empty_trades_returns_empty(self, monkeypatch):
        import app.services.holdings_service as hs
        monkeypatch.setattr(hs, "load_trades", lambda: [])
        assert analyse_holdings() == []

    def test_all_sold_returns_empty(self, monkeypatch):
        """買進後全部賣出 → 回傳 []。"""
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 100, "price": 850.0, "type": "sell"},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        assert analyse_holdings() == []


# ---------------------------------------------------------------------------
# 正常流程
# ---------------------------------------------------------------------------

class TestAnalyseHoldingsNormal:

    def test_returns_holding_analysis_list(self, monkeypatch):
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code))

        results = analyse_holdings()
        assert len(results) == 1
        assert isinstance(results[0], HoldingAnalysis)

    def test_fields_complete(self, monkeypatch):
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code, close=850.0))

        h = analyse_holdings()[0]
        assert h.avg_cost == 801.14
        assert h.shares == 100
        assert h.unrealized_pnl is not None
        assert h.return_rate is not None
        assert h.analysis.code == "2330"

    def test_profit_calculation_positive(self, monkeypatch):
        """現價 > 均價 → 正報酬。"""
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 1000, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, close=850.0))

        h = analyse_holdings()[0]
        assert h.unrealized_pnl == 45099.0
        assert h.return_rate == 5.63

    def test_profit_calculation_negative(self, monkeypatch):
        """現價 < 均價 → 負報酬。"""
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 500, "price": 1000.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, close=900.0))

        h = analyse_holdings()[0]
        assert h.unrealized_pnl == -52701.0
        assert h.return_rate < 0

    def test_data_missing_pnl_is_none(self, monkeypatch):
        """資料不足時 unrealized_pnl / return_rate 為 None。"""
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, data_ok=False))

        h = analyse_holdings()[0]
        assert h.unrealized_pnl is None
        assert h.return_rate is None

    def test_multiple_holdings(self, monkeypatch):
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0},
            {"code": "2317", "shares": 1000, "price": 200.0},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code))

        results = analyse_holdings()
        assert len(results) == 2
        codes = {h.analysis.code for h in results}
        assert codes == {"2330", "2317"}

    def test_partial_sell_reduces_shares(self, monkeypatch):
        """部分賣出後持股數正確。"""
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 200, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 50,  "price": 850.0, "type": "sell"},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code))

        results = analyse_holdings()
        assert len(results) == 1
        assert results[0].shares == 150

    def test_weighted_avg_cost(self, monkeypatch):
        """多次買進 → 加權平均成本正確。"""
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 100, "price": 900.0, "type": "buy"},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code))

        h = analyse_holdings()[0]
        # avg = (80000+114 + 90000+128) / 200 = 851.21
        assert h.avg_cost == 851.21
        assert h.shares == 200


# ---------------------------------------------------------------------------
# 排序
# ---------------------------------------------------------------------------

class TestHoldingsSorting:

    def test_exit_warning_before_hold(self, monkeypatch):
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0},
            {"code": "2317", "shares": 1000, "price": 200.0},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)

        def fake(code, **kw):
            sig = "hold" if code == "2330" else "exit_warning"
            return _fake_analysis(code, signal=sig)

        monkeypatch.setattr(hs, "analyse_stock", fake)

        results = analyse_holdings()
        assert results[0].analysis.signal == "exit_warning"
        assert results[1].analysis.signal == "hold"

    def test_take_profit_warning_between_exit_and_hold(self, monkeypatch):
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "A", "shares": 100, "price": 100.0},
            {"code": "B", "shares": 100, "price": 100.0},
            {"code": "C", "shares": 100, "price": 100.0},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)

        signals = {"A": "hold", "B": "exit_warning", "C": "take_profit_warning"}
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, signal=signals[code]))

        order = [h.analysis.signal for h in analyse_holdings()]
        assert order.index("exit_warning") < order.index("take_profit_warning")
        assert order.index("take_profit_warning") < order.index("hold")


# ---------------------------------------------------------------------------
# signal 合法值
# ---------------------------------------------------------------------------

class TestSignalValidity:

    def test_signal_in_valid_set(self, monkeypatch):
        import app.services.holdings_service as hs
        valid = {
            "hold", "take_profit_warning", "exit_warning", "invalidated",
            "watchlist", "ready_to_enter", "entry_confirmed", "DATA_MISSING",
        }
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock", lambda code, **kw: _fake_analysis(code))

        for h in analyse_holdings():
            assert h.analysis.signal in valid


# ---------------------------------------------------------------------------
# API 整合
# ---------------------------------------------------------------------------

class TestPortfolioAnalysisApi:

    def _patch_empty_trades(self, monkeypatch):
        import app.services.holdings_service as hs
        monkeypatch.setattr(hs, "load_trades", lambda: [])

    def test_endpoint_returns_200(self, client, monkeypatch):
        self._patch_empty_trades(monkeypatch)
        resp = client.get("/api/portfolio/analysis")
        assert resp.status_code == 200

    def test_endpoint_returns_list(self, client, monkeypatch):
        self._patch_empty_trades(monkeypatch)
        body = client.get("/api/portfolio/analysis").json()
        assert isinstance(body, list)

    def test_endpoint_empty_trades_returns_empty(self, client, monkeypatch):
        self._patch_empty_trades(monkeypatch)
        body = client.get("/api/portfolio/analysis").json()
        assert body == []

    def test_holding_schema_fields(self, client, monkeypatch):
        """API 回傳的每筆 HoldingAnalysis 應含 avg_cost / shares / analysis。"""
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, close=850.0))

        items = client.get("/api/portfolio/analysis").json()
        assert len(items) > 0
        item = items[0]
        assert "avg_cost" in item
        assert "shares" in item
        assert "unrealized_pnl" in item
        assert "return_rate" in item
        assert "analysis" in item
        for field in ("code", "signal", "score", "reasons", "risk_notes", "pattern"):
            assert field in item["analysis"], f"analysis 缺欄位：{field}"
