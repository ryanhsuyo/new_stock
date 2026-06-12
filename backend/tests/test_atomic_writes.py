import csv
import json


def test_atomic_write_text_replaces_target_and_removes_temp(tmp_path):
    from app.storage.atomic_write import atomic_write_text

    path = tmp_path / "summary.json"

    atomic_write_text(path, '{"as_of": "2026-05-19"}')

    assert json.loads(path.read_text(encoding="utf-8"))["as_of"] == "2026-05-19"
    assert not (tmp_path / ".summary.json.tmp").exists()


def test_summary_write_leaves_valid_json_and_no_temp_file(tmp_out):
    import app.services.signals_service as svc

    path = svc._write_summary({"as_of": "2026-05-19", "signals": []})

    assert json.loads(path.read_text(encoding="utf-8"))["as_of"] == "2026-05-19"
    assert not (tmp_out / ".summary.json.tmp").exists()


def test_previous_summary_write_leaves_valid_json_and_no_temp_file(tmp_out):
    import app.services.signals_service as svc

    path = svc._write_previous_summary({"as_of": "2026-05-18", "signals": []})

    assert path is not None
    assert json.loads(path.read_text(encoding="utf-8"))["as_of"] == "2026-05-18"
    assert not (tmp_out / ".summary_previous.json.tmp").exists()


def test_universe_report_write_leaves_valid_csv_and_no_temp_file(tmp_out):
    import app.services.signals_service as svc

    sig = {field: "" for field in svc._REPORT_FIELDS}
    sig.update({
        "code": "2330",
        "name": "台積電",
        "data_ok": True,
        "daily_checklist": ["market", "risk"],
        "reasons": ["測試原因"],
    })

    path = svc._write_universe_report([sig])

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["code"] == "2330"
    assert rows[0]["daily_checklist"] == '["market", "risk"]'
    assert not (tmp_out / ".universe_report.csv.tmp").exists()


def test_daily_brief_write_leaves_valid_json_and_no_temp_file(tmp_out):
    from app.services.daily_brief_service import write_daily_brief

    path = write_daily_brief(
        {
            "as_of": "2026-05-19",
            "generated_at": "2026-05-19T15:00:00",
            "signals": [],
            "market_context": {},
        },
        tmp_out,
    )

    assert json.loads(path.read_text(encoding="utf-8"))["data_status"]["last_data_as_of"] == "2026-05-19"
    assert not (tmp_out / ".daily_brief.json.tmp").exists()


def test_update_status_write_leaves_valid_json_and_no_temp_file(tmp_out, monkeypatch):
    import app.storage.update_store as store

    monkeypatch.setattr(store, "_OUT", tmp_out)
    monkeypatch.setattr(store, "UPDATE_STATUS_PATH", tmp_out / "update_status.json")

    store.save_update_status({**store._EMPTY, "last_run_status": "success"})

    path = tmp_out / "update_status.json"
    assert json.loads(path.read_text(encoding="utf-8"))["last_run_status"] == "success"
    assert not (tmp_out / ".update_status.json.tmp").exists()


def test_save_trades_uses_atomic_writer(tmp_path, monkeypatch):
    import app.storage.json_store as store
    from app.models.trade import TradeRecord

    path = tmp_path / "trades.json"
    calls = []

    def fake_atomic_write(target, text, *, encoding="utf-8"):
        calls.append((target, text, encoding))
        target.write_text(text, encoding=encoding)

    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(store, "atomic_write_text", fake_atomic_write)

    store.save_trades([
        TradeRecord(
            id="t1",
            stock_id="2330",
            name="台積電",
            trade_type="buy",
            date="2026-05-19",
            price=1000,
            shares=1000,
            created_at="2026-05-19T09:00:00",
        )
    ])

    assert calls and calls[0][0] == path
    assert json.loads(path.read_text(encoding="utf-8"))[0]["stock_id"] == "2330"


def test_watchlist_save_uses_atomic_writer(tmp_path, monkeypatch):
    import app.storage.watchlist_store as store

    path = tmp_path / "watchlists.json"
    calls = []

    def fake_atomic_write(target, text, *, encoding="utf-8"):
        calls.append((target, text, encoding))
        target.write_text(text, encoding=encoding)

    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_WATCHLISTS_PATH", path)
    monkeypatch.setattr(store, "atomic_write_text", fake_atomic_write)

    store.create_group("科技股")

    assert calls and calls[0][0] == path
    assert json.loads(path.read_text(encoding="utf-8"))["groups"][0]["name"] == "科技股"
