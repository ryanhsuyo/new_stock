"""
test_portfolio_summary.py — 投組摘要最小測試

覆蓋：
  1. 空交易紀錄 → 全零摘要
  2. 單次買進 → 持股數、成本、市值正確
  3. 買進後全部賣出 → 持股歸零
  4. signal 統計計數正確（hold / exit_warning / take_profit_warning / invalidated）
  5. GET /api/portfolio/summary schema 正確
  6. GET /api/portfolio/positions schema 正確
  7. compute_raw_positions：多次買進加權平均、部分賣出、全部賣出

測試策略：
  - load_trades / analyse_stock 以 monkeypatch 替換，不依賴真實資料
"""

import pytest

from app.models.analysis import PatternResult, PortfolioSummary, StockAnalysis, TrendLine
from app.models.trade import TradeRecord
from app.services.holdings_service import compute_raw_positions, get_portfolio_summary


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_trades(specs: list[dict]) -> list[TradeRecord]:
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


def _fake_analysis(code: str, signal: str = "hold", close: float = 100.0) -> StockAnalysis:
    tl = TrendLine(valid=False, p1=None, p2=None, note="")
    return StockAnalysis(
        code=code, stock_id=code, name=f"名稱{code}",
        as_of="2026-03-20",
        data_ok=True,
        data_missing_reason="",
        close=close,
        ma5=None, ma20=None, ma60=None, rsi14=None, vol_ratio=None,
        long_trend="up", short_trend="neutral",
        signal=signal, score=60,
        reasons=[], risk_notes=[], no_buy_reason="",
        support_lines=[], resistance_lines=[],
        uptrend_line=tl, downtrend_line=tl,
        pattern=PatternResult(pattern_type="none", pattern_status="none", neckline=None, note=""),
        ohlcv=[],
    )


# ---------------------------------------------------------------------------
# compute_raw_positions 單元測試
# ---------------------------------------------------------------------------

class TestComputeRawPositions:

    def test_single_buy(self):
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        pos = compute_raw_positions(trades)
        assert "2330" in pos
        assert pos["2330"]["shares"] == 100
        assert pos["2330"]["avg_cost"] == 801.14

    def test_multi_buy_weighted_avg(self):
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0},
            {"code": "2330", "shares": 100, "price": 900.0},
        ])
        pos = compute_raw_positions(trades)
        assert pos["2330"]["shares"] == 200
        assert pos["2330"]["avg_cost"] == 851.21

    def test_partial_sell(self):
        trades = _make_trades([
            {"code": "2330", "shares": 200, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 50,  "price": 850.0, "type": "sell"},
        ])
        pos = compute_raw_positions(trades)
        assert pos["2330"]["shares"] == 150

    def test_full_sell_removes_position(self):
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 100, "price": 850.0, "type": "sell"},
        ])
        pos = compute_raw_positions(trades)
        assert "2330" not in pos

    def test_empty_trades(self):
        assert compute_raw_positions([]) == {}

    def test_multiple_stocks(self):
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0},
            {"code": "2317", "shares": 500, "price": 200.0},
        ])
        pos = compute_raw_positions(trades)
        assert set(pos.keys()) == {"2330", "2317"}


# ---------------------------------------------------------------------------
# get_portfolio_summary 單元測試
# ---------------------------------------------------------------------------

class TestGetPortfolioSummary:

    def test_empty_trades_returns_zero_summary(self, monkeypatch):
        import app.services.holdings_service as hs
        monkeypatch.setattr(hs, "load_trades", lambda: [])

        s = get_portfolio_summary()
        assert isinstance(s, PortfolioSummary)
        assert s.total_positions == 0
        assert s.total_cost == 0.0
        assert s.total_market_value == 0.0
        assert s.total_unrealized_pnl == 0.0
        assert s.hold_count == 0
        assert s.exit_warning_count == 0

    def test_single_holding_values(self, monkeypatch):
        """單筆持股：成本、市值、損益應正確。"""
        import app.services.holdings_service as hs
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, close=850.0))

        s = get_portfolio_summary()
        assert s.total_positions == 1
        assert s.total_cost == 80114.0
        assert s.total_market_value == 84624.0
        assert s.total_unrealized_pnl == 4510.0

    def test_signal_counts(self, monkeypatch):
        """各 signal 計數正確。"""
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "A", "shares": 100, "price": 100.0},
            {"code": "B", "shares": 100, "price": 100.0},
            {"code": "C", "shares": 100, "price": 100.0},
            {"code": "D", "shares": 100, "price": 100.0},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)

        sig_map = {"A": "hold", "B": "exit_warning",
                   "C": "take_profit_warning", "D": "invalidated"}
        monkeypatch.setattr(hs, "analyse_stock",
                            lambda code, **kw: _fake_analysis(code, signal=sig_map[code]))

        s = get_portfolio_summary()
        assert s.total_positions == 4
        assert s.hold_count == 1
        assert s.exit_warning_count == 1
        assert s.take_profit_warning_count == 1
        assert s.invalidated_count == 1

    def test_all_sold_zero_summary(self, monkeypatch):
        """全部賣出後摘要應為零持倉。"""
        import app.services.holdings_service as hs
        trades = _make_trades([
            {"code": "2330", "shares": 100, "price": 800.0, "type": "buy"},
            {"code": "2330", "shares": 100, "price": 850.0, "type": "sell"},
        ])
        monkeypatch.setattr(hs, "load_trades", lambda: trades)

        s = get_portfolio_summary()
        assert s.total_positions == 0
        assert s.total_cost == 0.0


# ---------------------------------------------------------------------------
# API 整合
# ---------------------------------------------------------------------------

class TestPortfolioSummaryApi:

    def test_summary_endpoint_200(self, client, monkeypatch):
        import app.services.holdings_service as hs
        monkeypatch.setattr(hs, "load_trades", lambda: [])
        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200

    def test_summary_schema_fields(self, client, monkeypatch):
        import app.services.holdings_service as hs
        monkeypatch.setattr(hs, "load_trades", lambda: [])
        body = client.get("/api/portfolio/summary").json()
        for field in (
            "total_positions", "total_cost", "total_market_value",
            "total_unrealized_pnl", "hold_count",
            "take_profit_warning_count", "exit_warning_count", "invalidated_count",
        ):
            assert field in body, f"summary 缺欄位：{field}"

    def test_positions_endpoint_200(self, client, monkeypatch):
        import app.services.holdings_service as hs
        import app.routers.portfolio as pr
        monkeypatch.setattr(pr, "load_trades", lambda: [])
        resp = client.get("/api/portfolio/positions")
        assert resp.status_code == 200

    def test_positions_schema_fields(self, client, monkeypatch):
        import app.services.holdings_service as hs
        import app.routers.portfolio as pr
        trades = _make_trades([{"code": "2330", "shares": 100, "price": 800.0}])
        monkeypatch.setattr(pr, "load_trades", lambda: trades)

        items = client.get("/api/portfolio/positions").json()
        assert len(items) == 1
        item = items[0]
        for field in ("stock_id", "name", "shares", "avg_cost"):
            assert field in item, f"positions 缺欄位：{field}"
