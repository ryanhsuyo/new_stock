"""
test_universe_report.py — 候選股篩選報告 API 測試

覆蓋：
  get_universe_report_json():
    - 檔案存在時正確解析並回傳 list[dict]
    - bool / int / float 欄位正確轉型；空值 → None
    - 檔案不存在時回傳 None
    - 每筆補充 market / exchange 欄位
    - market 來自 stock_markets.json（精確）
    - stock_markets.json 無此 code 時 heuristic fallback
    - ETF 代號 → market=ETF
    - TPEX 代號（3491, 6274）→ market=TPEX
    - 一般上市（2330）→ market=TWSE
    - 例外 TWSE（3711, 5880）→ market=TWSE（stock_markets.json 正確）

  GET /api/stocks/signals/universe-report:
    - 404 / 200 / 欄位齊 / bool 型別
    - market / exchange 欄位存在且正確
"""

import csv
import json
from pathlib import Path

import pytest

import app.services.signals_service as svc
import app.storage.market_store as ms


# ---------------------------------------------------------------------------
# 固定測資
# ---------------------------------------------------------------------------

_CSV_HEADER = [
    "code", "name", "data_ok", "data_missing",
    "signal", "internal_signal", "entry_type", "score",
    "long_trend", "short_trend",
    "support_price", "resistance_price",
    "support_source", "resistance_source",
    "entry_source", "stop_source", "target_source",
    "pattern_type", "pattern_status",
    "no_buy_reason", "risk_note",
    "close", "ma5", "ma20", "ma60", "rsi14", "vol_ratio",
    "reasons",
    "daily_action", "daily_action_label", "daily_action_identity",
    "daily_action_reason", "daily_key_price", "daily_invalidation",
    "daily_priority",
]

_SAMPLE_ROWS = [
    {
        "code": "2330", "name": "台積電",
        "data_ok": "True", "data_missing": "False",
        "signal": "HOLD", "internal_signal": "hold", "entry_type": "",
        "score": "70",
        "long_trend": "up", "short_trend": "up",
        "support_price": "1760.0", "resistance_price": "2330.0",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "", "stop_source": "MA20", "target_source": "resistance_price",
        "pattern_type": "m_top", "pattern_status": "forming",
        "no_buy_reason": "持股中，長線趨勢穩定，可續抱",
        "risk_note": "M頂形成中（頸線 1760.0，注意跌破）",
        "close": "2135.0", "ma5": "2196.0", "ma20": "2042.75", "ma60": "1913.83",
        "rsi14": "62.62", "vol_ratio": "1.35",
        "reasons": "長線趨勢偏多 | 短線趨勢偏多",
    },
    {
        "code": "3034", "name": "聯詠",
        "data_ok": "True", "data_missing": "False",
        "signal": "BUY", "internal_signal": "ready_to_enter", "entry_type": "pullback",
        "score": "100",
        "long_trend": "up", "short_trend": "up",
        "support_price": "379.0", "resistance_price": "438.0",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "MA20", "stop_source": "support_price", "target_source": "resistance_price",
        "pattern_type": "w_bottom", "pattern_status": "confirmed",
        "no_buy_reason": "", "risk_note": "—",
        "close": "409.0", "ma5": "412.9", "ma20": "405.07", "ma60": "388.97",
        "rsi14": "58.62", "vol_ratio": "0.63",
        "reasons": "長線趨勢偏多 | RSI 健康區間",
    },
    {
        "code": "9999", "name": "資料不足股",
        "data_ok": "False", "data_missing": "True",
        "signal": "DATA_MISSING", "internal_signal": "DATA_MISSING", "entry_type": "",
        "score": "",
        "long_trend": "", "short_trend": "",
        "support_price": "", "resistance_price": "",
        "support_source": "", "resistance_source": "",
        "entry_source": "", "stop_source": "", "target_source": "",
        "pattern_type": "none", "pattern_status": "none",
        "no_buy_reason": "資料不足", "risk_note": "",
        "close": "", "ma5": "", "ma20": "", "ma60": "",
        "rsi14": "", "vol_ratio": "",
        "reasons": "",
    },
    # ETF
    {
        "code": "0050", "name": "元大台灣50",
        "data_ok": "True", "data_missing": "False",
        "signal": "HOLD", "internal_signal": "watchlist", "entry_type": "",
        "score": "80",
        "long_trend": "up", "short_trend": "up",
        "support_price": "85.0", "resistance_price": "95.0",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "MA20", "stop_source": "MA60", "target_source": "resistance_price",
        "pattern_type": "none", "pattern_status": "none",
        "no_buy_reason": "", "risk_note": "",
        "close": "90.5", "ma5": "91.0", "ma20": "88.0", "ma60": "85.0",
        "rsi14": "62.0", "vol_ratio": "0.9",
        "reasons": "長線趨勢偏多",
    },
    # TPEX 上櫃
    {
        "code": "3491", "name": "昇達科",
        "data_ok": "True", "data_missing": "False",
        "signal": "HOLD", "internal_signal": "watchlist", "entry_type": "",
        "score": "60",
        "long_trend": "up", "short_trend": "down",
        "support_price": "1425.0", "resistance_price": "1895.0",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "support_price", "stop_source": "support_price", "target_source": "resistance_price",
        "pattern_type": "none", "pattern_status": "none",
        "no_buy_reason": "等待回測", "risk_note": "",
        "close": "1550.0", "ma5": "1580.0", "ma20": "1665.0", "ma60": "1461.0",
        "rsi14": "29.77", "vol_ratio": "0.56",
        "reasons": "長線趨勢偏多",
    },
    # 以 3 開頭但為 TWSE 的例外
    {
        "code": "3711", "name": "日月光投控",
        "data_ok": "True", "data_missing": "False",
        "signal": "HOLD", "internal_signal": "take_profit_warning", "entry_type": "",
        "score": "95",
        "long_trend": "up", "short_trend": "up",
        "support_price": "328.5", "resistance_price": "523.0",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "", "stop_source": "MA20", "target_source": "resistance_price",
        "pattern_type": "w_bottom", "pattern_status": "confirmed",
        "no_buy_reason": "RSI 過熱", "risk_note": "",
        "close": "478.0", "ma5": "490.0", "ma20": "436.0", "ma60": "369.0",
        "rsi14": "77.78", "vol_ratio": "1.59",
        "reasons": "長線偏多",
    },
    # 以 5 開頭但為 TWSE 的例外
    {
        "code": "5880", "name": "合庫金",
        "data_ok": "True", "data_missing": "False",
        "signal": "SELL", "internal_signal": "exit_warning", "entry_type": "",
        "score": "35",
        "long_trend": "down", "short_trend": "down",
        "support_price": "22.8", "resistance_price": "24.1",
        "support_source": "recent_20d_low", "resistance_source": "recent_20d_high",
        "entry_source": "", "stop_source": "", "target_source": "",
        "pattern_type": "none", "pattern_status": "none",
        "no_buy_reason": "長線偏空", "risk_note": "",
        "close": "22.95", "ma5": "22.99", "ma20": "23.55", "ma60": "23.51",
        "rsi14": "21.87", "vol_ratio": "1.06",
        "reasons": "長線偏空",
    },
]

# stock_markets.json 測資（精確市場資訊）
_SAMPLE_MARKETS = {
    "2330": "TWSE",
    "3034": "TPEX",
    "0050": "TWSE",
    "3491": "TPEX",
    "3711": "TWSE",   # 以 3 開頭但 TWSE
    "5880": "TWSE",   # 以 5 開頭但 TWSE
}


def _write_sample_csv(out_dir: Path) -> Path:
    path = out_dir / "universe_report.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_HEADER)
        writer.writeheader()
        writer.writerows(_SAMPLE_ROWS)
    return path


@pytest.fixture()
def report_csv(tmp_out, monkeypatch):
    """
    建立臨時 universe_report.csv 與 stock_markets.json。
    tmp_out 已 monkeypatch svc._OUT；這裡再將 market_store 導向同一臨時目錄。
    """
    # 把 market_store 的路徑導向臨時目錄
    data_dir = tmp_out.parent / "data"
    data_dir.mkdir(exist_ok=True)
    markets_path = data_dir / "stock_markets.json"
    markets_path.write_text(
        json.dumps(_SAMPLE_MARKETS, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(ms, "MARKETS_PATH", markets_path)
    return _write_sample_csv(tmp_out)


@pytest.fixture()
def report_csv_no_markets(tmp_out, monkeypatch):
    """無 stock_markets.json（測試 heuristic fallback）。"""
    missing_path = tmp_out.parent / "nonexistent_markets.json"
    monkeypatch.setattr(ms, "MARKETS_PATH", missing_path)
    return _write_sample_csv(tmp_out)


# ---------------------------------------------------------------------------
# get_universe_report_json()
# ---------------------------------------------------------------------------

class TestGetUniverseReportJson:

    def test_returns_none_when_file_missing(self, tmp_out):
        result = svc.get_universe_report_json()
        assert result is None

    def test_returns_list_when_file_exists(self, report_csv):
        result = svc.get_universe_report_json()
        assert isinstance(result, list)
        assert len(result) == len(_SAMPLE_ROWS)

    def test_bool_true_converted(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["data_ok"] is True
        assert row["data_missing"] is False

    def test_bool_false_converted(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "9999")
        assert row["data_ok"] is False
        assert row["data_missing"] is True

    def test_score_is_int(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["score"] == 70
        assert isinstance(row["score"], int)

    def test_int_fields_accept_integer_like_float_strings(self, report_csv):
        """CSV writer may serialize integer percentages as 0.0; API still returns int."""
        path = Path(report_csv)
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
        fieldnames = list(rows[0].keys())
        if "fundamental_data_completeness_pct" not in fieldnames:
            fieldnames.append("fundamental_data_completeness_pct")
        rows[0]["fundamental_data_completeness_pct"] = "0.0"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        parsed = svc.get_universe_report_json()
        row = next(r for r in parsed if r["code"] == "2330")
        assert row["fundamental_data_completeness_pct"] == 0
        assert isinstance(row["fundamental_data_completeness_pct"], int)

    def test_float_fields_converted(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["close"] == 2135.0
        assert row["rsi14"] == 62.62
        assert row["vol_ratio"] == 1.35
        assert row["support_price"] == 1760.0

    def test_empty_numeric_fields_become_none(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "9999")
        assert row["score"] is None
        assert row["close"] is None
        assert row["rsi14"] is None
        assert row["support_price"] is None

    def test_string_fields_preserved(self, report_csv):
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "3034")
        assert row["name"] == "聯詠"
        assert row["internal_signal"] == "ready_to_enter"
        assert row["entry_type"] == "pullback"
        assert row["entry_source"] == "MA20"
        assert row["reasons"] == "長線趨勢偏多 | RSI 健康區間"


# ---------------------------------------------------------------------------
# GET /api/stocks/signals/universe-report
# ---------------------------------------------------------------------------

class TestUniverseReportEndpoint:

    def test_returns_404_when_file_missing(self, client, tmp_out):
        resp = client.get("/api/stocks/signals/universe-report")
        assert resp.status_code == 404

    def test_returns_200_with_list(self, client, report_csv):
        resp = client.get("/api/stocks/signals/universe-report")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == len(_SAMPLE_ROWS)

    def test_each_row_has_required_fields(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        required = (
            "code", "name", "data_ok", "data_missing",
            "signal", "internal_signal", "entry_type", "score",
            "close", "rsi14", "reasons", "no_buy_reason", "risk_note",
            "support_source", "resistance_source",
            "entry_source", "stop_source", "target_source",
        )
        for row in rows:
            for field in required:
                assert field in row, f"欄位缺失：{field}（code={row.get('code')}）"

    def test_bool_fields_are_json_bool(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        for row in rows:
            assert isinstance(row["data_ok"], bool), f"data_ok 應為 bool，code={row['code']}"
            assert isinstance(row["data_missing"], bool), f"data_missing 應為 bool，code={row['code']}"

    def test_numeric_fields_correct_type(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "2330")
        assert isinstance(row["score"], int)
        assert isinstance(row["close"], float)
        assert isinstance(row["rsi14"], float)

    def test_missing_data_numerics_are_null(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "9999")
        assert row["score"] is None
        assert row["close"] is None

    def test_existing_csv_download_still_works(self, client, report_csv):
        """既有 CSV 下載端點（underscore）不受影響。"""
        resp = client.get("/api/stocks/signals/universe_report")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_market_and_exchange_fields_present(self, client, report_csv):
        """每筆都要有 market 與 exchange 欄位。"""
        rows = client.get("/api/stocks/signals/universe-report").json()
        for row in rows:
            assert "market"   in row, f"market 欄位缺失，code={row.get('code')}"
            assert "exchange" in row, f"exchange 欄位缺失，code={row.get('code')}"

    def test_twse_stock_market(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["market"]   == "TWSE"
        assert row["exchange"] == "TWSE"

    def test_tpex_stock_market(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "3491")
        assert row["market"]   == "TPEX"
        assert row["exchange"] == "TPEX"

    def test_etf_market(self, client, report_csv):
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "0050")
        assert row["market"]   == "ETF"
        assert row["exchange"] == "TWSE"

    def test_exception_3711_twse(self, client, report_csv):
        """3711 日月光投控：代碼以 3 開頭，但 exchange=TWSE → market=TWSE。"""
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "3711")
        assert row["market"] == "TWSE"

    def test_exception_5880_twse(self, client, report_csv):
        """5880 合庫金：代碼以 5 開頭，但 exchange=TWSE → market=TWSE。"""
        rows = client.get("/api/stocks/signals/universe-report").json()
        row = next(r for r in rows if r["code"] == "5880")
        assert row["market"] == "TWSE"


# ---------------------------------------------------------------------------
# Market enrichment — 含 / 不含 stock_markets.json
# ---------------------------------------------------------------------------

class TestMarketEnrichment:

    def test_with_markets_json_twse(self, report_csv):
        """stock_markets.json 存在：2330 → market=TWSE。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["market"]   == "TWSE"
        assert row["exchange"] == "TWSE"

    def test_with_markets_json_tpex(self, report_csv):
        """stock_markets.json 存在：3491 → market=TPEX。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "3491")
        assert row["market"]   == "TPEX"
        assert row["exchange"] == "TPEX"

    def test_with_markets_json_etf(self, report_csv):
        """stock_markets.json 存在：0050 → market=ETF，exchange=TWSE。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "0050")
        assert row["market"]   == "ETF"
        assert row["exchange"] == "TWSE"

    def test_with_markets_json_exception_3711(self, report_csv):
        """stock_markets.json 正確標記 3711=TWSE，覆蓋 heuristic。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "3711")
        assert row["market"] == "TWSE"

    def test_without_markets_json_heuristic_1xxx(self, report_csv_no_markets):
        """無 stock_markets.json：1xxx / 2xxx heuristic → TWSE。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "2330")
        assert row["market"]   == "TWSE"
        assert row["exchange"] == ""

    def test_without_markets_json_heuristic_3xxx(self, report_csv_no_markets):
        """無 stock_markets.json：3034 heuristic → TPEX。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "3034")
        assert row["market"] == "TPEX"

    def test_without_markets_json_etf_still_etf(self, report_csv_no_markets):
        """無 stock_markets.json：0050 以代碼前綴判斷 → ETF（不依賴 markets.json）。"""
        rows = svc.get_universe_report_json()
        row = next(r for r in rows if r["code"] == "0050")
        assert row["market"] == "ETF"
