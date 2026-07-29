from app.models.trade import TradeRecord, TradeUpdateRequest
from app.services import trade_integrity_service as integrity
from app.services import trade_service


def _trade(**overrides) -> TradeRecord:
    values = {
        "id": "t1",
        "stock_id": "2330",
        "name": "台積電",
        "trade_type": "buy",
        "date": "2026-07-23",
        "price": 1000.0,
        "shares": 100,
        "gross_amount": 100000.0,
        "fee": 50.0,
        "tax": 0.0,
        "net_amount": 100050.0,
        "note": "",
        "created_at": "2026-07-23T10:00:00",
    }
    values.update(overrides)
    return TradeRecord(**values)


def test_integrity_report_marks_out_of_range_trade_provisional():
    result = integrity.build_trade_integrity_report(
        [_trade(price=1200)],
        {"2330": [{"date": "2026-07-23", "low": 980, "high": 1020, "close": 1005}]},
    )

    assert result["performance_status"] == "provisional"
    assert result["warning_count"] == 1
    assert result["items"][0]["status"] == "warning"
    assert result["items"][0]["difference_pct"] > 0


def test_integrity_report_marks_in_range_trade_verified():
    result = integrity.build_trade_integrity_report(
        [_trade(price=1000)],
        {"2330": [{"date": "2026-07-23", "low": 980, "high": 1020, "close": 1005}]},
    )

    assert result["performance_status"] == "verified"
    assert result["warning_count"] == 0
    assert result["items"][0]["status"] == "ok"


def test_update_trade_backs_up_recalculates_and_saves(monkeypatch):
    saved = {}
    original = _trade()
    monkeypatch.setattr(trade_service, "load_trades", lambda: [original])
    monkeypatch.setattr(trade_service, "backup_trades", lambda: saved.setdefault("backup", True))
    monkeypatch.setattr(trade_service, "save_trades", lambda trades: saved.setdefault("trades", trades))
    monkeypatch.setattr(
        trade_service,
        "calculate_trade_amounts",
        lambda *_args: {"gross_amount": 99000.0, "fee": 40.0, "tax": 0.0, "net_amount": 99040.0},
    )

    result = trade_service.update_trade_record(
        "t1",
        TradeUpdateRequest(date="2026-07-22", price=990, shares=100, note="已核對"),
    )

    assert saved["backup"] is True
    assert saved["trades"][0].price == 990
    assert result.date == "2026-07-22"
    assert result.net_amount == 99040.0


def test_update_trade_rejects_missing_id(monkeypatch):
    monkeypatch.setattr(trade_service, "load_trades", lambda: [])

    try:
        trade_service.update_trade_record(
            "missing",
            TradeUpdateRequest(date="2026-07-22", price=990, shares=100),
        )
    except KeyError:
        pass
    else:
        raise AssertionError("missing trade must raise KeyError")


def test_trade_update_api_maps_not_found(client, monkeypatch):
    from app.routers import trades as router

    monkeypatch.setattr(router, "update_trade_record", lambda *_args: (_ for _ in ()).throw(KeyError("x")))
    response = client.patch(
        "/api/trades/missing",
        json={"date": "2026-07-22", "price": 990, "shares": 100, "note": ""},
    )

    assert response.status_code == 404
