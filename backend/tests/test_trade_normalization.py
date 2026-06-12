from app.models.trade import TradeRecord
from app.services.trade_service import (
    calculate_positions,
    calculate_stats,
    calculate_trade_amounts,
    normalize_trade_names,
)


def _trade(stock_id: str, name: str) -> TradeRecord:
    return TradeRecord(
        id=f"t-{stock_id}",
        stock_id=stock_id,
        name=name,
        trade_type="buy",
        date="2026-05-01",
        price=100.0,
        shares=1000,
        note="",
        created_at="2026-05-01T00:00:00",
    )


def test_normalize_trade_names_uses_stock_names_map():
    trades = [_trade("2337", "2337"), _trade("2303", "聯電")]

    normalized, changed = normalize_trade_names(
        trades,
        {"2337": "旺宏", "2303": "聯電"},
    )

    assert changed == 1
    assert normalized[0].name == "旺宏"
    assert normalized[1].name == "聯電"


def test_calculate_trade_amounts_buy_adds_brokerage_fee_to_cost():
    amounts = calculate_trade_amounts("buy", price=100.0, shares=1000)

    assert amounts["gross_amount"] == 100000
    assert amounts["fee"] == 142
    assert amounts["tax"] == 0
    assert amounts["net_amount"] == 100142


def test_calculate_trade_amounts_sell_deducts_fee_and_transaction_tax():
    amounts = calculate_trade_amounts("sell", price=100.0, shares=1000)

    assert amounts["gross_amount"] == 100000
    assert amounts["fee"] == 142
    assert amounts["tax"] == 300
    assert amounts["net_amount"] == 99558


def test_calculate_trade_amounts_applies_brokerage_discount_and_min_fee(monkeypatch):
    import app.services.trade_service as ts

    monkeypatch.setattr(ts, "load_trading_settings", lambda: {
        "brokerage_fee_rate": 0.001425,
        "brokerage_discount": 0.28,
        "min_brokerage_fee": 20,
        "sell_transaction_tax_rate": 0.003,
    })

    small = calculate_trade_amounts("buy", price=10.0, shares=1000)
    large = calculate_trade_amounts("sell", price=100.0, shares=1000)

    assert small["fee"] == 20
    assert small["net_amount"] == 10020
    assert large["fee"] == 40
    assert large["tax"] == 300
    assert large["net_amount"] == 99660


def test_calculate_positions_avg_cost_includes_buy_fee(monkeypatch):
    import app.services.trade_service as ts

    trades = [
        TradeRecord(
            id="t1",
            stock_id="2330",
            name="台積電",
            trade_type="buy",
            date="2026-05-01",
            price=100.0,
            shares=1000,
            note="",
            created_at="2026-05-01T00:00:00",
        )
    ]
    monkeypatch.setattr(ts, "get_all_current_prices", lambda: {"2330": 110.0})
    monkeypatch.setattr(ts, "load_stock_names", lambda: {"2330": "台積電"})

    pos = calculate_positions(trades)[0]

    assert pos.avg_cost == 100.14
    assert pos.total_cost == 100142


def test_calculate_stats_realized_pnl_uses_net_sell_amount():
    trades = [
        TradeRecord(
            id="b1",
            stock_id="2330",
            name="台積電",
            trade_type="buy",
            date="2026-05-01",
            price=100.0,
            shares=1000,
            note="",
            created_at="2026-05-01T00:00:00",
        ),
        TradeRecord(
            id="s1",
            stock_id="2330",
            name="台積電",
            trade_type="sell",
            date="2026-05-02",
            price=110.0,
            shares=1000,
            note="",
            created_at="2026-05-02T00:00:00",
        ),
    ]

    stats = calculate_stats(trades, "all")

    assert stats.realized_pnl == 9371
