import json
import logging

import pytest
from app.models.trade import TradeRecord
import app.services.signals_service as svc


def _trade(*, trade_id: str, trade_type: str) -> TradeRecord:
    return TradeRecord(
        id=trade_id,
        stock_id="2330",
        name="台積電",
        trade_type=trade_type,
        date="2026-06-01",
        price=100.0,
        shares=1000,
        note="",
        created_at="2026-06-01T00:00:00",
    )


def _write_legacy_positions(path) -> None:
    path.write_text(
        json.dumps(
            {
                "cash": 10,
                "holdings": {
                    "2330": {"name": "台積電", "shares": 1000, "avg_cost": 90.0}
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_empty_trades_are_authoritative(tmp_path, monkeypatch):
    legacy = tmp_path / "positions.json"
    _write_legacy_positions(legacy)
    monkeypatch.setattr(svc, "load_trades", lambda: [])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {})
    monkeypatch.setattr(svc, "POSITIONS_PATH", legacy)

    result = svc._load_positions()

    assert result == {"cash": 0, "holdings": {}, "source": "trades"}


def test_fully_sold_trades_are_authoritative(tmp_path, monkeypatch):
    legacy = tmp_path / "positions.json"
    _write_legacy_positions(legacy)
    trades = [
        _trade(trade_id="buy-1", trade_type="buy"),
        _trade(trade_id="sell-1", trade_type="sell"),
    ]
    monkeypatch.setattr(svc, "load_trades", lambda: trades)
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電"})
    monkeypatch.setattr(svc, "POSITIONS_PATH", legacy)

    result = svc._load_positions()

    assert result == {"cash": 0, "holdings": {}, "source": "trades"}


def test_trade_failure_uses_legacy_positions(tmp_path, monkeypatch, caplog):
    legacy = tmp_path / "positions.json"
    _write_legacy_positions(legacy)
    monkeypatch.setattr(
        svc,
        "load_trades",
        lambda: (_ for _ in ()).throw(ValueError("invalid trades")),
    )
    monkeypatch.setattr(svc, "load_stock_names", lambda: {})
    monkeypatch.setattr(svc, "POSITIONS_PATH", legacy)

    with caplog.at_level(logging.WARNING):
        result = svc._load_positions()

    assert result["source"] == "positions"
    assert result["holdings"]["2330"]["shares"] == 1000
    assert "trades position calculation failed" in caplog.text


def test_trade_failure_without_legacy_positions_returns_none_source(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        svc,
        "load_trades",
        lambda: (_ for _ in ()).throw(ValueError("invalid trades")),
    )
    monkeypatch.setattr(svc, "load_stock_names", lambda: {})
    monkeypatch.setattr(svc, "POSITIONS_PATH", tmp_path / "missing.json")

    result = svc._load_positions()

    assert result == {"cash": 1_000_000, "holdings": {}, "source": "none"}


def test_invalid_legacy_json_remains_visible_after_trade_failure(
    tmp_path, monkeypatch, caplog
):
    legacy = tmp_path / "positions.json"
    legacy.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(
        svc,
        "load_trades",
        lambda: (_ for _ in ()).throw(ValueError("invalid trades")),
    )
    monkeypatch.setattr(svc, "load_stock_names", lambda: {})
    monkeypatch.setattr(svc, "POSITIONS_PATH", legacy)

    with caplog.at_level(logging.WARNING), pytest.raises(json.JSONDecodeError):
        svc._load_positions()

    assert "trades position calculation failed" in caplog.text
