"""
test_backfill_tpex.py — 驗證 TPEX 回補邏輯（不依賴真實網路）

測試重點：
  1. _parse_tpex_response: 新版 POST API 回應解析（tables[0].data / name）
  2. fetch_stock: TWSE 無資料時 fallback 至 TPEX
  3. fetch_stock: TWSE 有資料時直接使用（不觸碰 TPEX）
  4. fetch_stock: 兩者均無資料時回傳 UNKNOWN
  5. 成交量單位：張（lots）× 1000 = 股（shares），與 TWSE 一致
  6. fetch_stock: TWSE raise FetchError → fallback TPEX，不中斷
  7. fetch_stock: TWSE + TPEX 均 raise FetchError → skip month，不 raise
  8. fetch_stock: 單一月份失敗不影響其他月份
  9. _months_to_fetch: 預設排除當月；include_current_month=True 才包含
 10. fetch_stock: 預設不查當月；include_current_month=True 才查
 11. parse_args: --include-current-month flag
"""

import sys
from datetime import date
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "scripts"))

import backfill_ohlcv_twse as bf  # type: ignore[import]


# ---------------------------------------------------------------------------
# 新版 TPEX 回應 Sample
# ---------------------------------------------------------------------------

_SAMPLE_TPEX_PAYLOAD = {
    "stat": "ok",
    "code": "6125",
    "name": "廣運",
    "tables": [{
        "title": "個股日成交資訊",
        "date": "20240401",
        "fields": ["日 期", "成交張數", "成交仟元", "開盤", "最高", "最低", "收盤", "漲跌", "筆數"],
        "data": [
            ["113/04/01", "1,235", "186,540", "151.50", "153.00", "150.00", "152.00", "+1.00", "456"],
            ["113/04/02", "988",   "149,000", "152.00", "154.00", "151.00", "153.50", "+1.50", "321"],
        ],
        "totalCount": 2,
        "notes": [],
        "summary": [],
    }],
    "date": "20240401",
    "flagField": "張數",
}


# ---------------------------------------------------------------------------
# _parse_tpex_response
# ---------------------------------------------------------------------------

def test_parse_tpex_response_ok():
    rows, name = bf._parse_tpex_response("6125", _SAMPLE_TPEX_PAYLOAD)

    assert name == "廣運"
    assert len(rows) == 2

    r0 = rows[0]
    assert r0["date"]   == "2024-04-01"
    assert r0["code"]   == "6125"
    assert r0["open"]   == 151.50
    assert r0["high"]   == 153.00
    assert r0["low"]    == 150.00
    assert r0["close"]  == 152.00
    assert r0["volume"] == 1_235_000


def test_parse_tpex_response_second_row():
    rows, _ = bf._parse_tpex_response("6125", _SAMPLE_TPEX_PAYLOAD)
    r1 = rows[1]
    assert r1["date"]   == "2024-04-02"
    assert r1["close"]  == 153.50
    assert r1["volume"] == 988_000


def test_parse_tpex_response_suspended_skipped():
    """停牌（--）的列應被跳過。"""
    payload = {
        "stat": "ok",
        "name": "廣運",
        "tables": [{"data": [
            ["113/04/01", "0", "0", "--", "--", "--", "--", "0", "0"],
            ["113/04/02", "988", "149,000", "152.00", "154.00", "151.00", "153.50", "+1.50", "321"],
        ]}],
    }
    rows, _ = bf._parse_tpex_response("6125", payload)
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-04-02"


def test_parse_tpex_response_empty_data():
    """tables[0].data 為空列表時回傳空 rows。"""
    payload = {"stat": "ok", "name": "廣運", "tables": [{"data": [], "fields": []}]}
    rows, name = bf._parse_tpex_response("6125", payload)
    assert rows == []
    assert name == "廣運"


def test_parse_tpex_response_missing_tables():
    """tables 欄位不存在時回傳空 rows 且 name 為 None。"""
    rows, name = bf._parse_tpex_response("6125", {"stat": "ok"})
    assert rows == []
    assert name is None


def test_parse_tpex_response_short_record_skipped():
    """欄位不足的列應被跳過。"""
    payload = {"stat": "ok", "tables": [{"data": [["113/04/01", "1,000"]]}]}
    rows, _ = bf._parse_tpex_response("6125", payload)
    assert rows == []


def test_parse_tpex_response_stat_not_ok_returns_empty():
    """stat != ok 的 payload 由 fetch_tpex_month 過濾，parser 本身仍可處理（回傳空）。"""
    rows, name = bf._parse_tpex_response("6125", {"stat": "參數輸入錯誤"})
    assert rows == []
    assert name is None


def test_parse_tpex_response_volume_unit_lots_to_shares():
    """成交量應從張（lots）轉換為股（shares），× 1000。"""
    payload = {
        "stat": "ok",
        "name": "雙鴻",
        "tables": [{"data": [
            ["114/04/01", "3,184", "1,697,926", "535.00", "540.00", "527.00", "535.00", "5.00", "3,926"],
        ]}],
    }
    rows, name = bf._parse_tpex_response("3324", payload)
    assert len(rows) == 1
    assert rows[0]["volume"] == 3_184_000
    assert name == "雙鴻"


# ---------------------------------------------------------------------------
# fetch_stock fallback behaviour（mock 網路，不發真實請求）
# ---------------------------------------------------------------------------

_TWSE_ROW = {
    "date": "2024-04-01", "code": "2330",
    "open": 900.0, "high": 910.0, "low": 895.0, "close": 905.0, "volume": 5_000_000,
}
_TPEX_ROW = {
    "date": "2024-04-01", "code": "6125",
    "open": 151.5, "high": 153.0, "low": 150.0, "close": 152.0, "volume": 1_235_000,
}


def test_fetch_stock_uses_twse_when_available(monkeypatch):
    """TWSE 有資料 → 直接使用，不觸碰 TPEX。"""
    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: ([_TWSE_ROW], "台積電"))
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: (_ for _ in ()).throw(AssertionError("不應呼叫 TPEX")))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("2330", months_back=1)
    assert market == "TWSE"
    assert len(rows) == 1
    assert name == "台積電"


def test_fetch_stock_falls_back_to_tpex(monkeypatch):
    """TWSE 無資料（回傳 empty）→ fallback 至 TPEX。"""
    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: ([], None))
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([_TPEX_ROW], "廣運"))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("6125", months_back=1)
    assert market == "TPEX"
    assert len(rows) == 1
    assert name == "廣運"


def test_fetch_stock_unknown_when_both_empty(monkeypatch):
    """TWSE / TPEX 均無資料 → UNKNOWN，rows 為空。"""
    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: ([], None))
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([], None))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("9999", months_back=1)
    assert rows == []
    assert market == "UNKNOWN"
    assert name is None


def test_retry_skipped_stocks_recovers_transient_empty_twse(monkeypatch):
    """第一輪 skipped 的代碼應在同次流程重試；重試成功後不可留在 skipped。"""
    calls: list[str] = []

    def mock_fetch_stock(code, months_back, include_current_month=False):
        calls.append(code)
        if code == "2412":
            return ([{**_TWSE_ROW, "code": "2412"}], "TWSE", "中華電")
        return ([], "UNKNOWN", None)

    monkeypatch.setattr(bf, "fetch_stock", mock_fetch_stock)
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    result = bf.retry_skipped_stocks(["2412", "9999"], months_back=1, include_current_month=True)

    assert calls == ["2412", "9999"]
    assert result["skipped"] == ["9999"]
    assert result["rows"] == [{**_TWSE_ROW, "code": "2412"}]
    assert result["names"] == {"2412": "中華電"}
    assert result["markets"] == {"2412": "TWSE"}
    assert result["twse_count"] == 1
    assert result["tpex_count"] == 0


def test_fetch_stock_multi_month_aggregation(monkeypatch):
    """多個月份的 rows 應被合併回傳。"""
    call_count = {"n": 0}

    def mock_tpex(code, y, m):
        call_count["n"] += 1
        return ([{**_TPEX_ROW, "date": f"2024-0{call_count['n']}-01"}], "廣運")

    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: ([], None))
    monkeypatch.setattr(bf, "fetch_tpex_month", mock_tpex)
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("6125", months_back=3)
    assert market == "TPEX"
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# 新增測試：FetchError 容錯行為
# ---------------------------------------------------------------------------

def test_fetch_stock_twse_exception_fallback_to_tpex(monkeypatch):
    """TWSE raise FetchError（timeout/connection error）→ fallback TPEX，不中斷。"""
    def raise_fetch_error(code, y, m):
        raise bf.FetchError("The read operation timed out")

    monkeypatch.setattr(bf, "fetch_month",      raise_fetch_error)
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([_TPEX_ROW], "廣運"))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("3491", months_back=1)
    assert market == "TPEX"
    assert len(rows) == 1
    assert name == "廣運"


def test_fetch_stock_twse_exception_tpex_exception_no_raise(monkeypatch):
    """TWSE 與 TPEX 都 raise FetchError → rows 為空，不 raise，不中斷流程。"""
    def raise_error(code, y, m):
        raise bf.FetchError("network error")

    monkeypatch.setattr(bf, "fetch_month",      raise_error)
    monkeypatch.setattr(bf, "fetch_tpex_month", raise_error)
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("9999", months_back=1)
    assert rows == []
    assert market == "UNKNOWN"
    assert name is None


def test_fetch_stock_single_month_failure_no_interrupt(monkeypatch):
    """month 2 兩邊都 error，month 1 和 3 TWSE 成功 → 只回傳成功月份，不中斷。"""
    call_count = {"n": 0}

    def mock_twse(code, y, m):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise bf.FetchError("timeout")
        return ([{**_TWSE_ROW, "date": f"2024-0{call_count['n']}-01"}], "台積電")

    def mock_tpex(code, y, m):
        raise bf.FetchError("TPEX timeout")

    monkeypatch.setattr(bf, "fetch_month",      mock_twse)
    monkeypatch.setattr(bf, "fetch_tpex_month", mock_tpex)
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("2330", months_back=3)
    assert len(rows) == 2       # month 1 and 3 succeed; month 2 skipped
    assert market == "TWSE"
    assert name == "台積電"


def test_fetch_stock_partial_tpex_no_data_still_returns_rest(monkeypatch):
    """部分月份 TPEX 無資料（not error），其他月份正常 → 仍回傳成功月份。"""
    call_count = {"n": 0}

    def mock_tpex(code, y, m):
        call_count["n"] += 1
        if call_count["n"] == 2:
            return ([], None)   # month 2: no data
        return ([{**_TPEX_ROW, "date": f"2024-0{call_count['n']}-01"}], "廣運")

    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: ([], None))
    monkeypatch.setattr(bf, "fetch_tpex_month", mock_tpex)
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("6125", months_back=3)
    assert len(rows) == 2   # month 2 skipped; months 1 and 3 included
    assert market == "TPEX"
    assert name == "廣運"


def test_fetch_stock_twse_exception_tpex_empty_skip_month(monkeypatch):
    """TWSE error + TPEX empty（not error）→ skip month，不 raise。"""
    monkeypatch.setattr(bf, "fetch_month",      lambda code, y, m: (_ for _ in ()).throw(bf.FetchError("timeout")))
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([], None))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    rows, market, name = bf.fetch_stock("3491", months_back=1)
    assert rows == []
    assert market == "UNKNOWN"


# ---------------------------------------------------------------------------
# _months_to_fetch — 月份清單產生邏輯
# ---------------------------------------------------------------------------

def test_months_to_fetch_default_excludes_current_month():
    """預設 include_current_month=False → 不包含當月。"""
    today = date(2026, 5, 3)
    months = bf._months_to_fetch(3, include_current_month=False, today=today)
    assert months == [(2026, 4), (2026, 3), (2026, 2)]
    assert (2026, 5) not in months


def test_months_to_fetch_include_current_month():
    """include_current_month=True → 從當月開始。"""
    today = date(2026, 5, 3)
    months = bf._months_to_fetch(3, include_current_month=True, today=today)
    assert months == [(2026, 5), (2026, 4), (2026, 3)]


def test_months_to_fetch_year_boundary_default():
    """月份回溯跨年（1 月往前 → 上年 12 月）：預設排除當月。"""
    today = date(2026, 1, 15)
    months = bf._months_to_fetch(3, include_current_month=False, today=today)
    assert months == [(2025, 12), (2025, 11), (2025, 10)]


def test_months_to_fetch_year_boundary_include_current():
    """月份回溯跨年：include_current_month=True 從當月（1 月）開始。"""
    today = date(2026, 1, 15)
    months = bf._months_to_fetch(3, include_current_month=True, today=today)
    assert months == [(2026, 1), (2025, 12), (2025, 11)]


def test_months_to_fetch_correct_count():
    """回傳筆數等於 months_back。"""
    today = date(2026, 5, 3)
    assert len(bf._months_to_fetch(12, today=today)) == 12
    assert len(bf._months_to_fetch(1,  today=today)) == 1


# ---------------------------------------------------------------------------
# fetch_stock — 月份查詢範圍驗證
# ---------------------------------------------------------------------------

def test_fetch_stock_default_excludes_current_month(monkeypatch):
    """預設 include_current_month=False：今天 2026-05-03, months_back=3 → 不查 2026/05。"""
    queried: list[tuple[int, int]] = []

    def mock_twse(code, y, m):
        queried.append((y, m))
        return ([], None)

    monkeypatch.setattr(bf, "fetch_month",      mock_twse)
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([], None))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    bf.fetch_stock("3491", months_back=3, _today=date(2026, 5, 3))

    assert (2026, 5) not in queried
    assert (2026, 4) in queried
    assert (2026, 3) in queried
    assert (2026, 2) in queried


def test_fetch_stock_include_current_month_queries_current(monkeypatch):
    """include_current_month=True：今天 2026-05-03, months_back=3 → 查 2026/05。"""
    queried: list[tuple[int, int]] = []

    def mock_twse(code, y, m):
        queried.append((y, m))
        return ([], None)

    monkeypatch.setattr(bf, "fetch_month",      mock_twse)
    monkeypatch.setattr(bf, "fetch_tpex_month", lambda code, y, m: ([], None))
    monkeypatch.setattr(bf.time, "sleep", lambda _: None)

    bf.fetch_stock("3491", months_back=3, include_current_month=True, _today=date(2026, 5, 3))

    assert (2026, 5) in queried
    assert (2026, 4) in queried
    assert (2026, 3) in queried


# ---------------------------------------------------------------------------
# parse_args — CLI flag
# ---------------------------------------------------------------------------

def test_parse_args_default_excludes_current_month(monkeypatch):
    """CLI 不帶 --include-current-month → include_current_month=False。"""
    monkeypatch.setattr(sys, "argv", ["backfill", "--months", "3"])
    args = bf.parse_args()
    assert args.include_current_month is False


def test_parse_args_with_include_current_month(monkeypatch):
    """CLI 帶 --include-current-month → include_current_month=True。"""
    monkeypatch.setattr(sys, "argv", ["backfill", "--months", "3", "--include-current-month"])
    args = bf.parse_args()
    assert args.include_current_month is True
