"""
test_pattern_service.py — W底 / M頂 / 頭肩底型態辨識最小測試

測試策略：
  使用固定合成測資，不依賴真實 OHLCV 或網路。
  每個型態 × 每個狀態（forming / confirmed / failed）都有一個 case。
  none 路徑（資料不足 / 無配對）各一個 case。
"""

from datetime import date, timedelta

import pytest

from app.services.pattern_service import detect_pattern


# ---------------------------------------------------------------------------
# 合成測資工廠
# ---------------------------------------------------------------------------

def _rows(prices: list[float], start: str = "2025-01-02") -> list[dict]:
    """
    給定收盤價序列，產生對應 OHLCV rows（高 = close+1, 低 = close-1）。
    跳過週末。
    """
    rows = []
    d = date.fromisoformat(start)
    for i, close in enumerate(prices):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        close = round(close, 2)
        rows.append({
            "date": d.isoformat(),
            "open":   round(close - 0.5, 2),
            "high":   round(close + 1.0, 2),
            "low":    round(close - 1.0, 2),
            "close":  close,
            "volume": 1000 + i * 10,
        })
        d += timedelta(days=1)
    return rows


def _w_bottom_prices(end_close: float) -> list[float]:
    """
    合成 W 底走勢：
      第一段下跌 100→80（20 步），頸線高點約 96（第二段漲 80→96），
      第二段回落至 ~80.5（第三段跌 96→80.5），
      最後一段上漲至 end_close（第四段）。

    兩底約 80.0 / 80.5，差距 < 1%，頸線約 97（high = close+1 → 96+1）。
    """
    seg1 = [100 - i * 1.0  for i in range(21)]       # 100 → 80
    seg2 = [80  + i * 0.8  for i in range(21)]       # 80 → 96
    seg3 = [96  - i * 0.775 for i in range(21)]      # 96 → ~80.5
    seg4_start = seg3[-1]
    seg4 = [
        round(seg4_start + (end_close - seg4_start) * i / 20, 2)
        for i in range(21)
    ]
    return seg1 + seg2 + seg3 + seg4


def _w_bottom_prices_failed() -> list[float]:
    """
    合成 W 底「失效」走勢：第二底之後單調上漲（確保第二底被偵測為 swing low），
    隨後急跌至 74（低於兩底最低 × 0.97 = 77.6）。

    bounce 設計為持續上漲（無局部高點），避免被誤判為 M 頂。
    失效條件：74 < 80 × 0.97 = 77.6 ✓
    """
    seg1   = [100 - i * 1.0   for i in range(21)]    # 100 → 80
    seg2   = [80  + i * 0.8   for i in range(21)]    # 80 → 96
    seg3   = [96  - i * 0.775 for i in range(21)]    # 96 → ~80.5
    # 持續上漲 bounce（不產生局部高點）：確保 seg3 末尾的 80.5 是 swing low
    bounce = [80.5 + i * 0.6  for i in range(6)]     # 80.5 → 83.5（單調上漲）
    # 從最高點急跌至 74（單獨成段不產生 M 頂配對）
    top    = bounce[-1]
    crash  = [round(top - (top - 74) / 8 * i, 2) for i in range(9)]  # 83.5 → 74
    return seg1 + seg2 + seg3 + bounce + crash


def _m_top_prices(end_close: float) -> list[float]:
    """
    合成 M 頂走勢：
      第一段上漲 80→100，頸線低點約 84，
      第二段下跌 100→84，第三段回升至約 99.5，
      最後一段下跌至 end_close。
    """
    seg1 = [80  + i * 1.0  for i in range(21)]       # 80 → 100
    seg2 = [100 - i * 0.8  for i in range(21)]       # 100 → 84
    seg3 = [84  + i * 0.775 for i in range(21)]      # 84 → ~99.5
    seg4_start = seg3[-1]
    seg4 = [
        round(seg4_start + (end_close - seg4_start) * i / 20, 2)
        for i in range(21)
    ]
    return seg1 + seg2 + seg3 + seg4


def _m_top_prices_failed() -> list[float]:
    """
    合成 M 頂「失效」走勢：第二頂之後短暫回落（讓 swing 偵測到第二頂），
    隨後急漲至 107（高於兩頂最高 × 1.03）。
    失效條件：107 > 100 × 1.03 = 103 ✓
    """
    seg1 = [80  + i * 1.0  for i in range(21)]       # 80 → 100
    seg2 = [100 - i * 0.8  for i in range(21)]       # 100 → 84
    seg3 = [84  + i * 0.775 for i in range(21)]      # 84 → ~99.5
    bounce = [99.5, 99.0, 98.5, 98.0, 98.5]          # 短暫回落確保第二頂被偵測為 swing high
    surge  = [98 + (107 - 98) / 7 * i for i in range(8)]  # 急漲至 107
    return seg1 + seg2 + seg3 + bounce + surge


def _head_shoulders_bottom_prices(end_close: float) -> list[float]:
    """
    合成頭肩底走勢：
      左肩約 90，頭部約 80，右肩約 91，
      頸線高點約 104（high = close+1 → 103+1）。
    """
    seg1 = [110 - i * 1.0 for i in range(21)]       # 110 → 90（左肩）
    seg2 = [90 + i * 0.65 for i in range(21)]       # 90 → 103（左頸線）
    seg3 = [103 - i * 1.15 for i in range(21)]      # 103 → 80（頭）
    seg4 = [80 + i * 1.15 for i in range(21)]       # 80 → 103（右頸線）
    seg5 = [103 - i * 0.6 for i in range(21)]       # 103 → 91（右肩）
    start = seg5[-1]
    seg6 = [
        round(start + (end_close - start) * i / 20, 2)
        for i in range(21)
    ]
    return seg1 + seg2 + seg3 + seg4 + seg5 + seg6


def _head_shoulders_bottom_prices_failed() -> list[float]:
    """
    合成頭肩底「失效」走勢：右肩被偵測後跌破頭部低點 80 × 0.97 = 77.6。
    """
    base = _head_shoulders_bottom_prices(end_close=94.0)
    crash = [94 - (94 - 75) / 8 * i for i in range(9)]
    return base + crash


def _head_shoulders_top_prices(end_close: float) -> list[float]:
    """合成左肩約 100、頭部約 110、右肩約 99 的頭肩頂。"""
    seg1 = [80 + i * 1.0 for i in range(21)]
    seg2 = [100 - i * 0.65 for i in range(21)]
    seg3 = [87 + i * 1.15 for i in range(21)]
    seg4 = [110 - i * 1.15 for i in range(21)]
    seg5 = [87 + i * 0.6 for i in range(21)]
    start = seg5[-1]
    seg6 = [
        round(start + (end_close - start) * i / 20, 2)
        for i in range(21)
    ]
    return seg1 + seg2 + seg3 + seg4 + seg5 + seg6


def _head_shoulders_top_prices_failed() -> list[float]:
    base = _head_shoulders_top_prices(end_close=94.0)
    surge = [94 + (116 - 94) / 8 * i for i in range(9)]
    return base + surge


# ---------------------------------------------------------------------------
# W底測試
# ---------------------------------------------------------------------------

class TestWBottom:

    def test_w_bottom_forming(self):
        """第二底形成、尚未突破頸線 → forming。"""
        rows = _rows(_w_bottom_prices(end_close=88.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "w_bottom"
        assert result.pattern_status == "forming"
        assert result.neckline is not None
        assert result.neckline > 0
        assert "形成中" in result.note

    def test_w_bottom_confirmed(self):
        """收盤站上頸線 → confirmed。"""
        rows = _rows(_w_bottom_prices(end_close=100.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "w_bottom"
        assert result.pattern_status == "confirmed"
        assert "確認" in result.note

    def test_w_bottom_failed(self):
        """第二底形成後短暫反彈，隨後急跌破底 → failed。
        注意：若無短暫反彈，第二底不會被 swing 偵測到，pattern 會是 none。
        """
        rows = _rows(_w_bottom_prices_failed())
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "w_bottom"
        assert result.pattern_status == "failed"
        assert "失效" in result.note

    def test_w_bottom_neckline_positive(self):
        """頸線價格應為正數。"""
        rows = _rows(_w_bottom_prices(end_close=90.0))
        result = detect_pattern(rows, window=3)
        if result.pattern_type == "w_bottom":
            assert result.neckline > 0

    def test_w_bottom_note_nonempty(self):
        rows = _rows(_w_bottom_prices(end_close=90.0))
        result = detect_pattern(rows, window=3)
        assert result.note != ""


# ---------------------------------------------------------------------------
# M頂測試
# ---------------------------------------------------------------------------

class TestMTop:

    def test_m_top_forming(self):
        """第二頂形成、尚未跌破頸線 → forming。"""
        rows = _rows(_m_top_prices(end_close=91.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "m_top"
        assert result.pattern_status == "forming"
        assert result.neckline is not None
        assert "形成中" in result.note

    def test_m_top_confirmed(self):
        """收盤跌至頸線 → confirmed。"""
        rows = _rows(_m_top_prices(end_close=80.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "m_top"
        assert result.pattern_status == "confirmed"
        assert "確認" in result.note

    def test_m_top_failed(self):
        """第二頂形成後短暫回落，隨後急漲突破頂部 → failed。
        注意：若無短暫回落，第二頂不會被 swing 偵測到，pattern 會是 none。
        """
        rows = _rows(_m_top_prices_failed())
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "m_top"
        assert result.pattern_status == "failed"
        assert "失效" in result.note

    def test_m_top_note_nonempty(self):
        rows = _rows(_m_top_prices(end_close=91.0))
        result = detect_pattern(rows, window=3)
        assert result.note != ""


# ---------------------------------------------------------------------------
# 頭肩底測試
# ---------------------------------------------------------------------------

class TestHeadAndShouldersBottom:

    def test_head_shoulders_bottom_forming(self):
        rows = _rows(_head_shoulders_bottom_prices(end_close=96.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_bottom"
        assert result.pattern_status == "forming"
        assert result.neckline is not None
        assert "形成中" in result.note

    def test_head_shoulders_bottom_confirmed(self):
        rows = _rows(_head_shoulders_bottom_prices(end_close=106.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_bottom"
        assert result.pattern_status == "confirmed"
        assert "確認" in result.note

    def test_head_shoulders_bottom_failed(self):
        rows = _rows(_head_shoulders_bottom_prices_failed())
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_bottom"
        assert result.pattern_status == "failed"
        assert "失效" in result.note


# ---------------------------------------------------------------------------
# 頭肩頂測試
# ---------------------------------------------------------------------------

class TestHeadAndShouldersTop:

    def test_head_shoulders_top_forming(self):
        rows = _rows(_head_shoulders_top_prices(end_close=94.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_top"
        assert result.pattern_status == "forming"
        assert result.neckline is not None
        assert "形成中" in result.note

    def test_head_shoulders_top_confirmed(self):
        rows = _rows(_head_shoulders_top_prices(end_close=84.0))
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_top"
        assert result.pattern_status == "confirmed"
        assert "確認" in result.note

    def test_head_shoulders_top_failed(self):
        rows = _rows(_head_shoulders_top_prices_failed())
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "head_and_shoulders_top"
        assert result.pattern_status == "failed"
        assert "失效" in result.note

    def test_head_shoulders_top_rejects_mismatched_shoulders(self, monkeypatch):
        import app.services.pattern_service as svc

        rows = _rows([90.0] * 30)
        monkeypatch.setattr(svc, "_swing_highs", lambda rows, window: [
            {"date": rows[5]["date"], "price": 100.0},
            {"date": rows[15]["date"], "price": 115.0},
            {"date": rows[25]["date"], "price": 80.0},
        ])
        assert svc._detect_head_and_shoulders_top(rows, window=3) == {"found": False}

    def test_head_shoulders_top_rejects_shallow_head(self, monkeypatch):
        import app.services.pattern_service as svc

        rows = _rows([90.0] * 30)
        monkeypatch.setattr(svc, "_swing_highs", lambda rows, window: [
            {"date": rows[5]["date"], "price": 100.0},
            {"date": rows[15]["date"], "price": 102.0},
            {"date": rows[25]["date"], "price": 99.0},
        ])
        assert svc._detect_head_and_shoulders_top(rows, window=3) == {"found": False}


# ---------------------------------------------------------------------------
# None 路徑
# ---------------------------------------------------------------------------

class TestPatternNone:

    def test_insufficient_data_returns_none(self):
        """資料不足 20 筆 → none / none。"""
        rows = _rows([100.0] * 10)
        result = detect_pattern(rows, window=3)
        assert result.pattern_type == "none"
        assert result.pattern_status == "none"

    def test_flat_trend_no_pattern(self):
        """完全水平走勢（沒有明顯高低點配對）→ none 或 forming，不得是 confirmed。"""
        rows = _rows([100.0 + (i % 2) * 0.1 for i in range(80)])
        result = detect_pattern(rows, window=5)
        # 水平走勢不應偵測到已確認的型態
        assert result.pattern_status != "confirmed"

    def test_pattern_type_in_valid_set(self):
        """pattern_type 必須是合法值。"""
        valid = {
            "none", "w_bottom", "m_top",
            "head_and_shoulders_bottom", "head_and_shoulders_top",
        }
        rows = _rows([100.0 + (i % 3) * 0.5 for i in range(60)])
        result = detect_pattern(rows)
        assert result.pattern_type in valid

    def test_pattern_status_in_valid_set(self):
        """pattern_status 必須是合法值。"""
        valid = {"none", "forming", "confirmed", "failed"}
        rows = _rows([100.0 + (i % 3) * 0.5 for i in range(60)])
        result = detect_pattern(rows)
        assert result.pattern_status in valid

    def test_none_type_has_no_neckline(self):
        """pattern_type=none 時 neckline 應為 None。"""
        rows = _rows([100.0] * 10)
        result = detect_pattern(rows)
        assert result.neckline is None


# ---------------------------------------------------------------------------
# PatternResult 欄位完整性
# ---------------------------------------------------------------------------

class TestPatternResultSchema:

    def test_has_all_required_fields(self):
        rows = _rows(_w_bottom_prices(end_close=90.0))
        result = detect_pattern(rows, window=3)
        assert hasattr(result, "pattern_type")
        assert hasattr(result, "pattern_status")
        assert hasattr(result, "neckline")
        assert hasattr(result, "note")

    def test_neckline_is_float_when_pattern_found(self):
        rows = _rows(_w_bottom_prices(end_close=90.0))
        result = detect_pattern(rows, window=3)
        if result.pattern_type != "none":
            assert isinstance(result.neckline, float)
