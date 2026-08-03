import csv

import pytest

from app.storage import us_market_store as store
from app.storage.atomic_write import atomic_write_csv


def _row(code: str, date: str, close: str = "100") -> dict:
    return {"date": date, "code": code, "open": close, "high": close,
            "low": close, "close": close, "volume": "1000"}


@pytest.fixture
def _csv_path(tmp_path, monkeypatch):
    path = tmp_path / "ohlcv_us.csv"
    monkeypatch.setattr(store, "OHLCV_US_PATH", path)
    return path


def test_truncated_write_leftovers_do_not_survive_the_next_merge(_csv_path):
    """截斷寫入的殘值兩欄都非空，只檢查非空會把它當成真資料一路傳承下去。

    實際發生過：ohlcv_us.csv 第 2 行 code=143.4600067138672 / date=7138672
    活了數月，讓主資料載入器多出一個假 ticker。
    """
    _csv_path.write_text(
        "date,code,open,high,low,close,volume\n"
        "7138672,143.4600067138672,12812000,,,,\n"
        "2021-06-07,AAPL,126.16,126.31,124.83,125.90,71057600\n",
        encoding="utf-8",
    )

    total = store.merge_write_us_ohlcv([_row("MSFT", "2026-07-31")])

    codes = {r["code"] for r in csv.DictReader(_csv_path.open(encoding="utf-8"))}
    assert codes == {"AAPL", "MSFT"}
    assert total == 2


@pytest.mark.parametrize("code,date", [
    ("143.4600067138672", "7138672"),   # 截斷殘值
    ("", "2026-07-31"),                 # 缺代號
    ("AAPL", ""),                       # 缺日期
    ("AAPL", "20260731"),               # 日期格式錯
    ("1234", "2026-07-31"),             # 代號不以字母開頭
])
def test_malformed_keys_are_rejected(code, date):
    assert store._valid_key((code, date)) is False


@pytest.mark.parametrize("code", ["AAPL", "BRK.B", "RDS-A", "SPCX"])
def test_real_tickers_still_pass(code):
    assert store._valid_key((code, "2026-07-31")) is True


def test_incoming_rows_are_validated_too(_csv_path):
    total = store.merge_write_us_ohlcv([
        _row("AAPL", "2026-07-31"),
        _row("143.46", "7138672"),
    ])

    assert total == 1


def test_atomic_csv_leaves_no_partial_file_behind(tmp_path):
    path = tmp_path / "out.csv"
    atomic_write_csv(path, ["a", "b"], [{"a": "1", "b": "2"}])

    assert path.read_text(encoding="utf-8").splitlines()[0] == "a,b"
    # 暫存檔必須已被 replace 掉，不能留在資料夾裡被誤讀
    assert list(tmp_path.glob(".*.tmp")) == []


def test_atomic_csv_keeps_the_old_file_when_writing_fails(tmp_path):
    path = tmp_path / "out.csv"
    atomic_write_csv(path, ["a"], [{"a": "first"}])

    class Boom(dict):
        def get(self, *_args, **_kwargs):
            raise RuntimeError("寫到一半炸了")

    with pytest.raises(RuntimeError):
        atomic_write_csv(path, ["a"], [Boom()])

    # 舊檔必須完好；open("w") 的作法會在這裡留下一個被清空的檔
    assert "first" in path.read_text(encoding="utf-8")
