"""
test_signals_pattern.py — 批次訊號整合 pattern 最小測試

覆蓋：
  1. _compute_signal 回傳 pattern_type / pattern_status 欄位
  2. 欄位值為合法集合
  3. DATA_MISSING 時 pattern_type=none / pattern_status=none（不再是 n/a）
  4. W底 confirmed → score +20
  5. M頂 confirmed → score -20
  6. W底 forming → reasons 含型態說明
  7. M頂 forming → risk_note 含型態說明
  8. universe_report.csv 含 pattern_type / pattern_status 欄位
  9. universe_report.csv 不出現舊的 "n/a"

測試策略：
  - 欄位 / 值域測試用真實合成資料跑
  - score 增減測試用 monkeypatch 固定 detect_pattern 回傳，隔離型態偵測邏輯
  - 不依賴真實網路或 backend/data/ 真實檔案
"""

import csv
from datetime import date, timedelta

import pytest

from app.services.signals_service import _compute_signal, _write_universe_report


# ---------------------------------------------------------------------------
# 合成 OHLCV 資料
# ---------------------------------------------------------------------------

def _make_rows(prices: list[float], start: str = "2025-01-02") -> list[dict]:
    rows = []
    d = date.fromisoformat(start)
    for i, close in enumerate(prices):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        close = round(close, 2)
        rows.append({
            "date":   d.isoformat(),
            "open":   round(close - 0.5, 2),
            "high":   round(close + 1.0, 2),
            "low":    round(close - 1.0, 2),
            "close":  close,
            "volume": 10_000_000,
        })
        d += timedelta(days=1)
    return rows


def _flat_uptrend(n: int = 120) -> list[float]:
    """穩健緩漲走勢，不產生明確 W底 / M頂。"""
    return [100 + i * 0.1 for i in range(n)]


# ---------------------------------------------------------------------------
# 欄位完整性 / 值域
# ---------------------------------------------------------------------------

class TestPatternFields:

    def test_pattern_fields_exist(self):
        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        assert "pattern_type"   in sig
        assert "pattern_status" in sig

    def test_pattern_type_in_valid_set(self):
        valid = {
            "none", "w_bottom", "m_top",
            "head_and_shoulders_bottom", "head_and_shoulders_top",
        }
        rows  = _make_rows(_flat_uptrend())
        sig   = _compute_signal("2330", rows, {})
        assert sig["pattern_type"] in valid

    def test_pattern_status_in_valid_set(self):
        valid = {"none", "forming", "confirmed", "failed"}
        rows  = _make_rows(_flat_uptrend())
        sig   = _compute_signal("2330", rows, {})
        assert sig["pattern_status"] in valid

    def test_data_missing_returns_none_not_na(self):
        """資料不足時 pattern_status 應為 'none'，不再是舊的 'n/a'。"""
        rows = _make_rows([100.0] * 30)   # < MIN_ROWS=60
        sig  = _compute_signal("2330", rows, {})
        assert sig["pattern_type"]   == "none"
        assert sig["pattern_status"] == "none"
        assert sig["pattern_status"] != "n/a"


# ---------------------------------------------------------------------------
# 型態影響 score（monkeypatch 隔離型態偵測，確保 +/- 精確）
# ---------------------------------------------------------------------------

class TestPatternScoreEffect:

    def _base_score(self, rows, monkeypatch):
        """取得無型態時的 baseline score。"""
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="none", pattern_status="none", neckline=None, note="",
        ))
        return _compute_signal("2330", rows, {})["score"]

    def test_w_bottom_confirmed_adds_20(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="w_bottom", pattern_status="confirmed",
            neckline=105.0, note="W底確認",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == min(100, base + 20)

    def test_w_bottom_forming_adds_10(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="w_bottom", pattern_status="forming",
            neckline=105.0, note="W底形成中",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == min(100, base + 10)

    def test_head_shoulders_bottom_confirmed_adds_20(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_bottom", pattern_status="confirmed",
            neckline=105.0, note="頭肩底確認",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == min(100, base + 20)

    def test_head_shoulders_bottom_forming_adds_10(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_bottom", pattern_status="forming",
            neckline=105.0, note="頭肩底形成中",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == min(100, base + 10)

    def test_m_top_confirmed_subtracts_20(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="m_top", pattern_status="confirmed",
            neckline=95.0, note="M頂確認",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == max(0, base - 20)

    def test_m_top_forming_subtracts_10(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="m_top", pattern_status="forming",
            neckline=105.0, note="M頂形成中",
        ))
        sig = _compute_signal("2330", rows, {})
        assert sig["score"] == max(0, base - 10)

    def test_head_shoulders_top_forming_subtracts_10(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)
        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_top", pattern_status="forming",
            neckline=95.0, note="頭肩頂形成中",
        ))

        sig = _compute_signal("2330", rows, {})

        assert sig["score"] == max(0, base - 10)

    def test_head_shoulders_top_confirmed_subtracts_20(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)
        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_top", pattern_status="confirmed",
            neckline=95.0, note="頭肩頂確認",
        ))

        sig = _compute_signal("2330", rows, {})

        assert sig["score"] == max(0, base - 20)

    def test_head_shoulders_top_failed_has_no_bearish_penalty(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        rows = _make_rows(_flat_uptrend())
        base = self._base_score(rows, monkeypatch)
        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_top", pattern_status="failed",
            neckline=95.0, note="頭肩頂失效",
        ))

        sig = _compute_signal("2330", rows, {})

        assert sig["score"] == base

    def test_score_clamped_between_0_and_100(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="w_bottom", pattern_status="confirmed",
            neckline=105.0, note="W底確認",
        ))
        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        assert 0 <= sig["score"] <= 100


# ---------------------------------------------------------------------------
# 型態影響 reasons / risk_note
# ---------------------------------------------------------------------------

class TestPatternText:

    def test_w_bottom_forming_in_reasons(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="w_bottom", pattern_status="forming",
            neckline=105.0, note="W底形成中：兩底 100，頸線 105",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert any("W底" in reason for reason in sig["reasons"])

    def test_m_top_confirmed_in_risk_note(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="m_top", pattern_status="confirmed",
            neckline=95.0, note="M頂確認跌破頸線 95.0",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert "M頂" in sig["risk_note"]

    def test_w_bottom_failed_in_risk_note(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="w_bottom", pattern_status="failed",
            neckline=105.0, note="W底失效：收盤 77.0 跌破底部 80.0",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert "W底失效" in sig["risk_note"]

    def test_head_shoulders_bottom_confirmed_in_reasons(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_bottom", pattern_status="confirmed",
            neckline=105.0, note="頭肩底確認突破頸線 105.0",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert any("頭肩底" in reason for reason in sig["reasons"])

    def test_head_shoulders_bottom_failed_in_risk_note(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_bottom", pattern_status="failed",
            neckline=105.0, note="頭肩底失效：收盤 75.0 跌破頭部低點 80.0",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert "頭肩底失效" in sig["risk_note"]

    def test_m_top_failed_in_reasons(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="m_top", pattern_status="failed",
            neckline=95.0, note="M頂失效：收盤 107.0 突破頂部 100.0",
        ))
        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})
        assert any("M頂失效" in r for r in sig["reasons"])

    @pytest.mark.parametrize("status", ["forming", "confirmed"])
    def test_head_shoulders_top_bearish_status_in_risk_note(self, monkeypatch, status):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_top", pattern_status=status,
            neckline=95.0, note=f"頭肩頂 {status}",
        ))

        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})

        assert "頭肩頂" in sig["risk_note"]

    def test_head_shoulders_top_failed_in_reasons(self, monkeypatch):
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="head_and_shoulders_top", pattern_status="failed",
            neckline=95.0, note="頭肩頂失效：收盤突破頭部",
        ))

        sig = _compute_signal("2330", _make_rows(_flat_uptrend()), {})

        assert any("頭肩頂失效" in reason for reason in sig["reasons"])


# ---------------------------------------------------------------------------
# 強勢反轉保護
# ---------------------------------------------------------------------------

class TestStrongReversalGuard:

    def test_reclaim_ma60_is_not_exit_warning(self, monkeypatch):
        """前一日仍在 MA60 下方、今日強漲站回 MA60 時，不應仍判出場。"""
        from app.models.analysis import PatternResult
        import app.services.signals_service as svc

        monkeypatch.setattr(svc, "_detect_pattern", lambda r, **kw: PatternResult(
            pattern_type="none", pattern_status="none", neckline=None, note="",
        ))

        prices = [250.0] * 80 + [215.5, 282.0]
        rows = _make_rows(prices)
        for r in rows:
            r["volume"] = 10_000_000
        rows[-1]["volume"] = 18_000_000

        sig = _compute_signal("2408", rows, {}, {
            "market_regime": "bull",
            "market_filter": "allow",
            "market_reason": "測試市場偏多",
        })

        assert sig["internal_signal"] != "exit_warning"
        assert sig["signal"] != "SELL"
        assert "強勢反轉" in sig["no_buy_reason"] or any("強勢反轉" in r for r in sig["reasons"])


# ---------------------------------------------------------------------------
# universe_report.csv 欄位驗證
# ---------------------------------------------------------------------------

class TestUniverseReportPatternColumns:

    def test_csv_has_pattern_type_column(self, tmp_path, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or []
        assert "pattern_type" in fieldnames

    def test_csv_has_pattern_status_column(self, tmp_path, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or []
        assert "pattern_status" in fieldnames

    def test_csv_has_calculation_columns(self, tmp_path, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        rows = _make_rows(_flat_uptrend())
        sig = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or []
        assert "calculation_status" in fieldnames
        assert "calculation_error" in fieldnames

    def test_csv_has_professional_filter_columns(self, tmp_path, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        rows = _make_rows(_flat_uptrend())
        sig = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            fieldnames = csv.DictReader(f).fieldnames or []
        for field in (
            "trend_score", "entry_score", "risk_score",
            "market_regime", "relative_strength_score", "stage",
            "entry_price_low", "entry_price_high",
            "reward_risk_ratio", "price_plan_note",
            "support_source", "resistance_source",
            "entry_source", "stop_source", "target_source",
        ):
            assert field in fieldnames

    def test_csv_pattern_status_not_na(self, tmp_path, monkeypatch):
        """pattern_status 不應出現舊的 'n/a'。"""
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                assert row["pattern_status"] != "n/a"

    def test_csv_pattern_type_valid(self, tmp_path, monkeypatch):
        """CSV 中 pattern_type 必須是合法值。"""
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_OUT", tmp_path)

        valid = {
            "none", "w_bottom", "m_top",
            "head_and_shoulders_bottom", "head_and_shoulders_top",
        }
        rows = _make_rows(_flat_uptrend())
        sig  = _compute_signal("2330", rows, {})
        _write_universe_report([sig])

        with (tmp_path / "universe_report.csv").open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                assert row["pattern_type"] in valid
