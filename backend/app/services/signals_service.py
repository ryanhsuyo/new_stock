"""
signals_service.py — 日訊號計算服務（v2：支撐壓力 + 長短線趨勢 + breakout/breakdown）

內部使用 7 狀態訊號（signal_rules.md），對外輸出保持 API 契約（BUY/SELL/HOLD/DATA_MISSING）。

內部狀態 → 外部 signal 映射：
  entry_confirmed    → BUY   (entry_type: breakout)
  ready_to_enter     → BUY   (entry_type: pullback)
  watchlist          → HOLD
  hold               → HOLD
  take_profit_warning→ HOLD
  exit_warning       → SELL
  invalidated        → SELL
  DATA_MISSING       → DATA_MISSING

公開介面
--------
    run_daily_signals(as_of_date: str | None = None) -> dict
    check_required_files() -> list[str]
    get_signals_status() -> dict
"""

import csv
import hashlib
import json
import logging
import multiprocessing
import os
import re
import threading
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from app.services.pattern_service import detect_pattern as _detect_pattern
from app.services.fundamental_guard_service import evaluate_fundamental_guard
from app.services.daily_brief_service import write_daily_brief
from app.services.fundamental_service import write_fundamentals_report, write_priority_fill_csv
from app.services.rules_metadata_service import RULES_VERSION, build_rules_metadata
from app.services.signal_alert_service import write_signal_alerts
from app.services.signal_snapshot_service import write_snapshot_and_review
from app.services.today_scan_service import write_today_scan_report
from app.storage.chip_store import get_chip_metrics
from app.storage.fundamental_store import load_fundamentals
from app.storage.fundamental_store import FUNDAMENTALS_PATH
from app.storage.atomic_write import atomic_write_text
from app.storage.json_store import load_trades
from app.storage.name_store import load_stock_names
from app.storage.market_store import derive_market, load_stock_markets
from app.storage.settings_store import load_trading_settings

# ---------------------------------------------------------------------------
# 路徑常數
# backend/app/services/signals_service.py → 上三層 = backend/
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).resolve().parent.parent.parent
_DATA    = _BACKEND / "data"
_OUT     = _BACKEND / "out"

LEADERS_PATH   = _DATA / "leaders.json"
OHLCV_PATH     = _DATA / "ohlcv.csv"
POSITIONS_PATH = _DATA / "positions.json"
MARKET_NOTES_PATH = _DATA / "market_notes.json"

MIN_ROWS    = 60     # MA60 最少需要 60 筆
OLD_WANG_MARKET_MIN_ROWS = 10  # 老王大盤濾網只需要 MA5/MA10 與大量低點
RSI_PERIOD  = 14
SR_LOOKBACK = 20     # 支撐壓力回看天數（不含今日）
BENCHMARK_CODE = "0050"  # 第一版以台灣 50 ETF 代理大盤環境 / 相對強度
CORE_STRATEGY_ID = "core_technical_v2"
OLD_WANG_TAG = "old_wang_market_chip_rotation"
OLD_WANG_TAG_NAME = "老王大盤籌碼輪動"
STEADY_MOMENTUM_TAG = "steady_momentum_v1"
STEADY_MOMENTUM_NAME = "Quality Momentum Lite"
DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS = 20.0
OLD_WANG_MA10_TOLERANCE_PCT = 0.002

log = logging.getLogger(__name__)

# 內部 7 狀態 → (外部 signal, entry_type)
_EXT_MAP: dict[str, tuple[str, str]] = {
    "entry_confirmed":     ("BUY",          "breakout"),
    "ready_to_enter":      ("BUY",          "pullback"),
    "watchlist":           ("HOLD",         ""),
    "hold":                ("HOLD",         ""),
    "take_profit_warning": ("HOLD",         ""),
    "exit_warning":        ("SELL",         ""),
    "invalidated":         ("SELL",         ""),
    "DATA_MISSING":        ("DATA_MISSING", ""),
}

# universe_report.csv 欄位順序（新 + 舊相容）
_REPORT_FIELDS = [
    "code", "name", "data_ok", "data_missing",
    "calculation_status", "calculation_error",
    "signal", "internal_signal", "entry_type", "score",
    "trend_score", "entry_score", "risk_score",
    "position_size_pct", "position_size_note",
    "holding_shares", "holding_avg_cost", "holding_position_pct",
    "long_trend", "short_trend",
    "market_regime", "market_filter", "relative_strength_score",
    "strategy_alignment", "aligned_strategies", "strategy_conflict_notes",
    "old_wang_market_regime", "old_wang_market_filter",
    "old_wang_market_source", "old_wang_market_reason",
    "relative_strength_60d", "relative_strength_120d", "stage",
    "strategy_tags", "old_wang_flag", "old_wang_tag", "old_wang_score",
    "old_wang_signal", "old_wang_badges", "old_wang_reason", "old_wang_sector",
    "sector_score", "old_wang_volume_signal", "old_wang_gap_type",
    "old_wang_gap_support", "old_wang_gap_resistance", "old_wang_gap_note",
    "old_wang_ma_signal", "old_wang_volume_low_support",
    "old_wang_volume_low_price", "old_wang_support_state",
    "old_wang_ma_break_count", "old_wang_previous_high_risk",
    "old_wang_chip_signal", "old_wang_raw_score",
    "old_wang_previous_high_state", "old_wang_previous_high_price",
    "old_wang_volume_high_breakout", "old_wang_volume_high_price",
    "old_wang_all_ma_reclaim", "old_wang_parabolic_ma10_hold",
    "steady_momentum_flag", "steady_momentum_tag", "steady_momentum_score",
    "steady_momentum_signal", "steady_momentum_reason",
    "fundamental_flag", "fundamental_tag", "fundamental_score", "fundamental_signal",
    "fundamental_reason", "fundamental_data_ok", "fundamental_data_missing_reason",
    "fundamental_quality_score", "fundamental_value_score", "fundamental_safety_score",
    "fundamental_growth_score", "fundamental_data_completeness_pct",
    "fundamental_missing_fields", "fundamental_scored_groups",
    "daily_action", "daily_action_label", "daily_action_identity",
    "daily_action_reason", "daily_key_price", "daily_invalidation",
    "daily_priority", "daily_checklist",
    "data_as_of",
    "entry_price_low", "entry_price_high",
    "stop_price", "target_price", "risk_pct", "reward_pct", "reward_risk_ratio",
    "price_plan_note",
    "support_source", "resistance_source",
    "entry_source", "stop_source", "target_source",
    "support_price", "resistance_price",
    "pattern_type", "pattern_status",
    "no_buy_reason", "risk_note",
    "close", "ma5", "ma10", "ma20", "ma60", "rsi14", "volume", "vol_ratio",
    "reasons",
]



_signals_lock = threading.Lock()
_signals_run_status: dict = {"status": "idle", "error": None, "run_id": None}

_name_cache: dict[str, str] | None = None


def _reload_name_cache() -> None:
    global _name_cache
    _name_cache = load_stock_names()


def _stock_name(code: str) -> str:
    global _name_cache
    if _name_cache is None:
        _reload_name_cache()
    return _name_cache.get(code, code)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 前置檢查 / 狀態查詢（供 router 使用）
# ---------------------------------------------------------------------------

def check_required_files() -> list[str]:
    missing: list[str] = []
    if not LEADERS_PATH.exists():
        missing.append(f"leaders ({LEADERS_PATH})")
    if not OHLCV_PATH.exists():
        missing.append(f"ohlcv ({OHLCV_PATH})")
    return missing


def get_universe() -> list[dict]:
    """
    回傳目前追蹤股票的資料狀態清單（leaders.json × ohlcv.csv 交叉比對）。

    每筆欄位：
      code             股票代碼
      name             股票名稱
      has_data         bool，是否有足夠資料（>= MIN_ROWS）可分析
      row_count        目前 ohlcv.csv 中的資料筆數
      last_data_as_of  最後一筆資料的日期（YYYY-MM-DD）；無資料時 null
      data_status      "ok" | "insufficient" | "no_data"
    """
    if not LEADERS_PATH.exists():
        return []

    codes = _load_leaders()
    ohlcv = _load_ohlcv(None)   # 不限 as_of，讀全部資料

    result: list[dict] = []
    for code in codes:
        rows      = ohlcv.get(code, [])
        row_count = len(rows)
        last_date = rows[-1]["date"] if rows else None

        if row_count == 0:
            data_status = "no_data"
        elif row_count < MIN_ROWS:
            data_status = "insufficient"
        else:
            data_status = "ok"

        result.append({
            "code":            code,
            "name":            _stock_name(code),
            "has_data":        data_status == "ok",
            "row_count":       row_count,
            "last_data_as_of": last_date,
            "data_status":     data_status,
        })

    return sorted(result, key=lambda x: x["code"])


def get_summary() -> dict:
    """
    讀取最近一次 run 產生的 summary.json。
    檔案不存在時回傳 None（由 router 決定如何回應 404）。
    """
    path = _OUT / "summary.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def get_universe_report_json() -> list[dict] | None:
    """
    讀取最近一次 run 產生的 universe_report.csv，以 JSON-ready dict list 回傳。
    檔案不存在時回傳 None（由 router 決定回應 404）。

    每筆處理：
      - bool / int / float 欄位型別轉換；空值轉為 None
      - 補充 exchange（TWSE / TPEX）和 market（TWSE / TPEX / ETF）
        來源：stock_markets.json > derive_market heuristic
    """
    from app.storage.market_store import derive_market, load_stock_markets

    path = _OUT / "universe_report.csv"
    if not path.exists():
        return None

    bool_fields  = {
        "data_ok", "data_missing", "old_wang_flag",
        "old_wang_volume_low_support", "old_wang_previous_high_risk",
        "old_wang_volume_high_breakout", "old_wang_all_ma_reclaim",
        "old_wang_parabolic_ma10_hold",
        "fundamental_flag", "fundamental_data_ok",
    }
    int_fields   = {"score", "trend_score", "entry_score", "risk_score", "volume",
                    "position_size_pct", "holding_shares",
                    "relative_strength_score", "old_wang_score", "sector_score",
                    "old_wang_ma_break_count", "old_wang_raw_score",
                    "fundamental_score", "fundamental_quality_score", "fundamental_value_score",
                    "fundamental_safety_score", "fundamental_growth_score",
                    "fundamental_data_completeness_pct", "daily_priority"}
    float_fields = {"close", "ma5", "ma10", "ma20", "ma60", "rsi14", "vol_ratio",
                    "entry_price_low", "entry_price_high",
                    "support_price", "resistance_price",
                    "relative_strength_60d", "relative_strength_120d",
                    "stop_price", "target_price", "risk_pct", "reward_pct",
                    "reward_risk_ratio", "old_wang_gap_support",
                    "old_wang_gap_resistance", "old_wang_volume_low_price",
                    "old_wang_previous_high_price", "old_wang_volume_high_price",
                    "holding_avg_cost", "holding_position_pct"}

    def _parse_int_field(raw: str) -> int | None:
        if raw in ("", "None", "—"):
            return None
        value = float(raw)
        return int(value)

    all_markets = load_stock_markets()   # {code: exchange}

    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item: dict = {}
            for k, v in row.items():
                sv = (v or "").strip()
                if k in bool_fields:
                    item[k] = sv.lower() == "true"
                elif k in int_fields:
                    item[k] = _parse_int_field(sv)
                elif k in float_fields:
                    item[k] = float(sv) if sv not in ("", "None", "—") else None
                elif k == "daily_checklist":
                    item[k] = json.loads(sv) if sv else []
                else:
                    item[k] = v

            code = item.get("code", "")
            exchange = all_markets.get(code) or ""
            item["exchange"] = exchange
            item["market"]   = derive_market(code, exchange or None)
            rows.append(item)
    return rows


def get_signals_status() -> dict:
    def _file_info(path: Path, optional: bool = False) -> dict:
        exists = path.exists()
        info: dict = {"exists": exists, "path": str(path)}
        if optional:
            info["optional"] = True
        if exists:
            mtime = path.stat().st_mtime
            info["last_modified"] = datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        return info

    summary_path = _OUT / "summary.json"
    summary_info = _file_info(summary_path)
    daily_brief_path = _OUT / "daily_brief.json"
    daily_brief_info = _file_info(daily_brief_path)
    manual_note_status = None
    if summary_info["exists"]:
        try:
            with summary_path.open(encoding="utf-8") as f:
                s = json.load(f)
            summary_info["as_of"]        = s.get("as_of")
            summary_info["generated_at"] = s.get("generated_at")
            note = s.get("manual_market_note") or {}
            if note:
                manual_note_status = {
                    "date": note.get("date"),
                    "applies_to_as_of": note.get("applies_to_as_of"),
                    "is_stale": bool(note.get("is_stale")),
                    "update_required": bool(note.get("update_required") or note.get("is_stale")),
                    "stale_trading_days": note.get("stale_trading_days"),
                    "status_label": note.get("status_label"),
                    "stale_reason": note.get("stale_reason") or "",
                }
        except Exception as exc:
            summary_info["parse_error"] = str(exc)[:200]
    if daily_brief_info["exists"]:
        try:
            with daily_brief_path.open(encoding="utf-8") as f:
                brief = json.load(f)
            daily_brief_info["as_of"] = brief.get("as_of")
            daily_brief_info["generated_at"] = brief.get("generated_at")
            data_status = brief.get("data_status") or {}
            daily_brief_info["status_label"] = data_status.get("status_label")
            daily_brief_info["update_required"] = data_status.get("update_required")
        except Exception as exc:
            daily_brief_info["parse_error"] = str(exc)[:200]

    universe_report_info = _file_info(_OUT / "universe_report.csv")
    if universe_report_info["exists"]:
        try:
            with (_OUT / "universe_report.csv").open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                row_count = 0
                latest_as_of: str | None = None
                for row in reader:
                    row_count += 1
                    data_as_of = (row.get("data_as_of") or "").strip()
                    if data_as_of and (latest_as_of is None or data_as_of > latest_as_of):
                        latest_as_of = data_as_of
                universe_report_info["row_count"] = row_count
                universe_report_info["as_of"] = latest_as_of
        except Exception as exc:
            universe_report_info["parse_error"] = str(exc)[:200]

    return {
        "run_status": _signals_run_status["status"],   # idle / running / success / failed
        "run_error":  _signals_run_status.get("error"),
        "out_dir": str(_OUT),
        "manual_note_status": manual_note_status,
        "out_files": {
            "summary_json":        summary_info,
            "universe_report_csv": universe_report_info,
            "daily_brief_json":    daily_brief_info,
        },
        "data_files": {
            "leaders_json":   _file_info(LEADERS_PATH),
            "ohlcv_csv":      _file_info(OHLCV_PATH),
            "market_notes_json": _file_info(MARKET_NOTES_PATH, optional=True),
            "fundamentals_json": _file_info(FUNDAMENTALS_PATH, optional=True),
            "positions_json": _file_info(POSITIONS_PATH, optional=True),
        },
    }


def trigger_background_signals(as_of_date: str | None = None) -> dict:
    """
    在背景 thread 執行 run_daily_signals，立即回傳。

    若目前已在執行中，回傳 {"status": "already_running"}。
    否則回傳 {"status": "started"}。
    進度請透過 GET /api/stocks/signals/status 的 run_status 欄位輪詢。
    """
    global _signals_run_status

    if _signals_run_status.get("status") == "running":
        return {"status": "already_running"}

    acquired = _signals_lock.acquire(blocking=False)
    if not acquired:
        return {"status": "already_running"}

    run_id = object()
    _signals_run_status = {"status": "running", "error": None, "run_id": run_id}

    def _run() -> None:
        global _signals_run_status
        try:
            run_daily_signals(as_of_date=as_of_date)
            if _signals_run_status.get("run_id") is run_id:
                _signals_run_status = {"status": "success", "error": None, "run_id": run_id}
        except Exception as exc:
            if _signals_run_status.get("run_id") is run_id:
                _signals_run_status = {
                    "status": "failed",
                    "error": str(exc)[:500],
                    "run_id": run_id,
                }
        finally:
            _signals_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


# ---------------------------------------------------------------------------
# 資料載入
# ---------------------------------------------------------------------------

def _flatten_codes(obj) -> list[str]:
    codes: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            codes.extend(_flatten_codes(v))
    elif isinstance(obj, list):
        for item in obj:
            codes.extend(_flatten_codes(item))
    elif isinstance(obj, str):
        codes.append(obj.strip())
    return codes


def _load_leaders() -> list[str]:
    with LEADERS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    raw  = _flatten_codes(data)
    seen: set[str] = set()
    unique: list[str] = []
    for c in raw:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _load_leader_groups() -> dict[str, list[str]]:
    """
    讀取 leaders.json 的第一層族群設定。
    老王 tag 需要「族群輪動」脈絡；若 leaders.json 未採 dict 結構則退回空 dict。
    """
    with LEADERS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}

    groups: dict[str, list[str]] = {}
    for group_name, raw in data.items():
        codes = _flatten_codes(raw)
        if codes:
            groups[str(group_name)] = codes
    return groups


def _load_ohlcv(as_of_date: str | None) -> dict[str, list[dict]]:
    by_code: dict[str, list[dict]] = {}
    if not OHLCV_PATH.exists():
        return by_code

    with OHLCV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if as_of_date and row["date"] > as_of_date:
                continue
            code = row["code"]
            if code not in by_code:
                by_code[code] = []
            by_code[code].append({
                "date":   row["date"],
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": int(row["volume"]),
            })

    for code in by_code:
        by_code[code].sort(key=lambda r: r["date"])

    return by_code


def _load_positions() -> dict:
    """
    讀取目前持股。

    交易紀錄 trades.json 是目前實際持倉的主要來源；positions.json 保留為舊格式備援。
    回傳格式維持 {"cash": ..., "holdings": {code: {...}}}，供訊號判斷是否持股。
    """
    holdings: dict[str, dict] = {}
    stock_names = load_stock_names()
    try:
        settings = load_trading_settings()

        def trade_cost(trade) -> float:
            if trade.net_amount is not None:
                return float(trade.net_amount)
            gross = round(trade.price * trade.shares)
            raw_fee = gross * settings["brokerage_fee_rate"] * settings["brokerage_discount"]
            fee = round(raw_fee)
            if gross > 0 and settings["min_brokerage_fee"] > 0:
                fee = max(fee, round(settings["min_brokerage_fee"]))
            if trade.trade_type == "buy":
                return float(gross + fee)
            tax = round(gross * settings["sell_transaction_tax_rate"])
            return float(gross - fee - tax)

        buy_stats: dict[str, dict] = {}
        sold_shares: dict[str, int] = {}
        for trade in load_trades():
            sid = trade.stock_id
            if trade.trade_type == "buy":
                if sid not in buy_stats:
                    buy_stats[sid] = {"name": trade.name, "shares": 0, "cost": 0.0}
                buy_stats[sid]["shares"] += trade.shares
                buy_stats[sid]["cost"] += trade_cost(trade)
            else:
                sold_shares[sid] = sold_shares.get(sid, 0) + trade.shares

        for sid, stat in buy_stats.items():
            remaining = stat["shares"] - sold_shares.get(sid, 0)
            if remaining > 0:
                holdings[sid] = {
                    "name": stock_names.get(sid) or stat["name"],
                    "shares": remaining,
                    "avg_cost": round(stat["cost"] / stat["shares"], 2),
                }

        return {"cash": 0, "holdings": holdings, "source": "trades"}
    except Exception as exc:
        log.warning(
            "trades position calculation failed; trying positions.json fallback: %s",
            exc,
        )

    if POSITIONS_PATH.exists():
        with POSITIONS_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("source", "positions")
        return data
    return {"cash": 1_000_000, "holdings": {}, "source": "none"}


def _annotate_holding_weights(signals: list[dict], positions: dict) -> None:
    holdings = positions.get("holdings", {})
    total_value = 0.0
    values_by_code: dict[str, float] = {}

    for sig in signals:
        code = sig.get("code")
        holding = holdings.get(code) if code else None
        shares = int(holding.get("shares", 0)) if isinstance(holding, dict) else 0
        avg_cost = holding.get("avg_cost") if isinstance(holding, dict) else None
        close = sig.get("close")
        value = shares * close if shares and isinstance(close, (int, float)) else 0.0
        values_by_code[code] = value
        total_value += value
        sig["holding_shares"] = shares
        sig["holding_avg_cost"] = avg_cost if isinstance(avg_cost, (int, float)) else None

    for sig in signals:
        code = sig.get("code")
        value = values_by_code.get(code, 0.0)
        sig["holding_position_pct"] = round(value / total_value * 100, 2) if total_value > 0 and value > 0 else 0.0


# ---------------------------------------------------------------------------
# 技術指標（純 Python）
# ---------------------------------------------------------------------------

def _ma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains  = [max(d, 0.0) for d in recent]
    losses = [max(-d, 0.0) for d in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _avg_vol(vols: list[int], lookback: int = 20) -> float:
    window = vols[-(lookback + 1):-1]
    return sum(window) / len(window) if window else 0.0


def _return_pct(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    base = closes[-lookback - 1]
    if base <= 0:
        return None
    return round((closes[-1] / base - 1) * 100, 2)


def _slope_up(values: list[float], lookback: int) -> bool:
    if len(values) <= lookback:
        return False
    return values[-1] > values[-lookback - 1]


def _stage_from_closes(closes: list[float], ma60: float | None) -> str:
    """
    Weinstein Stage Analysis 第一版：
      stage_2 — 價格站上 MA60 且 MA60 上彎（主升段）
      stage_4 — 價格跌破 MA60 且 MA60 下彎（主跌段）
      stage_1 — 價格接近 MA60 且均線走平（築底 / 盤整）
      stage_3 — 價格仍在 MA60 上方但均線未上彎（頭部 / 轉弱觀察）

    專案目前只有日線 OHLCV，先以 MA60 近 20 日斜率代理 30 週均線概念。
    """
    if ma60 is None or len(closes) < 80:
        return "unknown"

    close = closes[-1]
    ma60_prev = _ma(closes[:-20], 60)
    if ma60_prev is None:
        return "unknown"

    ma_up = ma60 > ma60_prev
    ma_down = ma60 < ma60_prev
    near_ma = ma60 * 0.97 <= close <= ma60 * 1.05

    if close > ma60 and ma_up:
        return "stage_2"
    if close < ma60 and ma_down:
        return "stage_4"
    if near_ma:
        return "stage_1"
    if close > ma60:
        return "stage_3"
    return "stage_4"


def _relative_strength(
    closes: list[float],
    benchmark_rows: list[dict] | None,
) -> tuple[int | None, float | None, float | None]:
    """
    相對強度第一版：股票 60/120 日報酬減去 benchmark 報酬。
    回傳 (0-100 score, rs60, rs120)。資料不足時回傳 None。
    """
    if not benchmark_rows:
        return None, None, None

    benchmark_closes = [r["close"] for r in benchmark_rows]
    stock_60 = _return_pct(closes, 60)
    stock_120 = _return_pct(closes, 120)
    bench_60 = _return_pct(benchmark_closes, 60)
    bench_120 = _return_pct(benchmark_closes, 120)

    rs60 = round(stock_60 - bench_60, 2) if stock_60 is not None and bench_60 is not None else None
    rs120 = round(stock_120 - bench_120, 2) if stock_120 is not None and bench_120 is not None else None

    available = [v for v in (rs60, rs120) if v is not None]
    if not available:
        return None, rs60, rs120

    avg_rs = sum(available) / len(available)
    if avg_rs >= 15:
        score = 100
    elif avg_rs >= 8:
        score = 85
    elif avg_rs >= 3:
        score = 70
    elif avg_rs >= -3:
        score = 50
    elif avg_rs >= -8:
        score = 35
    else:
        score = 20
    return score, rs60, rs120


def _reward_risk(
    close: float,
    support_price: float | None,
    resistance_price: float | None,
    ma20: float | None,
    ma60: float | None,
) -> tuple[
    float | None, float | None, float | None, float | None, float | None, str, str
]:
    """
    以支撐/均線估算停損，以壓力/區間高度估算目標。
    這是入場品質濾網，不是價格預測。
    """
    stop_candidates = [
        (p, source)
        for p, source in (
            (support_price, "support_price"),
            (ma20, "MA20"),
            (ma60, "MA60"),
        )
        if p is not None and p < close
    ]
    if not stop_candidates:
        return None, None, None, None, None, "", ""

    stop_anchor, stop_source = max(stop_candidates, key=lambda item: item[0])
    stop_price = round(stop_anchor * 0.98, 2)
    if stop_price <= 0 or stop_price >= close:
        return None, None, None, None, None, "", ""

    if resistance_price is not None and resistance_price > close:
        target_price = resistance_price
        target_source = "resistance_price"
    elif resistance_price is not None and support_price is not None and resistance_price > support_price:
        target_price = close + (resistance_price - support_price) * 0.5
        target_source = "support_resistance_range_extension"
    else:
        target_price = close * 1.1
        target_source = "10pct_above_close"

    target_price = round(target_price, 2)
    risk_pct = round((close / stop_price - 1) * 100, 2)
    reward_pct = round((target_price / close - 1) * 100, 2)
    rr = round(reward_pct / risk_pct, 2) if risk_pct > 0 else None
    return stop_price, target_price, risk_pct, reward_pct, rr, stop_source, target_source


def _entry_price_plan(
    *,
    internal_signal: str,
    close: float,
    long_trend: str,
    stage: str,
    support_price: float | None,
    resistance_price: float | None,
    ma20: float | None,
    ma60: float | None,
) -> tuple[float | None, float | None, str, str]:
    """
    產生可操作的進場價格區間。

    原則：
      - 空頭 / 主跌段不給新進場區間，只提示等待趨勢修復
      - 突破確認：以突破後回測壓力轉支撐或最新收盤附近為區間
      - 準備進場 / 觀察中多頭：以 MA20 / 支撐附近回測區為區間
    """
    if long_trend == "down" or stage == "stage_4" or internal_signal in ("exit_warning", "invalidated"):
        return None, None, "目前不建議新進場；先等收盤重新站上 MA60 或重新形成多頭結構", ""

    if internal_signal == "take_profit_warning":
        return None, None, "目前偏停利區，不建議追價；等待回測 MA20 或支撐區再評估", ""

    if internal_signal == "entry_confirmed":
        if resistance_price is not None and close > resistance_price:
            low = max(resistance_price * 0.99, close * 0.97)
            high = close * 1.02
            note = "突破確認後，可等回測壓力轉支撐或最新收盤附近小幅分批"
            entry_source = "resistance_retest_or_close"
        else:
            low = close * 0.98
            high = close * 1.02
            note = "突破確認後，僅適合最新收盤附近小幅分批，避免追高過深"
            entry_source = "latest_close_breakout"
        return round(min(low, close), 2), round(max(high, close), 2), note, entry_source

    pullback_candidates = [
        (p, source)
        for p, source in (
            (ma20, "MA20"),
            (support_price, "support_price"),
            (ma60, "MA60"),
        )
        if p is not None and p > 0 and p <= close * 1.03
    ]
    if pullback_candidates:
        anchor, entry_source = max(pullback_candidates, key=lambda item: item[0])
        low = anchor * 0.98
        high = min(anchor * 1.05, close * 1.02)
        note = "可等回測 MA20 / 支撐附近且未跌破時分批進場"
        return round(low, 2), round(max(low, high), 2), note, entry_source

    if long_trend == "up" and ma20 is not None:
        return (
            round(ma20 * 0.98, 2),
            round(ma20 * 1.03, 2),
            "長線偏多但最新收盤離支撐較遠，等待回測 MA20 附近",
            "MA20",
        )

    return None, None, "趨勢尚未給出清楚進場區間，先列入觀察", ""


def _position_size_plan(
    *,
    internal_signal: str,
    old_wang_flag: bool,
    reward_risk_ratio: float | None,
    risk_score: int,
    old_wang_chip_signal: str,
) -> tuple[int, str]:
    """
    建議倉位第一版。

    只輸出「單筆初始部位上限」的參考百分比，不代表滿倉建議。
    """
    if internal_signal in ("exit_warning", "invalidated", "take_profit_warning", "DATA_MISSING"):
        return 0, "風險/停利訊號，不建議新進場"

    rr = reward_risk_ratio or 0
    chip_penalty = old_wang_chip_signal == "against"

    if internal_signal in ("entry_confirmed", "ready_to_enter") and old_wang_flag:
        if rr >= 1.5 and risk_score <= 60 and not chip_penalty:
            return 25, "雙重共振且風險可控，初始部位 20-30%"
        return 15, "雙重共振但風險報酬/籌碼未完全理想，初始部位 10-15%"

    if internal_signal in ("entry_confirmed", "ready_to_enter"):
        if rr >= 1.5 and risk_score <= 60:
            return 20, "日線買點成立，初始部位 10-20%"
        return 10, "日線買點成立但風險報酬不足，僅小部位 5-10%"

    if old_wang_flag:
        return 5, "老王觀察成立但日線買點未成立，先觀察或 5% 試單"

    return 0, "條件未完整成立，等待下一次收盤確認"


def _steady_momentum_indicator(
    *,
    close: float,
    ma20: float | None,
    ma60: float | None,
    long_trend: str,
    stage: str,
    market_filter: str,
    relative_strength_score: int | None,
    trend_score: int,
    entry_score: int,
    risk_score: int,
    reward_risk_ratio: float | None,
    rsi14: float | None,
    fundamental_guard: dict,
) -> dict:
    trend_part = round(max(0, min(100, trend_score)) * 0.25)
    rs_part = round(max(0, min(100, relative_strength_score or 50)) * 0.20)
    entry_part = round(max(0, min(100, entry_score)) * 0.20)

    if reward_risk_ratio is None:
        rr_part = 8
    elif reward_risk_ratio >= 2:
        rr_part = 15
    elif reward_risk_ratio >= 1.5:
        rr_part = 12
    elif reward_risk_ratio >= 1.2:
        rr_part = 7
    else:
        rr_part = 0

    heat_part = 10
    if rsi14 is not None:
        if rsi14 > 75:
            heat_part = 0
        elif rsi14 > 70:
            heat_part = 4
    if ma20 is not None and ma20 > 0 and close > ma20 * 1.12:
        heat_part = min(heat_part, 4)
    elif ma20 is not None and ma20 > 0 and close > ma20 * 1.08:
        heat_part = min(heat_part, 7)

    fundamental_data_ok = bool(fundamental_guard.get("fundamental_data_ok"))
    if fundamental_data_ok:
        available = [
            fundamental_guard.get("fundamental_quality_score"),
            fundamental_guard.get("fundamental_safety_score"),
            fundamental_guard.get("fundamental_growth_score"),
        ]
        available = [v for v in available if isinstance(v, (int, float))]
        fundamental_part = round(sum(available) / len(available) * 0.10) if available else 6
    else:
        fundamental_part = 6
    if fundamental_data_ok:
        fundamental_part_label = f"基本面避雷{fundamental_part}/10"
    else:
        missing_reason = fundamental_guard.get("fundamental_data_missing_reason") or "缺少可評分基本面資料"
        fundamental_part_label = f"基本面避雷：基本面資料不足，中性保留{fundamental_part}/10（{missing_reason}）"

    score = max(0, min(100, trend_part + rs_part + entry_part + rr_part + heat_part + fundamental_part))
    hard_block = (
        long_trend == "down"
        or stage == "stage_4"
        or market_filter == "block"
        or risk_score > 70
    )
    flag = score >= 75 and not hard_block

    parts = [
        f"趨勢{trend_part}/25",
        f"相對強度{rs_part}/20",
        f"進場位置{entry_part}/20",
        f"風險報酬{rr_part}/15",
        f"過熱控制{heat_part}/10",
        fundamental_part_label,
    ]
    if hard_block:
        parts.append("風險閘門未通過")

    return {
        "steady_momentum_flag": flag,
        "steady_momentum_tag": STEADY_MOMENTUM_TAG if flag else "",
        "steady_momentum_score": score,
        "steady_momentum_signal": "穩健動能候選" if flag else "未達穩健動能門檻",
        "steady_momentum_reason": "；".join(parts),
    }


def _strategy_alignment(
    internal_signal: str,
    old_wang_flag: bool,
    steady_momentum_flag: bool,
) -> dict:
    core_positive = {"entry_confirmed", "ready_to_enter", "hold"}
    core_risk = {"take_profit_warning", "exit_warning", "invalidated", "DATA_MISSING"}

    aligned: list[str] = []
    notes: list[str] = []

    if internal_signal in core_positive:
        aligned.append("core")
    if old_wang_flag:
        aligned.append("old_wang")
    if steady_momentum_flag:
        aligned.append("steady_momentum")

    if internal_signal in {"exit_warning", "invalidated"} and (old_wang_flag or steady_momentum_flag):
        notes.append("內部技術訊號已轉風險，老王或穩健動能訊號不可覆蓋出場/失效")
    elif internal_signal == "take_profit_warning" and (old_wang_flag or steady_momentum_flag):
        notes.append("內部技術訊號進入停利觀察，其他策略只作續抱參考，不追價")

    if old_wang_flag and internal_signal not in core_positive and internal_signal not in core_risk:
        notes.append("老王短波段轉強，但日線買點尚未確認")
    if steady_momentum_flag and internal_signal in {"exit_warning", "invalidated", "take_profit_warning"}:
        notes.append("穩健動能成立，但短線技術位置不適合加碼")

    if notes and internal_signal in {"exit_warning", "invalidated", "take_profit_warning"}:
        alignment = "conflict"
    elif len(aligned) >= 2:
        alignment = "strong_alignment"
    elif len(aligned) == 1:
        alignment = "single_strategy"
    else:
        alignment = "no_alignment"

    return {
        "strategy_alignment": alignment,
        "aligned_strategies": aligned,
        "strategy_conflict_notes": notes,
    }


def _fmt_price(value: float | int | None) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _daily_decision_plan(sig: dict) -> dict:
    """
    將訊號壓縮成每日可執行動作；不改變 BUY/SELL/HOLD 主訊號。
    """
    held = (sig.get("holding_shares") or 0) > 0
    old_wang = bool(sig.get("old_wang_flag"))
    core_buy = sig.get("internal_signal") in ("entry_confirmed", "ready_to_enter")
    hot = isinstance(sig.get("rsi14"), (int, float)) and sig["rsi14"] > 75

    if sig.get("old_wang_volume_low_price") is not None:
        key_price = f"爆量低 {_fmt_price(sig.get('old_wang_volume_low_price'))}"
    elif sig.get("old_wang_gap_support") is not None:
        key_price = f"缺口 {_fmt_price(sig.get('old_wang_gap_support'))}"
    elif sig.get("ma10") is not None:
        key_price = f"MA10 {_fmt_price(sig.get('ma10'))}"
    elif sig.get("ma20") is not None:
        key_price = f"MA20 {_fmt_price(sig.get('ma20'))}"
    elif sig.get("stop_price") is not None:
        key_price = f"停損 {_fmt_price(sig.get('stop_price'))}"
    else:
        key_price = "—"

    stop = _fmt_price(sig.get("stop_price")) if sig.get("stop_price") is not None else key_price

    def build(action: str, label: str, reason: str, invalidation: str, priority: int) -> dict:
        return {
            "daily_action": action,
            "daily_action_label": label,
            "daily_action_identity": "已持有" if held else "未持有",
            "daily_action_reason": reason,
            "daily_key_price": key_price,
            "daily_invalidation": invalidation,
            "daily_priority": priority,
        }

    if not sig.get("data_ok") or sig.get("internal_signal") == "DATA_MISSING":
        return build("avoid", "資料不足", "資料不足，先不做交易判斷", "補齊資料後重算", 80)

    if sig.get("internal_signal") in ("invalidated", "exit_warning"):
        return build(
            "exit",
            "出場處理" if held else "暫不進場",
            sig.get("no_buy_reason") or "趨勢或支撐已破壞",
            "重新站回 MA20/MA60 後再評估",
            100,
        )

    if held:
        if sig.get("internal_signal") == "take_profit_warning" or (hot and sig.get("old_wang_support_state") != "short_stop_trend_intact"):
            reason = "短線過熱，跌破 5/10 再減碼" if hot else sig.get("no_buy_reason") or "接近壓力區，先控風險"
            return build("reduce", "減碼觀察", reason, f"跌破 {key_price}", 95)
        reason = "仍守老王關鍵支撐，不預設高點" if old_wang else "長線未轉弱，依停損續抱"
        return build("hold", "續抱", reason, f"跌破 {key_price}", 70)

    if core_buy and old_wang and not hot:
        return build("enter", "可小試", "日線買點與老王旗標共振，可依區間小量", f"跌破 {stop}", 90)

    if core_buy:
        reason = "突破成立但仍需控量" if sig.get("entry_type") == "breakout" else "進場條件成立，可分批"
        return build("enter", "可小試", reason, f"跌破 {stop}", 86)

    if old_wang:
        reason = "老王旗標成立但短線過熱，不追高" if hot else "老王旗標成立，等 5/10 或支撐確認"
        return build("wait_pullback", "等回測", reason, f"跌破 {key_price}", 82)

    if sig.get("fundamental_flag"):
        return build(
            "long_watch",
            "長期觀察",
            "基本面避雷資料良好，但短線還沒有買點",
            sig.get("fundamental_reason") or "基本面避雷資料轉弱",
            55,
        )

    label = "先觀察" if sig.get("internal_signal") == "watchlist" else "暫不碰"
    return build("avoid", label, sig.get("no_buy_reason") or "條件未完整成立", "等待重新轉強或出現買點", 40)


def _daily_checklist(sig: dict) -> list[dict]:
    """
    將每日判斷拆成前端可直接呈現的檢查項。

    這裡只結構化既有訊號，不重新計算買賣規則。
    """
    checklist: list[dict] = []

    def add(category: str, label: str, status: str, detail: str, key_price: str = "") -> None:
        checklist.append({
            "category": category,
            "label": label,
            "status": status,
            "detail": detail,
            "key_price": key_price,
        })

    if not sig.get("data_ok") or sig.get("internal_signal") == "DATA_MISSING":
        reason = sig.get("no_buy_reason") or sig.get("data_missing_reason") or "資料不足"
        add("market", "大盤濾網", "info", "資料不足時不做大盤加減分")
        add("setup", "個股條件", "fail", reason)
        add("risk", "風險控管", "fail", "資料不足，無法估算支撐、壓力與停損")
        add("action", "明日動作", "fail", "先補齊資料，不做交易")
        return checklist

    old_wang_filter = sig.get("old_wang_market_filter") or sig.get("market_filter") or "neutral"
    market_reason = sig.get("old_wang_market_reason") or sig.get("market_regime") or "大盤濾網未提供說明"
    if old_wang_filter == "allow":
        market_status = "pass"
    elif old_wang_filter == "block":
        market_status = "fail"
    else:
        market_status = "warn"
    add("market", "大盤可做", market_status, str(market_reason))

    internal = sig.get("internal_signal", "")
    if internal in ("entry_confirmed", "ready_to_enter", "hold"):
        setup_status = "pass"
    elif internal in ("take_profit_warning", "watchlist"):
        setup_status = "warn"
    else:
        setup_status = "fail"
    setup_detail = sig.get("daily_action_reason") or sig.get("no_buy_reason") or "條件觀察中"
    add("setup", "個股型態", setup_status, setup_detail, sig.get("daily_key_price") or "")

    risk_score = sig.get("risk_score") or 0
    rr = sig.get("reward_risk_ratio")
    if internal in ("exit_warning", "invalidated") or risk_score >= 75:
        risk_status = "fail"
    elif risk_score >= 50 or internal == "take_profit_warning":
        risk_status = "warn"
    else:
        risk_status = "pass"
    risk_parts = [f"風險分 {risk_score}"]
    if isinstance(rr, (int, float)):
        risk_parts.append(f"R/R {rr:.2f}")
    if sig.get("rsi14") is not None:
        risk_parts.append(f"RSI {sig.get('rsi14')}")
    add("risk", "風險報酬", risk_status, "，".join(risk_parts))

    action = sig.get("daily_action") or "avoid"
    if action in ("enter", "hold", "long_watch"):
        action_status = "pass"
    elif action in ("wait_pullback", "reduce"):
        action_status = "warn"
    else:
        action_status = "fail"
    action_detail = sig.get("daily_invalidation") or sig.get("daily_action_reason") or "等待下一次收盤確認"
    add(
        "action",
        sig.get("daily_action_label") or "明日動作",
        action_status,
        action_detail,
        sig.get("daily_key_price") or "",
    )

    if sig.get("old_wang_volume_low_price") is not None:
        volume_low_support = bool(sig.get("old_wang_volume_low_support"))
        add(
            "setup",
            "爆大量低點",
            "pass" if volume_low_support else "warn",
            "已守住" if volume_low_support else "尚待確認",
            _fmt_price(sig.get("old_wang_volume_low_price")),
        )

    return checklist


def _old_wang_market_index_state(rows: list[dict]) -> dict:
    if len(rows) < OLD_WANG_MARKET_MIN_ROWS:
        return {
            "ok": False,
            "holds_short_ma": False,
            "holds_volume_low": False,
            "breaks_volume_low": False,
            "reason": "資料不足",
        }

    closes = [r["close"] for r in rows]
    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    volume_low = _volume_low_context(rows, ma5)
    close = closes[-1]
    holds_short_ma = (
        ma5 is not None
        and ma10 is not None
        and close >= ma5
        and close >= ma10
    )
    volume_low_price = volume_low.get("price")
    breaks_volume_low = (
        isinstance(volume_low_price, (int, float))
        and rows[-1]["low"] < volume_low_price * 0.995
    )
    return {
        "ok": True,
        "holds_short_ma": holds_short_ma,
        "holds_volume_low": bool(volume_low.get("support")),
        "breaks_volume_low": breaks_volume_low,
        "volume_low_price": volume_low_price,
        "ma5": ma5,
        "ma10": ma10,
        "reason": volume_low.get("note", ""),
    }


def _old_wang_market_context_for_index(index_code: str, state: dict) -> dict:
    if state["breaks_volume_low"]:
        regime = "risk"
        market_filter = "block"
        reason = f"{index_code} 跌破爆大量低點，老王大盤濾網轉風險"
    elif state["holds_short_ma"] and state["holds_volume_low"]:
        regime = "strong"
        market_filter = "allow"
        reason = f"{index_code} 守 MA5/MA10 與爆大量低點"
    elif state["holds_short_ma"]:
        regime = "caution"
        market_filter = "caution"
        reason = f"{index_code} 守短均線，但爆大量低點支撐未完全確認"
    else:
        regime = "risk"
        market_filter = "block"
        reason = f"{index_code} 未能守住 MA5/MA10"

    return {
        "old_wang_market_regime": regime,
        "old_wang_market_filter": market_filter,
        "old_wang_market_source": index_code,
        "old_wang_market_reason": reason,
    }


def _old_wang_market_context(ohlcv: dict[str, list[dict]], base_filter: str) -> dict:
    index_codes = [code for code in ("TSE", "OTC") if ohlcv.get(code)]
    use_tse_otc = (
        len(index_codes) >= 2
        and all(len(ohlcv.get(code, [])) >= OLD_WANG_MARKET_MIN_ROWS for code in index_codes)
    )
    if use_tse_otc:
        states = {code: _old_wang_market_index_state(ohlcv[code]) for code in index_codes}
        by_exchange = {
            "TWSE": _old_wang_market_context_for_index("TSE", states["TSE"]),
            "TPEX": _old_wang_market_context_for_index("OTC", states["OTC"]),
        }
        if any(state["breaks_volume_low"] for state in states.values()):
            regime = "risk"
            market_filter = "block"
            reason = "TSE/OTC 跌破爆大量低點，老王大盤濾網轉風險"
        elif all(state["holds_short_ma"] and state["holds_volume_low"] for state in states.values()):
            regime = "strong"
            market_filter = "allow"
            reason = "TSE/OTC 同時守 MA5/MA10 與爆大量低點"
        elif all(state["holds_short_ma"] for state in states.values()):
            regime = "caution"
            market_filter = "caution"
            reason = "TSE/OTC 守短均線，但爆大量低點支撐未完全確認"
        else:
            regime = "risk"
            market_filter = "block"
            reason = "TSE/OTC 未能同時守住 MA5/MA10"

        return {
            "old_wang_market_regime": regime,
            "old_wang_market_filter": market_filter,
            "old_wang_market_source": "TSE/OTC",
            "old_wang_market_reason": reason,
            "old_wang_market_by_exchange": by_exchange,
        }

    benchmark_rows = ohlcv.get(BENCHMARK_CODE)
    if benchmark_rows and len(benchmark_rows) >= MIN_ROWS:
        state = _old_wang_market_index_state(benchmark_rows)
        if state["breaks_volume_low"]:
            regime = "risk"
            market_filter = "block"
            reason = f"{BENCHMARK_CODE} 跌破爆大量低點，老王大盤濾網轉風險"
        elif state["holds_short_ma"] and state["holds_volume_low"]:
            regime = "strong"
            market_filter = "allow"
            reason = f"{BENCHMARK_CODE} 守 MA5/MA10 與爆大量低點，代理老王大盤偏多"
        elif state["holds_short_ma"]:
            regime = "caution"
            market_filter = "caution" if base_filter != "block" else "block"
            reason = f"{BENCHMARK_CODE} 守 MA5/MA10，但爆大量低點支撐未完全確認"
        else:
            regime = "risk"
            market_filter = "block" if base_filter == "block" else "caution"
            reason = f"{BENCHMARK_CODE} 未守 MA5/MA10，老王大盤濾網轉保守"

        fallback_context = {
            "old_wang_market_regime": regime,
            "old_wang_market_filter": market_filter,
            "old_wang_market_source": BENCHMARK_CODE,
            "old_wang_market_reason": reason,
        }
        return {
            **fallback_context,
            "old_wang_market_by_exchange": {
                "TWSE": fallback_context,
                "TPEX": fallback_context,
            },
        }

    return {
        "old_wang_market_regime": "unknown",
        "old_wang_market_filter": "neutral",
        "old_wang_market_source": "none",
        "old_wang_market_reason": "缺少 TSE/OTC 與 0050 資料，老王大盤濾網採中性",
        "old_wang_market_by_exchange": {},
    }


def _market_context(ohlcv: dict[str, list[dict]]) -> dict:
    """
    建立大盤濾網 context。
    優先使用 0050；若缺資料，退回用 universe 中站上 MA60 的比例推估。
    """
    benchmark_rows = ohlcv.get(BENCHMARK_CODE)
    market_regime = "unknown"
    market_filter = "neutral"
    reason = "缺少 benchmark 資料，市場濾網採中性"

    if benchmark_rows and len(benchmark_rows) >= MIN_ROWS:
        closes = [r["close"] for r in benchmark_rows]
        ma20 = _ma(closes, 20)
        ma60 = _ma(closes, 60)
        close = closes[-1]
        if ma20 is not None and ma60 is not None:
            ma60_up = _slope_up([_ma(closes[:i], 60) or 0 for i in range(60, len(closes) + 1)], 20)
            if close > ma20 > ma60 and ma60_up:
                market_regime = "bull"
                market_filter = "allow"
                reason = f"{BENCHMARK_CODE} 站上 MA20/MA60，市場偏多"
            elif close < ma60:
                market_regime = "bear"
                market_filter = "block"
                reason = f"{BENCHMARK_CODE} 跌破 MA60，市場偏空"
            else:
                market_regime = "neutral"
                market_filter = "caution"
                reason = f"{BENCHMARK_CODE} 趨勢未完全轉強，市場中性"
    else:
        ok = 0
        up = 0
        for rows in ohlcv.values():
            closes = [r["close"] for r in rows]
            ma60 = _ma(closes, 60)
            if ma60 is None:
                continue
            ok += 1
            if closes[-1] > ma60:
                up += 1
        breadth = up / ok if ok else 0.0
        if breadth >= 0.6:
            market_regime = "bull"
            market_filter = "allow"
            reason = f"股票宇宙 {breadth:.0%} 站上 MA60，市場廣度偏多"
        elif breadth <= 0.4:
            market_regime = "bear"
            market_filter = "block"
            reason = f"股票宇宙僅 {breadth:.0%} 站上 MA60，市場廣度偏空"
        elif ok:
            market_regime = "neutral"
            market_filter = "caution"
            reason = f"股票宇宙 {breadth:.0%} 站上 MA60，市場廣度中性"

    old_wang_market = _old_wang_market_context(ohlcv, market_filter)
    return {
        "benchmark_code": BENCHMARK_CODE,
        "benchmark_rows": benchmark_rows,
        "market_regime": market_regime,
        "market_filter": market_filter,
        "market_reason": reason,
        **old_wang_market,
    }


def _load_market_notes() -> list[dict]:
    if not MARKET_NOTES_PATH.exists():
        return []
    try:
        raw = json.loads(MARKET_NOTES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _business_days_between(start: str, end: str) -> int:
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return 0
    if end_date <= start_date:
        return 0

    days = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days


def _market_note_text(note: dict) -> str:
    parts: list[str] = []
    for key in ("title", "headline", "position_guidance"):
        value = note.get(key)
        if value:
            parts.append(str(value))
    for key in ("market_actions", "index_notes", "stock_notes", "rules"):
        value = note.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if item)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _derive_market_note_playbook(note: dict) -> dict:
    text = _market_note_text(note)
    if "七成" in text:
        target_level = "七成"
        target_position_pct = 70
    elif "五成" in text:
        target_level = "五成"
        target_position_pct = 50
    elif "三成" in text:
        target_level = "三成"
        target_position_pct = 30
    else:
        target_level = "依系統水位"
        target_position_pct = None

    risk_level = str(note.get("risk_level") or "").lower()
    if target_position_pct and target_position_pct >= 70 and risk_level in {"strong", "risk_on", "bull"}:
        stance = "risk_on"
    elif target_position_pct and target_position_pct <= 30:
        stance = "risk_off"
    elif risk_level in {"risk", "block", "bear"}:
        stance = "risk_off"
    elif risk_level in {"caution", "neutral"}:
        stance = "balanced"
    else:
        stance = "risk_on" if target_position_pct and target_position_pct >= 70 else "balanced"

    sector_aliases = [
        ("記憶體", ("記憶體",)),
        ("AI / 半導體", ("AI / 半導體", "AI 半導體", "半導體")),
        ("ABF / 載板", ("ABF", "載板")),
        ("PCB / 散熱", ("PCB", "散熱")),
        ("被動元件", ("被動元件",)),
        ("電源周邊", ("電源周邊", "電源")),
    ]
    focus_sectors: list[str] = []
    for label, aliases in sector_aliases:
        if any(alias in text for alias in aliases):
            focus_sectors.append(label)

    risk_keywords = ("量縮", "跌破", "MA5", "MA10", "月線", "爆大量低點", "汰弱", "不追")
    risk_controls: list[str] = []
    for key in ("rules", "market_actions", "stock_notes"):
        values = note.get(key) or []
        if not isinstance(values, list):
            values = [values]
        for value in values:
            line = str(value).strip()
            if line and any(keyword in line for keyword in risk_keywords) and line not in risk_controls:
                risk_controls.append(line)

    stock_note_values = note.get("stock_notes") or []
    if not isinstance(stock_note_values, list):
        stock_note_values = [stock_note_values]
    code_text = " ".join(str(value) for value in stock_note_values if value) or text

    watch_codes: list[str] = []
    for code in re.findall(r"(?<!\d)(\d{4,6})(?!\d)", code_text):
        if len(code) > 4 and not code.startswith("00"):
            continue
        if code not in watch_codes:
            watch_codes.append(code)

    return {
        "target_level": target_level,
        "target_position_pct": target_position_pct,
        "stance": stance,
        "focus_sectors": focus_sectors,
        "risk_controls": risk_controls[:8],
        "watch_codes": watch_codes[:30],
    }


def _annotate_market_note(note: dict, as_of: str | None) -> dict:
    annotated = dict(note)
    note_date = str(annotated.get("date", ""))
    stale_trading_days = _business_days_between(note_date, as_of or note_date)
    is_stale = stale_trading_days > 2

    annotated["applies_to_as_of"] = as_of
    annotated["stale_trading_days"] = stale_trading_days
    annotated["is_stale"] = is_stale
    annotated["update_required"] = is_stale
    annotated["status_label"] = "舊筆記" if is_stale else "最新筆記"
    annotated["stale_reason"] = (
        f"距離訊號基準日 {stale_trading_days} 個交易日，請更新人工盤後筆記"
        if is_stale
        else ""
    )
    annotated["playbook"] = _derive_market_note_playbook(annotated)
    return annotated


def _market_note_for_date(as_of: str | None) -> dict | None:
    notes = sorted(
        _load_market_notes(),
        key=lambda item: str(item.get("date", "")),
        reverse=True,
    )
    if not notes:
        return None
    if not as_of:
        return _annotate_market_note(notes[0], as_of)
    for note in notes:
        date = str(note.get("date", ""))
        if date and date <= as_of:
            return _annotate_market_note(note, as_of)
    return None


def _sector_rotation_context(
    leader_groups: dict[str, list[str]],
    ohlcv: dict[str, list[dict]],
) -> dict:
    """
    老王 tag 第一版的族群輪動代理值。

    只使用既有 OHLCV 與 leaders.json，不新增外部資料依賴：
      - 族群 20/60 日平均報酬
      - 族群內站上 MA20 比例
      - 族群內突破近期壓力比例

    回傳 code -> best sector context，讓個股可以知道自己是否屬於目前強勢族群。
    """
    sectors: dict[str, dict] = {}
    by_code: dict[str, dict] = {}

    for sector, codes in leader_groups.items():
        stats: list[dict] = []
        for code in codes:
            rows = ohlcv.get(code, [])
            closes = [r["close"] for r in rows]
            if len(closes) < MIN_ROWS:
                continue
            ma20 = _ma(closes, 20)
            support, resistance = _support_resistance(rows, SR_LOOKBACK)
            ret20 = _return_pct(closes, 20)
            ret60 = _return_pct(closes, 60)
            close = closes[-1]
            stats.append({
                "code": code,
                "ret20": ret20 or 0.0,
                "ret60": ret60 or 0.0,
                "above_ma20": ma20 is not None and close > ma20,
                "breakout": resistance is not None and close > resistance,
            })

        if not stats:
            continue

        avg20 = sum(s["ret20"] for s in stats) / len(stats)
        avg60 = sum(s["ret60"] for s in stats) / len(stats)
        above_ratio = sum(1 for s in stats if s["above_ma20"]) / len(stats)
        breakout_ratio = sum(1 for s in stats if s["breakout"]) / len(stats)
        sector_score = round(max(0, min(100, 45 + avg20 * 1.2 + avg60 * 0.35
                                      + above_ratio * 25 + breakout_ratio * 15)))
        sector_info = {
            "sector": sector,
            "sector_score": sector_score,
            "is_hot": sector_score >= 65,
            "avg20_return": round(avg20, 2),
            "avg60_return": round(avg60, 2),
            "above_ma20_ratio": round(above_ratio, 2),
            "breakout_ratio": round(breakout_ratio, 2),
        }
        sectors[sector] = sector_info

        for code in codes:
            current = by_code.get(code)
            if current is None or sector_score > current.get("sector_score", 0):
                by_code[code] = sector_info

    return {"sectors": sectors, "by_code": by_code}


def _gap_context(rows: list[dict]) -> dict:
    """
    判斷今日是否相對昨日出現跳空。

    - 向上跳空：今日 low > 昨日 high，昨日高點到今日低點視為多方缺口支撐區
    - 向下跳空：今日 high < 昨日 low，今日高點到昨日低點視為空方缺口壓力區
    """
    if len(rows) < 2:
        return {
            "gap_type": "none",
            "gap_support": None,
            "gap_resistance": None,
            "gap_note": "",
            "bullish_gap_support": False,
            "bearish_gap_pressure": False,
        }

    prev = rows[-2]
    today = rows[-1]
    close = today["close"]

    if today["low"] > prev["high"]:
        support = round(prev["high"], 2)
        upper = round(today["low"], 2)
        holds_gap = close >= support and today["low"] >= support * 0.995
        return {
            "gap_type": "gap_up",
            "gap_support": support,
            "gap_resistance": None,
            "gap_note": f"向上跳空，缺口支撐約 {support}-{upper}",
            "bullish_gap_support": holds_gap,
            "bearish_gap_pressure": False,
        }

    if today["high"] < prev["low"]:
        lower = round(today["high"], 2)
        resistance = round(prev["low"], 2)
        pressure = close <= resistance and today["high"] <= resistance * 1.005
        return {
            "gap_type": "gap_down",
            "gap_support": None,
            "gap_resistance": resistance,
            "gap_note": f"向下跳空，缺口壓力約 {lower}-{resistance}",
            "bullish_gap_support": False,
            "bearish_gap_pressure": pressure,
        }

    return {
        "gap_type": "none",
        "gap_support": None,
        "gap_resistance": None,
        "gap_note": "",
        "bullish_gap_support": False,
        "bearish_gap_pressure": False,
    }


def _volume_low_context(rows: list[dict], ma5: float | None) -> dict:
    """
    老王圖例中的「爆大量低點」代理值。

    優先取最近 20 根中「成交量 >= 量 MA20 的 1.5 倍」且絕對成交量最大的爆量 K 棒，
    若沒有爆量 K，才退回最近 20 根最大量 K。
    把該日低點視為大量低點。
    若目前收盤與近低仍守在該低點上方，且最好仍站上 MA5，視為大量低點支撐成立。
    """
    lookback = 20
    volume_multiplier = 1.5
    if len(rows) < 10:
        return {
            "support": False,
            "price": None,
            "note": "",
        }

    volumes = [r["volume"] for r in rows]
    volume_ma20: list[float | None] = []
    for i in range(len(volumes)):
        if i < 19:
            volume_ma20.append(None)
        else:
            volume_ma20.append(sum(volumes[i - 19:i + 1]) / 20)

    start = max(0, len(rows) - lookback)
    candidates: list[tuple[dict, float]] = []
    for i in range(start, len(rows)):
        base_volume = volume_ma20[i]
        if base_volume is None or base_volume <= 0:
            continue
        ratio = rows[i]["volume"] / base_volume
        if ratio >= volume_multiplier:
            candidates.append((rows[i], ratio))

    is_explosion = bool(candidates)
    if candidates:
        peak, peak_ratio = max(candidates, key=lambda item: item[0]["volume"])
    else:
        window = rows[-lookback:]
        peak = max(window, key=lambda r: r["volume"])
        peak_index = rows.index(peak)
        base_volume = volume_ma20[peak_index]
        peak_ratio = peak["volume"] / base_volume if base_volume else None

    support_price = round(peak["low"], 2)
    recent_low = min(r["low"] for r in rows[-3:])
    close = rows[-1]["close"]
    support = (
        close >= support_price
        and recent_low >= support_price * 0.995
        and (ma5 is None or close >= ma5)
    )
    label = "爆大量低點" if is_explosion else "大量低點"
    ratio_text = f"（{peak_ratio:.2f}x）" if isinstance(peak_ratio, (int, float)) else ""
    note = f"{label} {support_price}{ratio_text} {'已守住' if support else '尚待確認'}"
    return {
        "support": support,
        "price": support_price,
        "high_price": round(peak["high"], 2),
        "high_breakout": close > peak["high"],
        "note": note,
        "date": peak["date"],
        "volume": peak["volume"],
        "volume_ratio": round(peak_ratio, 2) if isinstance(peak_ratio, (int, float)) else None,
        "is_explosion": is_explosion,
    }


def _previous_high_context(rows: list[dict], lookback: int = 20) -> dict:
    """
    老王 V2.1 的前高狀態。

    - breakout：收盤突破前高，代表壓力成功轉強。
    - failed：盤中突破但收盤未站上，視為回檔或假突破觀察。
    - near：接近前高但尚未突破。
    """
    window = rows[-(lookback + 1):-1]
    if not window or not rows:
        return {"state": "none", "price": None}

    previous_high = round(max(r["high"] for r in window), 2)
    today = rows[-1]
    if today["close"] > previous_high:
        state = "breakout"
    elif today["high"] > previous_high and today["close"] <= previous_high:
        state = "failed"
    elif today["close"] >= previous_high * 0.98:
        state = "near"
    else:
        state = "none"

    return {"state": state, "price": previous_high}


def _old_wang_support_context(
    close: float,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    ma60: float | None,
    previous_close: float | None = None,
) -> dict:
    """
    老王均線支撐狀態。

    核心：不預設高點。先看 5/10 是否短線止跌，再看 20/60 是否中長線破壞。
    只有 5、10、20、60 全部跌破，才視為前高/頭部型態風險升高。
    """
    mas = [ma5, ma10, ma20, ma60]
    available = [ma for ma in mas if ma is not None]
    break_count = sum(1 for ma in available if close < ma)
    all_broken = len(available) == 4 and break_count == 4
    short_stop = (
        ma5 is not None and ma10 is not None
        and close >= ma5 and close >= ma10
    )
    mid_trend_intact = (
        ma20 is not None and ma60 is not None
        and close >= ma20 and close >= ma60
    )
    all_ma_reclaim = (
        len(available) == 4
        and break_count == 0
        and previous_close is not None
        and any(previous_close < ma for ma in available)
    )

    if all_ma_reclaim:
        state = "all_ma_reclaim"
    elif all_broken:
        state = "all_ma_broken_previous_high_risk"
    elif short_stop and mid_trend_intact:
        state = "short_stop_trend_intact"
    elif short_stop:
        state = "short_stop"
    elif mid_trend_intact:
        state = "mid_trend_intact"
    else:
        state = "partial_ma_break"

    return {
        "state": state,
        "ma_break_count": break_count,
        "previous_high_risk": all_broken,
        "all_ma_reclaim": all_ma_reclaim,
    }


def _old_wang_flag(
    *,
    code: str,
    close: float,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    ma60: float | None,
    rsi14: float | None,
    vol_ratio: float | None,
    long_trend: str,
    market_filter: str,
    breakout: bool,
    breakdown: bool,
    strong_reversal: bool,
    holds_recent_low: bool,
    stage: str,
    rs_score: int | None,
    reward_risk_ratio: float | None,
    gap: dict,
    volume_low: dict,
    chip: dict,
    context: dict,
    previous_close: float | None = None,
    previous_high: dict | None = None,
    signal_data_as_of: str | None = None,
) -> dict:
    """
    老王大盤籌碼輪動 tag。

    這不是新的主訊號，不會覆蓋 core BUY/SELL/HOLD；它只標記：
      1. 大盤沒有封鎖做多
      2. 族群正在轉強
      3. 個股屬於突破、守低點反彈、或強勢族群補漲
    """
    sector_info = context.get("sector_rotation", {}).get("by_code", {}).get(code, {})
    sector = sector_info.get("sector", "")
    sector_score = sector_info.get("sector_score")
    sector_hot = bool(sector_info.get("is_hot"))

    score = 40
    reasons: list[str] = []
    signals: list[str] = []
    primary_signals: list[str] = []
    volume_signal = "unknown"
    ma_signal = "unknown"
    chip_signal = "unknown"
    support = _old_wang_support_context(close, ma5, ma10, ma20, ma60, previous_close=previous_close)
    previous_high_risk = bool(support["previous_high_risk"])
    all_ma_reclaim = bool(support.get("all_ma_reclaim"))
    previous_high = previous_high or {"state": "none", "price": None}
    previous_high_state = previous_high.get("state", "none")
    previous_high_price = previous_high.get("price")
    volume_high_breakout = bool(volume_low.get("high_breakout"))
    volume_high_price = volume_low.get("high_price")
    parabolic_ma10_hold = (
        ma10 is not None
        and ma20 is not None
        and close >= ma10
        and close >= ma20 * 1.12
    )

    if market_filter == "allow":
        score += 15
        reasons.append("大盤濾網允許做多")
    elif market_filter == "caution":
        score += 5
        reasons.append("大盤中性，僅做強勢族群")
    elif market_filter == "block":
        score -= 30
        reasons.append("大盤濾網封鎖做多")

    if sector_hot:
        score += 25
        reasons.append(f"族群輪動轉強（{sector} score:{sector_score}）")

    foreign = chip.get("foreign_net_buy")
    trust = chip.get("investment_trust_net_buy")
    retail_change = chip.get("retail_pct_change")
    major_change = chip.get("major_pct_change")
    chip_data_as_of = chip.get("data_as_of")
    chip_points = 0
    chip_reasons: list[str] = []
    if isinstance(foreign, (int, float)) and foreign > 0:
        chip_points += 6
        chip_reasons.append(f"外資買超 {foreign:,.0f} 張")
    elif isinstance(foreign, (int, float)) and foreign < 0:
        chip_points -= 4
        chip_reasons.append(f"外資賣超 {abs(foreign):,.0f} 張")
    if isinstance(trust, (int, float)) and trust > 0:
        chip_points += 6
        chip_reasons.append(f"投信買超 {trust:,.0f} 張")
    elif isinstance(trust, (int, float)) and trust < 0:
        chip_points -= 4
        chip_reasons.append(f"投信賣超 {abs(trust):,.0f} 張")
    if isinstance(retail_change, (int, float)) and retail_change < 0:
        chip_points += 6
        chip_reasons.append(f"散戶比例下降 {abs(retail_change):.2f}%")
    elif isinstance(retail_change, (int, float)) and retail_change > 0:
        chip_points -= 4
        chip_reasons.append(f"散戶比例上升 {retail_change:.2f}%")
    if isinstance(major_change, (int, float)) and major_change > 0:
        chip_points += 6
        chip_reasons.append(f"大戶比例上升 {major_change:.2f}%")
    elif isinstance(major_change, (int, float)) and major_change < 0:
        chip_points -= 4
        chip_reasons.append(f"大戶比例下降 {abs(major_change):.2f}%")
    if chip_reasons and isinstance(chip_data_as_of, str) and chip_data_as_of:
        chip_reasons.append(f"籌碼資料日 {chip_data_as_of}")
        try:
            chip_date = datetime.strptime(chip_data_as_of, "%Y-%m-%d").date()
            signal_date = (
                datetime.strptime(signal_data_as_of, "%Y-%m-%d").date()
                if isinstance(signal_data_as_of, str) and signal_data_as_of
                else None
            )
        except ValueError:
            signal_date = None
        if signal_date is not None and (signal_date - chip_date).days >= 4:
            chip_reasons.append("籌碼資料偏舊，僅作參考")

    if chip_points >= 8:
        chip_signal = "supportive"
        signals.append("chip_support")
        reasons.append("籌碼支持：" + "；".join(chip_reasons))
    elif chip_points <= -8:
        chip_signal = "against"
        reasons.append("籌碼偏逆風：" + "；".join(chip_reasons))
    elif chip_reasons:
        chip_signal = "mixed"
        reasons.append("籌碼中性：" + "；".join(chip_reasons))
    score += chip_points

    if long_trend == "up":
        score += 15
        reasons.append("個股長線站上 MA60")
    elif long_trend == "down":
        score -= 30
        reasons.append("個股長線仍在 MA60 下方")

    if ma5 is not None and ma10 is not None:
        if close > ma5 > ma10:
            score += 18
            ma_signal = "ma5_above_ma10"
            signals.append("ma5_ma10_wave")
            reasons.append("波段結構偏多：收盤站上 MA5，且 MA5 在 MA10 上方")
        elif close > ma10:
            score += 8
            ma_signal = "above_ma10"
            reasons.append("波段仍站上 MA10")
        elif (
            ma20 is not None
            and close >= ma5
            and close >= ma20
            and close >= ma10 * (1 - OLD_WANG_MA10_TOLERANCE_PCT)
        ):
            score += 3
            ma_signal = "near_ma10"
            reasons.append("收盤貼近 MA10（0.2% 內），以準站回觀察")
        else:
            score -= 15
            ma_signal = "below_ma10"
            reasons.append("波段跌破 MA10，老王 tag 降權")

    if support["state"] == "all_ma_reclaim":
        score += 18
        signals.append("all_ma_reclaim")
        primary_signals.append("all_ma_reclaim")
        reasons.append("重新站回 5/10/20/60 所有均線，形成四海遊龍翻多")
    elif support["state"] == "short_stop_trend_intact":
        score += 15
        reasons.append("5/10 短線止跌且 20/60 中長線未破，不預設高點")
    elif support["state"] == "short_stop":
        score += 8
        reasons.append("5/10 短線止跌，先觀察波段續航")
    elif support["state"] == "partial_ma_break":
        score -= 8
        reasons.append(f"已有 {support['ma_break_count']} 條均線跌破，等待 5/10 止跌")
    elif previous_high_risk:
        score -= 40
        reasons.append("5/10/20/60 全部跌破，前高型態風險成立")

    if ma20 is not None and close > ma20:
        score += 10
        reasons.append("短線站上 MA20")

    if breakout:
        score += 20
        signals.append("leader_breakout")
        primary_signals.append("leader_breakout")
        reasons.append("突破近期壓力，符合強勢股突破觀察")

    if previous_high_state == "breakout":
        score += 18
        signals.append("previous_high_breakout")
        primary_signals.append("previous_high_breakout")
        reasons.append(f"突破前高壓力 {previous_high_price}，轉為強勢延伸")
    elif previous_high_state == "failed":
        score -= 8
        signals.append("previous_high_failed")
        reasons.append(f"盤中突破前高 {previous_high_price} 但收盤未站上，先視為回檔觀察")
    elif previous_high_state == "near":
        signals.append("previous_high_near")
        reasons.append(f"接近前高壓力 {previous_high_price}，不追高，等突破或回測")

    if volume_high_breakout:
        score += 16
        signals.append("volume_high_breakout")
        primary_signals.append("volume_high_breakout")
        reasons.append(f"突破爆大量高點 {volume_high_price}，代表換手後續攻")

    if strong_reversal:
        score += 20
        signals.append("ma60_reclaim")
        primary_signals.append("ma60_reclaim")
        reasons.append("重新站回 MA60，符合跌深後轉強觀察")

    if holds_recent_low and rsi14 is not None and rsi14 <= 75:
        score += 12
        signals.append("low_hold_rebound")
        reasons.append("守住短線低點後反彈，符合低點不破觀察")

    if volume_low.get("support"):
        score += 18
        signals.append("volume_low_support")
        primary_signals.append("volume_low_support")
        reasons.append(f"{volume_low.get('note')}，符合爆大量低點支撐")

    if parabolic_ma10_hold:
        score += 8
        signals.append("parabolic_ma10_hold")
        reasons.append("短線噴出但仍守 MA10，噴出行情支撐改看十日均線")

    catch_up = (
        sector_hot
        and ma20 is not None and close > ma20
        and rs_score is not None and 45 <= rs_score <= 85
        and not breakout
    )
    if catch_up:
        score += 15
        signals.append("sector_catch_up")
        primary_signals.append("sector_catch_up")
        reasons.append("強勢族群內補漲候選，尚非過度領先")

    if vol_ratio is not None:
        if vol_ratio >= 1.2:
            score += 12
            volume_signal = "confirmed"
            reasons.append(f"量能確認：高於均量（{vol_ratio:.1f}x）")
        elif vol_ratio < 0.8:
            score -= 12
            volume_signal = "weak"
            reasons.append(f"量能不足（{vol_ratio:.1f}x），避免只看單根 K 線")
        else:
            volume_signal = "neutral"

    bullish_gap_support = bool(gap.get("bullish_gap_support"))
    bearish_gap_pressure = bool(gap.get("bearish_gap_pressure"))
    if bullish_gap_support:
        score += 18
        signals.append("gap_up_support")
        primary_signals.append("gap_up_support")
        reasons.append(f"向上跳空且缺口未回補，形成多方支撐（{gap.get('gap_support')}）")
    elif gap.get("gap_type") == "gap_up":
        score += 5
        reasons.append(gap.get("gap_note", "向上跳空，觀察缺口是否守住"))

    if bearish_gap_pressure:
        score -= 30
        reasons.append(f"向下跳空形成空方壓力（{gap.get('gap_resistance')}），老王 tag 降權")
    elif gap.get("gap_type") == "gap_down":
        score -= 12
        reasons.append(gap.get("gap_note", "向下跳空，先觀察缺口壓力"))

    if rsi14 is not None and rsi14 > 82 and previous_high_risk:
        score -= 18
        reasons.append(f"RSI 過熱（{rsi14}）且均線全破，前高風險加重")
    elif rsi14 is not None and rsi14 > 82:
        reasons.append(f"RSI 偏高（{rsi14}），但均線未全破，不預設為高點")

    if reward_risk_ratio is not None and reward_risk_ratio < 1.2:
        score -= 12
        reasons.append(f"風險報酬不足（R/R:{reward_risk_ratio}）")

    if breakdown:
        score -= 45
        reasons.append("跌破支撐，不符合老王強勢/輪動條件")

    if stage == "stage_4":
        score -= 30
        reasons.append("Stage 4 主跌段，排除")

    raw_score = score
    if raw_score >= 70:
        calibrated_score = 70 + round((raw_score - 70) * 0.22)
    else:
        calibrated_score = raw_score

    score = max(0, min(96, round(calibrated_score)))
    stands_above_short_mas = (
        ma5 is not None
        and ma10 is not None
        and ma20 is not None
        and close >= ma5
        and close >= ma10 * (1 - OLD_WANG_MA10_TOLERANCE_PCT)
        and close >= ma20
    )
    has_strong_setup = any(
        signal in primary_signals
        for signal in (
            "all_ma_reclaim",
            "gap_up_support",
            "previous_high_breakout",
            "volume_high_breakout",
            "volume_low_support",
            "leader_breakout",
        )
    )
    market_block_override = (
        market_filter == "block"
        and sector_hot
        and stands_above_short_mas
        and has_strong_setup
        and raw_score >= 70
    )
    chip_against_override = (
        chip_signal == "against"
        and stands_above_short_mas
        and has_strong_setup
        and raw_score >= 90
    )
    volume_or_structure_ok = (
        volume_signal == "confirmed"
        or bullish_gap_support
        or volume_low.get("support")
        or (
            stands_above_short_mas
            and any(signal in primary_signals for signal in ("all_ma_reclaim", "previous_high_breakout", "volume_high_breakout"))
        )
    )
    flag = (
        raw_score >= 70
        and (market_filter != "block" or market_block_override)
        and long_trend != "down"
        and not breakdown
        and sector != "ETF"
        and bool(primary_signals)
        and not bearish_gap_pressure
        and volume_or_structure_ok
        and ma_signal != "below_ma10"
        and not previous_high_risk
        and (chip_signal != "against" or chip_against_override)
    )
    if market_block_override:
        reasons.append("大盤風險下僅列強型態觀察")
    if chip_against_override:
        reasons.append("籌碼逆風，降級觀察")

    badges: list[str] = []
    if sector_hot:
        badges.append("族群轉強")
    if ma_signal == "ma5_above_ma10":
        badges.append("MA5/10多頭")
    elif support["state"] in ("short_stop_trend_intact", "short_stop"):
        badges.append("5/10止跌")
    if "volume_low_support" in signals:
        badges.append("守爆量低")
    if "volume_high_breakout" in signals:
        badges.append("爆量高突破")
    if "parabolic_ma10_hold" in signals:
        badges.append("噴出看MA10")
    if "all_ma_reclaim" in signals:
        badges.append("四海遊龍")
    if "previous_high_breakout" in signals:
        badges.append("突破前高")
    elif "previous_high_failed" in signals:
        badges.append("前高回檔")
    if "gap_up_support" in signals:
        badges.append("跳空支撐")
    if "leader_breakout" in signals:
        badges.append("突破壓力")
    if "ma60_reclaim" in signals:
        badges.append("站回MA60")
    if "low_hold_rebound" in signals:
        badges.append("低點不破")
    if "sector_catch_up" in signals:
        badges.append("族群補漲")
    if volume_signal == "confirmed":
        badges.append("量能確認")
    elif volume_signal == "weak":
        badges.append("量能不足")
    if chip_signal == "supportive":
        badges.append("籌碼支持")
    elif chip_signal == "against":
        badges.append("籌碼逆風")
    if previous_high_risk:
        badges.append("前高風險")

    badges = list(dict.fromkeys(badges))[:8]

    return {
        "old_wang_flag": flag,
        "old_wang_tag": OLD_WANG_TAG if flag else "",
        "old_wang_score": score,
        "old_wang_raw_score": round(raw_score),
        "old_wang_signal": ",".join(dict.fromkeys(signals)),
        "old_wang_badges": badges,
        "old_wang_reason": "；".join(reasons) if reasons else "",
        "old_wang_sector": sector,
        "sector_score": sector_score,
        "old_wang_volume_signal": volume_signal,
        "old_wang_gap_type": gap.get("gap_type", "none"),
        "old_wang_gap_support": gap.get("gap_support"),
        "old_wang_gap_resistance": gap.get("gap_resistance"),
        "old_wang_gap_note": gap.get("gap_note", ""),
        "old_wang_ma_signal": ma_signal,
        "old_wang_volume_low_support": bool(volume_low.get("support")),
        "old_wang_volume_low_price": volume_low.get("price"),
        "old_wang_support_state": support["state"],
        "old_wang_ma_break_count": support["ma_break_count"],
        "old_wang_previous_high_risk": previous_high_risk,
        "old_wang_chip_signal": chip_signal,
        "old_wang_previous_high_state": previous_high_state,
        "old_wang_previous_high_price": previous_high_price,
        "old_wang_volume_high_breakout": volume_high_breakout,
        "old_wang_volume_high_price": volume_high_price,
        "old_wang_all_ma_reclaim": all_ma_reclaim,
        "old_wang_parabolic_ma10_hold": parabolic_ma10_hold,
    }


def _latest_data_date(codes: list[str], ohlcv: dict[str, list[dict]]) -> str | None:
    dates = [ohlcv[code][-1]["date"] for code in codes if ohlcv.get(code)]
    return max(dates) if dates else None


# ---------------------------------------------------------------------------
# 支撐壓力（第一版：區間高低點）
# ---------------------------------------------------------------------------

def _support_resistance(rows: list[dict], lookback: int = SR_LOOKBACK) -> tuple[float | None, float | None]:
    """
    壓力 = 最近 lookback 根 K 棒（不含今日）的最高點
    支撐 = 最近 lookback 根 K 棒（不含今日）的最低點
    使用區間判斷（±2%/±5%），非單點比對。
    """
    window = rows[-(lookback + 1):-1]
    if not window:
        return None, None
    support    = round(min(r["low"]  for r in window), 2)
    resistance = round(max(r["high"] for r in window), 2)
    return support, resistance


# ---------------------------------------------------------------------------
# 長短線趨勢
# ---------------------------------------------------------------------------

def _long_trend(closes: list[float], ma60: float | None) -> str:
    """
    長線趨勢（MA60 基準）：
      "up"      — 收盤站上 MA60
      "down"    — 收盤跌破 MA60
      "neutral" — 資料不足
    """
    if ma60 is None:
        return "neutral"
    close = closes[-1]
    if close > ma60:
        return "up"
    elif close < ma60:
        return "down"
    return "neutral"


def _short_trend(closes: list[float], ma20: float | None, ma60: float | None) -> str:
    """
    短線趨勢（MA20 基準）：
      "up"      — 收盤站上 MA20 且 MA20 > MA60（多頭排列）
      "down"    — 收盤跌破 MA20
      "neutral" — 其他
    """
    if ma20 is None:
        return "neutral"
    close = closes[-1]
    if close < ma20:
        return "down"
    if ma60 is not None and ma20 > ma60:
        return "up"
    return "neutral"


# ---------------------------------------------------------------------------
# 訊號計算主體
# ---------------------------------------------------------------------------

def _resolve_stock_timeout_seconds(env: Mapping[str, str] | None = None) -> float:
    source = os.environ if env is None else env
    raw_value = source.get("SIGNAL_STOCK_TIMEOUT_SECONDS")
    if raw_value is None or not str(raw_value).strip():
        return DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        log.warning(
            "SIGNAL_STOCK_TIMEOUT_SECONDS=%r is invalid; using %.1f seconds",
            raw_value,
            DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS,
        )
        return DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS
    if value <= 0:
        log.warning(
            "SIGNAL_STOCK_TIMEOUT_SECONDS must be positive; using %.1f seconds",
            DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS,
        )
        return DEFAULT_SIGNAL_STOCK_TIMEOUT_SECONDS
    return value


def _build_unavailable_signal(
    code: str,
    rows: list[dict],
    context: dict | None,
    *,
    reason: str,
    calculation_status: str,
    calculation_error: str,
) -> dict:
    context = context or {}
    market_filter = context.get("market_filter", "neutral")
    if calculation_status == "data_missing":
        fundamental_guard = evaluate_fundamental_guard(
            code,
            context.get("fundamentals", {}).get(code),
        )
        position_size_note = "資料不足，不建議新進場"
        price_plan_note = "資料不足，無法估算進出場價格"
        risk_note = "資料不足，無法分析"
    else:
        fundamental_guard = {
            "fundamental_flag": False,
            "fundamental_tag": "",
            "fundamental_score": 0,
            "fundamental_signal": "",
            "fundamental_reason": "計算未完成，不評估基本面策略",
            "fundamental_data_ok": False,
            "fundamental_data_missing_reason": reason,
            "fundamental_quality_score": 0,
            "fundamental_value_score": 0,
            "fundamental_safety_score": 0,
            "fundamental_growth_score": 0,
            "fundamental_data_completeness_pct": 0,
            "fundamental_missing_fields": [],
            "fundamental_scored_groups": [],
        }
        position_size_note = "計算未完成，不建議新進場"
        price_plan_note = "計算未完成，無法估算進出場價格"
        risk_note = "計算未完成，不可使用此列做交易判斷"

    closes = [row["close"] for row in rows]
    return {
        "code": code,
        "name": _stock_name(code),
        "data_ok": False,
        "data_missing": True,
        "calculation_status": calculation_status,
        "calculation_error": calculation_error,
        "signal": "DATA_MISSING",
        "internal_signal": "DATA_MISSING",
        "entry_type": "",
        "score": 0,
        "trend_score": 0,
        "entry_score": 0,
        "risk_score": 0,
        "position_size_pct": 0,
        "position_size_note": position_size_note,
        "holding_shares": 0,
        "holding_avg_cost": None,
        "holding_position_pct": 0.0,
        "long_trend": "unknown",
        "short_trend": "unknown",
        "market_regime": context.get("market_regime", "unknown"),
        "market_filter": market_filter,
        "old_wang_market_regime": context.get("old_wang_market_regime", "unknown"),
        "old_wang_market_filter": context.get("old_wang_market_filter", market_filter),
        "old_wang_market_source": context.get("old_wang_market_source", ""),
        "old_wang_market_reason": context.get("old_wang_market_reason", ""),
        "relative_strength_score": None,
        "relative_strength_60d": None,
        "relative_strength_120d": None,
        "stage": "unknown",
        "strategy_tags": "",
        "strategy_alignment": "no_alignment",
        "aligned_strategies": [],
        "strategy_conflict_notes": [],
        "old_wang_flag": False,
        "old_wang_tag": "",
        "old_wang_score": 0,
        "old_wang_signal": "",
        "old_wang_badges": [],
        "old_wang_reason": "",
        "old_wang_sector": "",
        "sector_score": None,
        "old_wang_volume_signal": "unknown",
        "old_wang_gap_type": "none",
        "old_wang_gap_support": None,
        "old_wang_gap_resistance": None,
        "old_wang_gap_note": "",
        "old_wang_ma_signal": "unknown",
        "old_wang_volume_low_support": False,
        "old_wang_volume_low_price": None,
        "old_wang_support_state": "unknown",
        "old_wang_ma_break_count": 0,
        "old_wang_previous_high_risk": False,
        "old_wang_chip_signal": "unknown",
        "old_wang_raw_score": 0,
        "old_wang_previous_high_state": "none",
        "old_wang_previous_high_price": None,
        "old_wang_volume_high_breakout": False,
        "old_wang_volume_high_price": None,
        "old_wang_all_ma_reclaim": False,
        "old_wang_parabolic_ma10_hold": False,
        "steady_momentum_flag": False,
        "steady_momentum_tag": "",
        "steady_momentum_score": 0,
        "steady_momentum_signal": "",
        "steady_momentum_reason": "資料不足，不評估穩健動能策略",
        **fundamental_guard,
        "entry_price_low": None,
        "entry_price_high": None,
        "data_as_of": rows[-1]["date"] if rows else None,
        "stop_price": None,
        "target_price": None,
        "risk_pct": None,
        "reward_pct": None,
        "reward_risk_ratio": None,
        "price_plan_note": price_plan_note,
        "support_source": "",
        "resistance_source": "",
        "entry_source": "",
        "stop_source": "",
        "target_source": "",
        "support_price": None,
        "resistance_price": None,
        "pattern_type": "none",
        "pattern_status": "none",
        "no_buy_reason": reason,
        "risk_note": risk_note,
        "close": closes[-1] if closes else None,
        "ma5": None,
        "ma10": None,
        "ma20": None,
        "ma60": None,
        "rsi14": None,
        "volume": rows[-1]["volume"] if rows else None,
        "vol_ratio": None,
        "reasons": [reason],
    }


def _compute_signal_task(args: tuple[str, list[dict], dict, dict]) -> dict:
    return _compute_signal(*args)


def _spawn_signal_pool():
    return multiprocessing.get_context("spawn").Pool(processes=1)


def _run_signal_batch(
    codes: list[str],
    ohlcv: dict[str, list[dict]],
    positions: dict,
    context: dict,
    *,
    timeout_seconds: float,
    pool_factory=None,
) -> list[dict]:
    factory = pool_factory or _spawn_signal_pool
    pool = factory()
    signals: list[dict] = []

    try:
        for code in codes:
            rows = ohlcv.get(code, [])
            result = pool.apply_async(
                _compute_signal_task,
                ((code, rows, positions, context),),
            )
            try:
                signals.append(result.get(timeout=timeout_seconds))
            except multiprocessing.TimeoutError:
                log.error(
                    "signal timeout code=%s timeout=%ss step=compute_signal; "
                    "continue with next stock",
                    code,
                    f"{timeout_seconds:g}",
                )
                pool.terminate()
                pool.join()
                pool = None

                reason = f"訊號計算逾時（超過 {timeout_seconds:g} 秒）"
                signals.append(
                    _build_unavailable_signal(
                        code,
                        rows,
                        context,
                        reason=reason,
                        calculation_status="timeout",
                        calculation_error=reason,
                    )
                )
                pool = factory()
            except BaseException:
                pool.terminate()
                pool.join()
                pool = None
                raise

        pool.close()
        pool.join()
        pool = None
        return signals
    finally:
        if pool is not None:
            pool.terminate()
            pool.join()


def _compute_signal(
    code: str,
    rows: list[dict],
    positions: dict,
    context: dict | None = None,
) -> dict:
    """
    計算訊號與指標，回傳包含完整欄位的 dict。

    外部 signal 欄位維持 BUY/SELL/HOLD/DATA_MISSING（API 契約）。
    內部 7 狀態保存在 internal_signal 欄位（供 universe_report 觀察用）。

    訊號優先順序（內部）：
      1. DATA_MISSING  — 資料不足
      2. invalidated   — 長線偏空且跌破支撐（雙重確認）
      3. exit_warning  — 長線偏空 OR 跌破支撐
      4. take_profit_warning — RSI 過熱 / 接近壓力
      5. hold          — 持股且長線未轉弱
      6. entry_confirmed — 長線多頭 + 突破壓力 + 放量
      7. ready_to_enter  — 長線多頭 + 接近 MA20 / 支撐
      8. watchlist     — 其他（觀察中）
    """
    name   = _stock_name(code)
    closes = [r["close"] for r in rows]
    context = context or {}
    market_regime = context.get("market_regime", "unknown")
    market_filter = context.get("market_filter", "neutral")
    stock_markets = context.get("stock_markets") or {}
    exchange = derive_market(code, stock_markets.get(code))
    old_wang_exchange_context = (
        context.get("old_wang_market_by_exchange", {}).get(exchange)
        if exchange in ("TWSE", "TPEX")
        else None
    )
    old_wang_market_regime = (
        old_wang_exchange_context.get("old_wang_market_regime")
        if old_wang_exchange_context
        else context.get("old_wang_market_regime", "unknown")
    )
    old_wang_market_filter = (
        old_wang_exchange_context.get("old_wang_market_filter")
        if old_wang_exchange_context
        else context.get("old_wang_market_filter", market_filter)
    )
    old_wang_market_source = (
        old_wang_exchange_context.get("old_wang_market_source")
        if old_wang_exchange_context
        else context.get("old_wang_market_source", "")
    )
    old_wang_market_reason = (
        old_wang_exchange_context.get("old_wang_market_reason")
        if old_wang_exchange_context
        else context.get("old_wang_market_reason", "")
    )

    # ── DATA_MISSING ──────────────────────────────────────────────────────
    if len(closes) < MIN_ROWS:
        reason = f"資料不足（僅 {len(closes)} 日，需 {MIN_ROWS} 日）"
        return _build_unavailable_signal(
            code,
            rows,
            context,
            reason=reason,
            calculation_status="data_missing",
            calculation_error=reason,
        )

    # ── 計算指標 ──────────────────────────────────────────────────────────
    close  = closes[-1]
    ma5    = _ma(closes, 5)
    ma10   = _ma(closes, 10)
    ma20   = _ma(closes, 20)
    ma60   = _ma(closes, 60)
    rsi14  = _rsi(closes, RSI_PERIOD)

    avg_v     = _avg_vol([r["volume"] for r in rows], 20)
    vol_ratio = round(rows[-1]["volume"] / avg_v, 2) if avg_v > 0 else None

    support_price, resistance_price = _support_resistance(rows, SR_LOOKBACK)
    long_t  = _long_trend(closes, ma60)
    short_t = _short_trend(closes, ma20, ma60)
    stage = _stage_from_closes(closes, ma60)
    data_as_of = rows[-1]["date"]
    gap = _gap_context(rows)
    volume_low = _volume_low_context(rows, ma5)
    previous_high = _previous_high_context(rows)
    chip = {} if context.get("core_backtest") else get_chip_metrics(code)

    rs_score, rs60, rs120 = _relative_strength(
        closes,
        context.get("benchmark_rows"),
    )
    support_source = "recent_20d_low" if support_price is not None else ""
    resistance_source = "recent_20d_high" if resistance_price is not None else ""
    (
        stop_price,
        target_price,
        risk_pct,
        reward_pct,
        reward_risk_ratio,
        stop_source,
        target_source,
    ) = _reward_risk(
        close, support_price, resistance_price, ma20, ma60
    )

    is_holding = code in positions.get("holdings", {})

    # ── 條件旗標 ──────────────────────────────────────────────────────────
    breakout = (
        resistance_price is not None
        and close > resistance_price
        and vol_ratio is not None and vol_ratio >= 1.5
    )
    breakdown = (
        support_price is not None
        and close < support_price * 0.98
    )
    near_support = (
        support_price is not None
        and support_price * 0.98 <= close <= support_price * 1.05
    )
    near_ma20 = (
        ma20 is not None
        and ma20 <= close <= ma20 * 1.05
    )
    recaptures_ma5 = (
        ma5 is not None
        and len(closes) >= 2
        and closes[-2] <= ma5
        and close > ma5
    )
    holds_recent_low = (
        len(rows) >= 4
        and rows[-1]["low"] >= min(r["low"] for r in rows[-4:-1]) * 0.995
    )
    pullback_quality = (
        (near_ma20 or near_support)
        and (short_t == "up" or recaptures_ma5 or holds_recent_low)
        and (vol_ratio is None or vol_ratio >= 0.8 or recaptures_ma5)
        and (rsi14 is None or 40 <= rsi14 <= 70)
        and (reward_risk_ratio is None or reward_risk_ratio >= 1.5)
    )
    strong_reversal = (
        len(closes) >= 2
        and ma60 is not None
        and close > ma60
        and (
            closes[-2] < ma60
            or close >= closes[-2] * 1.07
        )
        and (vol_ratio is None or vol_ratio >= 1.0)
    )
    breakout_rr_ok = reward_risk_ratio is None or reward_risk_ratio >= 1.2
    breakout_rsi_ok = rsi14 is None or rsi14 <= 75
    breakout_entry_quality = breakout_rr_ok and breakout_rsi_ok
    ma60_break_pct = (
        round((ma60 - close) / ma60 * 100, 2)
        if ma60 is not None and close < ma60 and ma60 > 0
        else 0.0
    )
    ma60_prior = _ma(closes[:-20], 60) if len(closes) >= 80 else None
    ma60_down = ma60 is not None and ma60_prior is not None and ma60 < ma60_prior
    ma60_minor_break = (
        ma60 is not None
        and close < ma60
        and ma60_break_pct <= 1.0
        and not ma60_down
    )
    short_ma_hold = (
        ma5 is not None
        and ma10 is not None
        and close >= ma5
        and close >= ma10
    )
    overheated = rsi14 is not None and rsi14 > 75
    near_hot_resistance = (
        resistance_price is not None
        and close >= resistance_price * 0.98
        and rsi14 is not None
        and rsi14 > 70
    )
    old_wang = _old_wang_flag(
        code=code,
        close=close,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        rsi14=rsi14,
        vol_ratio=vol_ratio,
        long_trend=long_t,
        market_filter=old_wang_market_filter,
        breakout=breakout,
        breakdown=breakdown,
        strong_reversal=strong_reversal,
        holds_recent_low=holds_recent_low,
        stage=stage,
        rs_score=rs_score,
        reward_risk_ratio=reward_risk_ratio,
        gap=gap,
        volume_low=volume_low,
        chip=chip,
        context=context,
        previous_close=closes[-2] if len(closes) >= 2 else None,
        previous_high=previous_high,
        signal_data_as_of=rows[-1]["date"] if rows else None,
    )
    fundamental_guard = evaluate_fundamental_guard(
        code,
        context.get("fundamentals", {}).get(code),
    )

    # ── Score（可追溯來源）───────────────────────────────────────────────
    score   = 50
    reasons: list[str] = []
    risks:   list[str] = []

    if long_t == "up":
        score += 20
        reasons.append("長線趨勢偏多（收盤站上 MA60）")
    elif long_t == "down":
        score -= 20
        reasons.append(f"長線趨勢偏空（收盤 {close} 跌破 MA60 {ma60}）")
        risks.append("長線偏空，多頭訊號需降權")

    if short_t == "up":
        score += 10
        reasons.append("短線趨勢偏多（MA20 站上 MA60，多頭排列）")
    elif short_t == "down":
        score -= 10
        reasons.append(f"短線趨勢偏空（收盤低於 MA20 {ma20}）")

    if near_support and not breakdown:
        score += 15
        reasons.append(f"接近支撐區（支撐:{support_price}，誤差≤5%）")

    if resistance_price is not None and close >= resistance_price * 0.98:
        score -= 10
        reasons.append(f"接近壓力區（壓力:{resistance_price}）")
        risks.append("接近壓力，突破需確認量能")

    if breakout:
        score += 20
        reasons.append(f"突破壓力 {resistance_price}，量能放大（{vol_ratio:.1f}x）")

    if strong_reversal:
        score += 15
        reasons.append("強勢反轉：收盤重新站上 MA60，且單日漲幅/量能明顯轉強")

    if breakdown:
        score -= 20
        reasons.append(f"跌破支撐 {support_price} 達 2% 以上")
        risks.append(f"跌破支撐 {support_price}，下行風險加大")

    if vol_ratio is not None and vol_ratio >= 1.5:
        score += 10
        reasons.append(f"量能放大（{vol_ratio:.1f}x 均量）")
    elif vol_ratio is not None and vol_ratio < 0.8:
        reasons.append(f"量能偏低（{vol_ratio:.1f}x 均量）")

    if rsi14 is not None:
        if 40 <= rsi14 <= 60:
            score += 5
            reasons.append(f"RSI 處於健康區間（{rsi14}）")
        elif rsi14 > 75:
            score -= 15
            reasons.append(f"RSI 過熱（{rsi14}），注意超買風險")
            risks.append("RSI 偏高，可能短期過熱")
        elif rsi14 < 30:
            score += 10
            reasons.append(f"RSI 接近超賣（{rsi14}），注意反彈機會")

    # ── 型態辨識（signal_rules.md §6：底部型態加分，M頂扣分）─────────────
    pat = _detect_pattern(rows)
    pattern_type   = pat.pattern_type
    pattern_status = pat.pattern_status

    if pat.pattern_type == "w_bottom":
        if pat.pattern_status == "forming":
            score += 10
            reasons.append(f"W底形成中（頸線 {pat.neckline}，待突破確認）")
        elif pat.pattern_status == "confirmed":
            score += 20
            reasons.append(f"W底確認突破頸線 {pat.neckline}")
        elif pat.pattern_status == "failed":
            risks.append(pat.note)
    elif pat.pattern_type == "m_top":
        if pat.pattern_status == "forming":
            score -= 10
            risks.append(f"M頂形成中（頸線 {pat.neckline}，注意跌破）")
        elif pat.pattern_status == "confirmed":
            score -= 20
            risks.append(f"M頂確認跌破頸線 {pat.neckline}")
        elif pat.pattern_status == "failed":
            reasons.append(pat.note)
    elif pat.pattern_type == "head_and_shoulders_top":
        if pat.pattern_status == "forming":
            score -= 10
            risks.append(f"頭肩頂形成中（頸線 {pat.neckline}，注意跌破）")
        elif pat.pattern_status == "confirmed":
            score -= 20
            risks.append(f"頭肩頂確認跌破頸線 {pat.neckline}")
        elif pat.pattern_status == "failed":
            reasons.append(pat.note)
    elif pat.pattern_type == "head_and_shoulders_bottom":
        if pat.pattern_status == "forming":
            score += 10
            reasons.append(f"頭肩底形成中（頸線 {pat.neckline}，待突破確認）")
        elif pat.pattern_status == "confirmed":
            score += 20
            reasons.append(f"頭肩底確認突破頸線 {pat.neckline}")
        elif pat.pattern_status == "failed":
            risks.append(pat.note)

    # ── 專業濾網：市場環境 / 相對強度 / 階段 / 風險報酬 ────────────────
    if market_regime == "bull":
        score += 5
        reasons.append(context.get("market_reason", "市場環境偏多"))
    elif market_regime == "bear":
        score -= 15
        risks.append(context.get("market_reason", "市場環境偏空，做多需降權"))
    elif market_regime == "neutral":
        risks.append(context.get("market_reason", "市場環境中性，突破需更嚴格確認"))

    if rs_score is not None:
        if rs_score >= 70:
            score += 10
            reasons.append(f"相對強度優於大盤（RS60:{rs60}%，RS120:{rs120}%）")
        elif rs_score <= 35:
            score -= 10
            risks.append(f"相對強度弱於大盤（RS60:{rs60}%，RS120:{rs120}%）")

    if stage == "stage_2":
        score += 10
        reasons.append("Stage 2 主升段：價格站上上彎 MA60")
    elif stage == "stage_4":
        score -= 20
        risks.append("Stage 4 主跌段：避免逆勢做多")
    elif stage == "stage_3":
        score -= 5
        risks.append("Stage 3 頭部觀察：趨勢仍在高位但動能未延續")

    if reward_risk_ratio is not None:
        if reward_risk_ratio >= 2:
            score += 5
            reasons.append(f"風險報酬比良好（R/R:{reward_risk_ratio}）")
        elif reward_risk_ratio < 1.2:
            score -= 10
            risks.append(f"風險報酬比不足（R/R:{reward_risk_ratio}）")

    if old_wang["old_wang_flag"]:
        reasons.append(f"{OLD_WANG_TAG_NAME}：{old_wang['old_wang_reason']}")

    score     = max(0, min(100, score))

    trend_score = 50
    if long_t == "up":
        trend_score += 20
    elif long_t == "down":
        trend_score -= 20
    if short_t == "up":
        trend_score += 10
    elif short_t == "down":
        trend_score -= 10
    if stage == "stage_2":
        trend_score += 15
    elif stage == "stage_4":
        trend_score -= 25
    if rs_score is not None:
        trend_score += round((rs_score - 50) * 0.3)
    trend_score = max(0, min(100, trend_score))

    entry_score = 50
    if breakout:
        entry_score += 25
    if strong_reversal:
        entry_score += 25
    if pullback_quality:
        entry_score += 20
    if near_ma20 or near_support:
        entry_score += 10
    if rsi14 is not None and not (40 <= rsi14 <= 70):
        entry_score -= 15
    if vol_ratio is not None and vol_ratio < 0.8:
        entry_score -= 10
    if reward_risk_ratio is not None:
        if reward_risk_ratio >= 2:
            entry_score += 15
        elif reward_risk_ratio < 1.2:
            entry_score -= 20
    if pat.pattern_type == "m_top" and pat.pattern_status in ("forming", "confirmed"):
        entry_score -= 20
    if market_regime == "bear":
        entry_score -= 25
    entry_score = max(0, min(100, entry_score))

    risk_score = 50
    if market_regime == "bear":
        risk_score += 20
    if long_t == "down":
        risk_score += 20
    if breakdown:
        risk_score += 20
    if rsi14 is not None and rsi14 > 75:
        risk_score += 15
    if pat.pattern_type == "m_top" and pat.pattern_status in ("forming", "confirmed"):
        risk_score += 15
    if reward_risk_ratio is not None and reward_risk_ratio < 1.2:
        risk_score += 10
    risk_score = max(0, min(100, risk_score))

    steady_momentum = _steady_momentum_indicator(
        close=close,
        ma20=ma20,
        ma60=ma60,
        long_trend=long_t,
        stage=stage,
        market_filter=market_filter,
        relative_strength_score=rs_score,
        trend_score=trend_score,
        entry_score=entry_score,
        risk_score=risk_score,
        reward_risk_ratio=reward_risk_ratio,
        rsi14=rsi14,
        fundamental_guard=fundamental_guard,
    )

    risk_note = "；".join(risks) if risks else "—"

    # ── 內部 7 狀態訊號（依優先順序）────────────────────────────────────
    no_buy_reason: str

    if long_t == "down" and breakdown:
        internal = "invalidated"
        no_buy_reason = f"長線偏空且跌破支撐（支撐:{support_price}），訊號失效"

    elif ma60_minor_break:
        internal = "watchlist"
        no_buy_reason = f"收盤小幅跌破 MA60 {ma60}（{ma60_break_pct:.2f}%），先觀察是否收回，不直接出場"

    elif long_t == "down":
        if ma60_break_pct <= 1.0 and not ma60_down:
            internal = "watchlist"
            no_buy_reason = f"收盤小幅跌破 MA60 {ma60}（{ma60_break_pct:.2f}%），等待跌破確認"
        else:
            internal = "exit_warning"
            slope_note = "且 MA60 下彎" if ma60_down else ""
            no_buy_reason = f"收盤 {close} 跌破 MA60 {ma60}（{ma60_break_pct:.2f}%）{slope_note}，長線偏空"

    elif breakdown:
        internal = "exit_warning"
        no_buy_reason = f"跌破支撐 {support_price} 達 2% 以上，注意下行風險"

    elif (
        long_t == "up"
        and breakout
        and breakout_entry_quality
        and market_filter != "block"
        and stage != "stage_4"
    ):
        internal = "entry_confirmed"
        no_buy_reason = ""

    elif long_t == "up" and breakout and market_filter != "block" and stage != "stage_4":
        internal = "watchlist"
        if not breakout_rr_ok and not breakout_rsi_ok:
            no_buy_reason = f"突破放量但 RSI 過熱（{rsi14}）且風險報酬不足（R/R:{reward_risk_ratio}），不追價"
        elif not breakout_rr_ok:
            no_buy_reason = f"突破放量但風險報酬不足（R/R:{reward_risk_ratio}），不追價"
        else:
            no_buy_reason = f"突破放量但 RSI 過熱（{rsi14}），等待回測或降溫"

    elif strong_reversal and market_filter != "block":
        internal = "watchlist"
        no_buy_reason = "強勢反轉站回 MA60，等待隔日量價確認，不再視為出場"

    elif (overheated or near_hot_resistance) and short_ma_hold:
        internal = "watchlist"
        if overheated:
            no_buy_reason = f"RSI 過熱（{rsi14}）但仍守 MA5/MA10，強勢延伸觀察，跌破短均再減碼"
        else:
            no_buy_reason = f"接近壓力區（{resistance_price}）但仍守 MA5/MA10，先不預設高點"

    elif overheated or near_hot_resistance:
        internal = "take_profit_warning"
        if overheated:
            no_buy_reason = f"RSI 過熱（{rsi14}）且未守穩 MA5/MA10，停利觀察"
        else:
            no_buy_reason = f"接近壓力區（{resistance_price}）且 RSI 偏高（{rsi14}），停利注意"

    elif is_holding and long_t != "down" and not breakdown:
        internal = "hold"
        no_buy_reason = "持股中，長線趨勢穩定，可續抱"

    elif (
        long_t == "up"
        and pullback_quality
        and market_filter != "block"
        and stage in ("stage_2", "unknown")
        and not (pat.pattern_type == "m_top" and pat.pattern_status in ("forming", "confirmed"))
    ):
        internal = "ready_to_enter"
        no_buy_reason = ""

    else:
        internal = "watchlist"
        if long_t == "up":
            if market_filter == "block":
                no_buy_reason = "大盤環境偏空，個股多頭訊號降為觀察"
            elif stage == "stage_3":
                no_buy_reason = "可能進入 Stage 3 頭部觀察，等待趨勢重新轉強"
            elif pat.pattern_type == "m_top" and pat.pattern_status in ("forming", "confirmed"):
                no_buy_reason = "出現 M 頂風險，等待型態化解或重新突破"
            elif close < (ma20 or 0):
                no_buy_reason = "長線多頭，但收盤未站上 MA20，等候回升"
            elif near_ma20 or near_support:
                if rsi14 is not None and rsi14 > 70:
                    no_buy_reason = f"接近進場區但 RSI 偏高（{rsi14}），等待降溫"
                elif vol_ratio is not None and vol_ratio < 0.8 and not recaptures_ma5:
                    no_buy_reason = f"接近進場區但量能不足（{vol_ratio:.1f}x），等候放量或站回 MA5"
                elif reward_risk_ratio is not None and reward_risk_ratio < 1.5:
                    no_buy_reason = f"接近進場區但風險報酬不足（R/R:{reward_risk_ratio}）"
                else:
                    no_buy_reason = "接近進場區，但尚未出現明確止跌或轉強"
            elif ma20 is not None and close > ma20 * 1.05:
                pct = round((close / ma20 - 1) * 100, 1)
                no_buy_reason = f"長線多頭，但收盤距 MA20 過遠（+{pct}%），等候回測"
            elif vol_ratio is not None and vol_ratio < 0.8:
                no_buy_reason = f"長線多頭，但量能不足（{vol_ratio:.1f}x），等候放量"
            else:
                no_buy_reason = "長線多頭，觀察是否形成進場型態"
        else:
            no_buy_reason = f"長線趨勢中性（MA60:{ma60}），觀察趨勢方向確立"

    # ── 外部 signal / entry_type（API 契約）─────────────────────────────
    ext_signal, entry_type = _EXT_MAP[internal]
    strategy_tags = [CORE_STRATEGY_ID]
    if old_wang["old_wang_flag"]:
        strategy_tags.append(OLD_WANG_TAG)
    if steady_momentum["steady_momentum_flag"]:
        strategy_tags.append(STEADY_MOMENTUM_TAG)
    alignment = _strategy_alignment(
        internal_signal=internal,
        old_wang_flag=old_wang["old_wang_flag"],
        steady_momentum_flag=steady_momentum["steady_momentum_flag"],
    )
    entry_price_low, entry_price_high, price_plan_note, entry_source = _entry_price_plan(
        internal_signal=internal,
        close=close,
        long_trend=long_t,
        stage=stage,
        support_price=support_price,
        resistance_price=resistance_price,
        ma20=ma20,
        ma60=ma60,
    )
    position_size_pct, position_size_note = _position_size_plan(
        internal_signal=internal,
        old_wang_flag=old_wang["old_wang_flag"],
        reward_risk_ratio=reward_risk_ratio,
        risk_score=risk_score,
        old_wang_chip_signal=old_wang["old_wang_chip_signal"],
    )

    return {
        # ── 舊 API 契約欄位（測試依賴）──
        "code":          code,
        "data_ok":       True,
        "data_missing":  False,
        "calculation_status": "ok",
        "calculation_error": "",
        "signal":        ext_signal,    # BUY / SELL / HOLD / DATA_MISSING
        "entry_type":    entry_type,    # pullback / breakout / squeeze / ""
        "no_buy_reason": no_buy_reason,
        "close":         close,
        "ma5":           ma5,
        "ma10":          ma10,
        "ma20":          ma20,
        "ma60":          ma60,
        "rsi14":         rsi14,
        "volume":        rows[-1]["volume"],
        "vol_ratio":     vol_ratio,
        # ── 新增欄位（可觀測性）──
        "name":            name,
        "internal_signal": internal,    # 7 狀態（watchlist/ready_to_enter/…）
        "score":           score,
        "trend_score":     trend_score,
        "entry_score":     entry_score,
        "risk_score":      risk_score,
        "position_size_pct": position_size_pct,
        "position_size_note": position_size_note,
        "holding_shares": 0,
        "holding_avg_cost": None,
        "holding_position_pct": 0.0,
        "long_trend":      long_t,
        "short_trend":     short_t,
        "market_regime":   market_regime,
        "market_filter":   market_filter,
        "old_wang_market_regime": old_wang_market_regime,
        "old_wang_market_filter": old_wang_market_filter,
        "old_wang_market_source": old_wang_market_source,
        "old_wang_market_reason": old_wang_market_reason,
        "relative_strength_score": rs_score,
        "relative_strength_60d":   rs60,
        "relative_strength_120d":  rs120,
        "stage":           stage,
        "strategy_tags":    strategy_tags,
        "strategy_alignment": alignment["strategy_alignment"],
        "aligned_strategies": alignment["aligned_strategies"],
        "strategy_conflict_notes": alignment["strategy_conflict_notes"],
        "old_wang_flag":    old_wang["old_wang_flag"],
        "old_wang_tag":     old_wang["old_wang_tag"],
        "old_wang_score":   old_wang["old_wang_score"],
        "old_wang_signal":  old_wang["old_wang_signal"],
        "old_wang_badges":  old_wang["old_wang_badges"],
        "old_wang_reason":  old_wang["old_wang_reason"],
        "old_wang_sector":  old_wang["old_wang_sector"],
        "sector_score":     old_wang["sector_score"],
        "old_wang_volume_signal": old_wang["old_wang_volume_signal"],
        "old_wang_gap_type": old_wang["old_wang_gap_type"],
        "old_wang_gap_support": old_wang["old_wang_gap_support"],
        "old_wang_gap_resistance": old_wang["old_wang_gap_resistance"],
        "old_wang_gap_note": old_wang["old_wang_gap_note"],
        "old_wang_ma_signal": old_wang["old_wang_ma_signal"],
        "old_wang_volume_low_support": old_wang["old_wang_volume_low_support"],
        "old_wang_volume_low_price": old_wang["old_wang_volume_low_price"],
        "old_wang_support_state": old_wang["old_wang_support_state"],
        "old_wang_ma_break_count": old_wang["old_wang_ma_break_count"],
        "old_wang_previous_high_risk": old_wang["old_wang_previous_high_risk"],
        "old_wang_chip_signal": old_wang["old_wang_chip_signal"],
        "old_wang_raw_score": old_wang["old_wang_raw_score"],
        "old_wang_previous_high_state": old_wang["old_wang_previous_high_state"],
        "old_wang_previous_high_price": old_wang["old_wang_previous_high_price"],
        "old_wang_volume_high_breakout": old_wang["old_wang_volume_high_breakout"],
        "old_wang_volume_high_price": old_wang["old_wang_volume_high_price"],
        "old_wang_all_ma_reclaim": old_wang["old_wang_all_ma_reclaim"],
        "old_wang_parabolic_ma10_hold": old_wang["old_wang_parabolic_ma10_hold"],
        "steady_momentum_flag": steady_momentum["steady_momentum_flag"],
        "steady_momentum_tag": steady_momentum["steady_momentum_tag"],
        "steady_momentum_score": steady_momentum["steady_momentum_score"],
        "steady_momentum_signal": steady_momentum["steady_momentum_signal"],
        "steady_momentum_reason": steady_momentum["steady_momentum_reason"],
        "fundamental_flag": fundamental_guard["fundamental_flag"],
        "fundamental_tag": fundamental_guard["fundamental_tag"],
        "fundamental_score": fundamental_guard["fundamental_score"],
        "fundamental_signal": fundamental_guard["fundamental_signal"],
        "fundamental_reason": fundamental_guard["fundamental_reason"],
        "fundamental_data_ok": fundamental_guard["fundamental_data_ok"],
        "fundamental_data_missing_reason": fundamental_guard["fundamental_data_missing_reason"],
        "fundamental_quality_score": fundamental_guard["fundamental_quality_score"],
        "fundamental_value_score": fundamental_guard["fundamental_value_score"],
        "fundamental_safety_score": fundamental_guard["fundamental_safety_score"],
        "fundamental_growth_score": fundamental_guard["fundamental_growth_score"],
        "fundamental_data_completeness_pct": fundamental_guard["fundamental_data_completeness_pct"],
        "fundamental_missing_fields": fundamental_guard["fundamental_missing_fields"],
        "fundamental_scored_groups": fundamental_guard["fundamental_scored_groups"],
        "data_as_of":      data_as_of,
        "entry_price_low": entry_price_low,
        "entry_price_high": entry_price_high,
        "stop_price":      stop_price,
        "target_price":    target_price,
        "risk_pct":        risk_pct,
        "reward_pct":      reward_pct,
        "reward_risk_ratio": reward_risk_ratio,
        "price_plan_note": price_plan_note,
        "support_source":  support_source,
        "resistance_source": resistance_source,
        "entry_source":    entry_source,
        "stop_source":     stop_source,
        "target_source":   target_source,
        "support_price":   support_price,
        "resistance_price": resistance_price,
        "pattern_type":    pattern_type,
        "pattern_status":  pattern_status,
        "risk_note":       risk_note,
        "reasons":         reasons,
    }


def _annotate_daily_decisions(signals: list[dict]) -> None:
    for sig in signals:
        sig.update(_daily_decision_plan(sig))
        sig["daily_checklist"] = _daily_checklist(sig)


# ---------------------------------------------------------------------------
# 輸出
# ---------------------------------------------------------------------------

def _write_summary(result: dict) -> Path:
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / "summary.json"
    atomic_write_text(path, json.dumps(result, ensure_ascii=False, indent=2))
    return path


def _write_previous_summary(previous: dict | None) -> Path | None:
    if not previous:
        return None
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / "summary_previous.json"
    atomic_write_text(path, json.dumps(previous, ensure_ascii=False, indent=2))
    return path


def _recommended_codes(summary: dict) -> set[str]:
    buckets = summary.get("recommendation_buckets") or {}
    codes: set[str] = set()
    for key in ("old_wang", "steady_momentum"):
        for item in buckets.get(key) or []:
            if item.get("code"):
                codes.add(str(item.get("code")))
    return codes


def _compute_change_report(previous: dict | None, current_signals: list[dict]) -> dict:
    """
    與前一次 summary 比較，產生日更/重算後的變化報告。

    比較基準：
      - 推薦新增/移出：用兩方案推薦桶 old_wang / steady_momentum 的聯集
      - 狀態變化：用 signals[*].internal_signal
    """
    current_by_code = {s["code"]: s for s in current_signals if s.get("code")}
    current_recommended = {
        code for code, sig in current_by_code.items()
        if sig.get("old_wang_flag") or sig.get("steady_momentum_flag")
    }

    if not previous:
        return {
            "has_previous": False,
            "previous_as_of": None,
            "new_recommendations": sorted(current_recommended),
            "removed_recommendations": [],
            "signal_changes": [],
            "summary": {
                "new_count": len(current_recommended),
                "removed_count": 0,
                "changed_count": 0,
            },
        }

    previous_signals = previous.get("signals") or []
    previous_by_code = {s["code"]: s for s in previous_signals if s.get("code")}
    previous_recommended = _recommended_codes(previous)

    def _brief(code: str, sig: dict, *, previous_signal: str | None = None) -> dict:
        item = {
            "code": code,
            "name": sig.get("name", code),
            "internal_signal": sig.get("internal_signal"),
            "score": sig.get("score"),
            "entry_score": sig.get("entry_score"),
            "old_wang_score": sig.get("old_wang_score"),
            "old_wang_badges": sig.get("old_wang_badges") or [],
            "no_buy_reason": sig.get("no_buy_reason", ""),
        }
        if previous_signal is not None:
            item["previous_signal"] = previous_signal
        return item

    new_recommendations = [
        _brief(code, current_by_code[code])
        for code in sorted(current_recommended - previous_recommended)
        if code in current_by_code
    ]
    removed_recommendations = [
        _brief(code, current_by_code.get(code, previous_by_code[code]))
        for code in sorted(previous_recommended - current_recommended)
        if code in previous_by_code
    ]

    signal_changes = []
    for code, current in current_by_code.items():
        previous_item = previous_by_code.get(code)
        if not previous_item:
            continue
        previous_signal = previous_item.get("internal_signal")
        current_signal = current.get("internal_signal")
        if previous_signal and current_signal and previous_signal != current_signal:
            signal_changes.append(_brief(code, current, previous_signal=previous_signal))

    signal_changes.sort(key=lambda item: (
        item.get("internal_signal") not in ("entry_confirmed", "ready_to_enter", "exit_warning", "invalidated"),
        item.get("code", ""),
    ))

    return {
        "has_previous": True,
        "previous_as_of": previous.get("as_of"),
        "new_recommendations": new_recommendations[:30],
        "removed_recommendations": removed_recommendations[:30],
        "signal_changes": signal_changes[:50],
        "summary": {
            "new_count": len(new_recommendations),
            "removed_count": len(removed_recommendations),
            "changed_count": len(signal_changes),
        },
    }


def _write_universe_report(signals: list[dict]) -> Path:
    _OUT.mkdir(parents=True, exist_ok=True)
    path = _OUT / "universe_report.csv"

    rows = []
    for s in signals:
        row = dict(s)
        if isinstance(row.get("reasons"), list):
            row["reasons"] = " | ".join(row["reasons"])
        if isinstance(row.get("strategy_tags"), list):
            row["strategy_tags"] = ",".join(row["strategy_tags"])
        if isinstance(row.get("aligned_strategies"), list):
            row["aligned_strategies"] = ",".join(row["aligned_strategies"])
        if isinstance(row.get("strategy_conflict_notes"), list):
            row["strategy_conflict_notes"] = " | ".join(row["strategy_conflict_notes"])
        if isinstance(row.get("old_wang_badges"), list):
            row["old_wang_badges"] = ",".join(row["old_wang_badges"])
        if isinstance(row.get("daily_checklist"), list):
            row["daily_checklist"] = json.dumps(row["daily_checklist"], ensure_ascii=False)
        rows.append(row)

    tmp_path = path.with_name(f".{path.name}.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)
    return path


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _build_signal_lineage(generated_at: str) -> dict:
    digest = hashlib.sha1(generated_at.encode("utf-8")).hexdigest()[:8]
    compact_time = generated_at.replace("-", "").replace(":", "")
    return {
        "batch_id": f"signals-{compact_time}-{digest}",
        "source": "run_daily_signals",
        "run_started_at": generated_at,
    }


def run_daily_signals(as_of_date: str | None = None, lineage: dict | None = None) -> dict:
    """
    計算全宇宙股票訊號，寫出 summary.json 與 universe_report.csv。

    Parameters
    ----------
    as_of_date : str | None
        計算基準日（YYYY-MM-DD）。None 表示使用今日。

    Returns
    -------
    dict
        summary 結果，同時寫入 backend/out/summary.json。
    """
    requested_as_of = as_of_date
    if as_of_date is None:
        from datetime import date
        as_of_date = date.today().isoformat()

    _reload_name_cache()  # 確保 backfill 後名稱立即生效
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    previous_summary = get_summary()
    run_lineage = dict(lineage or _build_signal_lineage(generated_at))
    if not run_lineage.get("batch_id"):
        run_lineage["batch_id"] = _build_signal_lineage(generated_at)["batch_id"]

    codes     = _load_leaders()
    leader_groups = _load_leader_groups()
    ohlcv     = _load_ohlcv(as_of_date)
    positions = _load_positions()
    context   = _market_context(ohlcv)
    context["stock_markets"] = load_stock_markets()
    context["sector_rotation"] = _sector_rotation_context(leader_groups, ohlcv)
    context["fundamentals"] = load_fundamentals()
    actual_as_of = _latest_data_date(codes, ohlcv) or as_of_date

    timeout_seconds = _resolve_stock_timeout_seconds()
    signals = _run_signal_batch(
        codes,
        ohlcv,
        positions,
        context,
        timeout_seconds=timeout_seconds,
    )
    no_buy_counter: Counter = Counter()

    for sig in signals:
        # 統計未進場原因（BUY 以外）
        if sig["signal"] != "BUY" and sig["no_buy_reason"]:
            no_buy_counter[sig["no_buy_reason"]] += 1

    _annotate_holding_weights(signals, positions)
    _annotate_daily_decisions(signals)

    # 資料完整的股票
    data_ok_signals = [s for s in signals if s["data_ok"]]
    calculation_timeout_codes = [
        s["code"] for s in signals if s.get("calculation_status") == "timeout"
    ]

    # data_ok_counts（中文鍵，維持舊 API 契約）
    data_ok_counts = {
        "買入": sum(1 for s in data_ok_signals if s["signal"] == "BUY"),
        "賣出": sum(1 for s in data_ok_signals if s["signal"] == "SELL"),
        "觀望": sum(1 for s in data_ok_signals if s["signal"] == "HOLD"),
    }

    # signal_counts（7 狀態，供內部觀測）
    _STATES = (
        "entry_confirmed", "ready_to_enter", "watchlist",
        "hold", "take_profit_warning", "exit_warning", "invalidated",
    )
    signal_counts: dict[str, int] = {s: 0 for s in _STATES}
    signal_counts["DATA_MISSING"] = sum(1 for s in signals if not s["data_ok"])
    for s in data_ok_signals:
        internal = s.get("internal_signal", "")
        if internal in signal_counts:
            signal_counts[internal] += 1

    high_score_non_buy = [
        {
            "code": s["code"],
            "name": s.get("name", s["code"]),
            "score": s.get("score"),
            "entry_score": s.get("entry_score"),
            "risk_score": s.get("risk_score"),
            "internal_signal": s.get("internal_signal"),
            "no_buy_reason": s.get("no_buy_reason"),
        }
        for s in data_ok_signals
        if s.get("signal") != "BUY" and (s.get("score") or 0) >= 90
    ]
    high_score_non_buy.sort(key=lambda s: s.get("score") or 0, reverse=True)

    def _pick_fields(s: dict, source: str) -> dict:
        return {
            "code": s["code"],
            "name": s.get("name", s["code"]),
            "source": source,
            "signal": s.get("signal"),
            "internal_signal": s.get("internal_signal"),
            "score": s.get("score"),
            "entry_score": s.get("entry_score"),
            "strategy_alignment": s.get("strategy_alignment"),
            "aligned_strategies": s.get("aligned_strategies"),
            "strategy_conflict_notes": s.get("strategy_conflict_notes"),
            "fundamental_score": s.get("fundamental_score"),
            "fundamental_signal": s.get("fundamental_signal"),
            "fundamental_reason": s.get("fundamental_reason"),
            "fundamental_quality_score": s.get("fundamental_quality_score"),
            "fundamental_value_score": s.get("fundamental_value_score"),
            "fundamental_safety_score": s.get("fundamental_safety_score"),
            "fundamental_growth_score": s.get("fundamental_growth_score"),
            "fundamental_data_completeness_pct": s.get("fundamental_data_completeness_pct"),
            "fundamental_missing_fields": s.get("fundamental_missing_fields"),
            "fundamental_scored_groups": s.get("fundamental_scored_groups"),
            "steady_momentum_score": s.get("steady_momentum_score"),
            "steady_momentum_signal": s.get("steady_momentum_signal"),
            "steady_momentum_reason": s.get("steady_momentum_reason"),
            "old_wang_score": s.get("old_wang_score"),
            "old_wang_signal": s.get("old_wang_signal"),
            "old_wang_badges": s.get("old_wang_badges"),
            "old_wang_sector": s.get("old_wang_sector"),
            "old_wang_volume_signal": s.get("old_wang_volume_signal"),
            "old_wang_gap_type": s.get("old_wang_gap_type"),
            "old_wang_gap_support": s.get("old_wang_gap_support"),
            "old_wang_gap_resistance": s.get("old_wang_gap_resistance"),
            "old_wang_gap_note": s.get("old_wang_gap_note"),
            "old_wang_ma_signal": s.get("old_wang_ma_signal"),
            "old_wang_volume_low_support": s.get("old_wang_volume_low_support"),
            "old_wang_volume_low_price": s.get("old_wang_volume_low_price"),
            "old_wang_support_state": s.get("old_wang_support_state"),
            "old_wang_ma_break_count": s.get("old_wang_ma_break_count"),
            "old_wang_previous_high_risk": s.get("old_wang_previous_high_risk"),
            "old_wang_chip_signal": s.get("old_wang_chip_signal"),
            "old_wang_raw_score": s.get("old_wang_raw_score"),
            "old_wang_previous_high_state": s.get("old_wang_previous_high_state"),
            "old_wang_previous_high_price": s.get("old_wang_previous_high_price"),
            "old_wang_volume_high_breakout": s.get("old_wang_volume_high_breakout"),
            "old_wang_volume_high_price": s.get("old_wang_volume_high_price"),
            "old_wang_all_ma_reclaim": s.get("old_wang_all_ma_reclaim"),
            "old_wang_parabolic_ma10_hold": s.get("old_wang_parabolic_ma10_hold"),
            "position_size_pct": s.get("position_size_pct"),
            "position_size_note": s.get("position_size_note"),
            "holding_shares": s.get("holding_shares"),
            "holding_avg_cost": s.get("holding_avg_cost"),
            "holding_position_pct": s.get("holding_position_pct"),
            "daily_action": s.get("daily_action"),
            "daily_action_label": s.get("daily_action_label"),
            "daily_action_reason": s.get("daily_action_reason"),
            "daily_key_price": s.get("daily_key_price"),
            "daily_invalidation": s.get("daily_invalidation"),
            "daily_checklist": s.get("daily_checklist"),
            "entry_price_low": s.get("entry_price_low"),
            "entry_price_high": s.get("entry_price_high"),
            "stop_price": s.get("stop_price"),
            "target_price": s.get("target_price"),
            "price_plan_note": s.get("price_plan_note"),
            "support_source": s.get("support_source"),
            "resistance_source": s.get("resistance_source"),
            "entry_source": s.get("entry_source"),
            "stop_source": s.get("stop_source"),
            "target_source": s.get("target_source"),
            "reason": (
                s.get("old_wang_reason")
                if source == OLD_WANG_TAG
                else s.get("steady_momentum_reason")
                if source == STEADY_MOMENTUM_TAG
                else s.get("no_buy_reason", "")
            ),
        }

    old_wang_recommendations = [
        _pick_fields(s, OLD_WANG_TAG)
        for s in data_ok_signals
        if s.get("old_wang_flag")
    ]
    steady_momentum_recommendations = [
        _pick_fields(s, STEADY_MOMENTUM_TAG)
        for s in data_ok_signals
        if s.get("steady_momentum_flag")
    ]
    steady_momentum_recommendations = sorted(
        steady_momentum_recommendations,
        key=lambda s: (s.get("steady_momentum_score") or 0, s.get("score") or 0),
        reverse=True,
    )

    result = {
        "as_of":               actual_as_of if requested_as_of is None else as_of_date,
        "requested_as_of":      requested_as_of,
        "generated_at":        generated_at,
        "rules_version":        RULES_VERSION,
        "rules_metadata":       build_rules_metadata(),
        "batch_id":            run_lineage["batch_id"],
        "lineage":             run_lineage,
        "universe_size":       len(codes),
        "data_ok_count":       len(data_ok_signals),
        "data_missing_count":  len(codes) - len(data_ok_signals),
        "calculation_timeout_seconds": timeout_seconds,
        "calculation_timeout_count": len(calculation_timeout_codes),
        "calculation_timeout_codes": calculation_timeout_codes,
        "data_ok_counts":      data_ok_counts,       # 舊 API 契約（中文鍵）
        "signal_counts":       signal_counts,         # 新增（7 狀態，可觀測性）
        "market_context": {
            "benchmark_code": context.get("benchmark_code"),
            "market_regime": context.get("market_regime"),
            "market_filter": context.get("market_filter"),
            "reason": context.get("market_reason"),
            "old_wang_market_regime": context.get("old_wang_market_regime"),
            "old_wang_market_filter": context.get("old_wang_market_filter"),
            "old_wang_market_source": context.get("old_wang_market_source"),
            "old_wang_market_reason": context.get("old_wang_market_reason"),
        },
        "manual_market_note": _market_note_for_date(actual_as_of if requested_as_of is None else as_of_date),
        "strategy_catalog": {
            OLD_WANG_TAG: {
                "name": OLD_WANG_TAG_NAME,
                "role": "短波段攻擊策略",
                "description": "用上市/櫃買大盤濾網、族群輪動、短均線、跳空、爆大量低點/高點與前高突破，尋找短線資金發動標的。",
            },
            STEADY_MOMENTUM_TAG: {
                "name": STEADY_MOMENTUM_NAME,
                "role": "穩健主線策略",
                "description": "以價格動能為主，搭配 PE、獲利、負債與成長等低成本基本面 guard，建立 Quality Momentum Lite 候選。",
            },
        },
        "recommendation_buckets": {
            "old_wang": old_wang_recommendations[:30],
            "steady_momentum": steady_momentum_recommendations[:30],
        },
        "change_report": _compute_change_report(previous_summary, signals),
        "high_score_non_buy": high_score_non_buy[:20],
        "no_buy_reason_counts": dict(no_buy_counter.most_common()),
        "signals":             signals,
    }

    _OUT.mkdir(parents=True, exist_ok=True)
    previous_path = _write_previous_summary(previous_summary)
    summary_path = _write_summary(result)
    report_path  = _write_universe_report(signals)
    brief_path   = write_daily_brief(result, _OUT)
    today_scan_path = write_today_scan_report(_OUT)
    snapshot_outputs = write_snapshot_and_review(result, _OUT)
    snapshot_review = json.loads(snapshot_outputs["review_path"].read_text(encoding="utf-8"))
    alert_path = write_signal_alerts(snapshot_review, _OUT)
    signal_alerts = json.loads(alert_path.read_text(encoding="utf-8"))
    priority_fundamentals_path = write_priority_fill_csv(_OUT)
    fundamentals_path = write_fundamentals_report(_OUT)

    result["out_dir"]       = str(_OUT)
    result["signal_alert_count"] = int(signal_alerts.get("alert_count") or 0)
    result["signal_alert_summary"] = {
        "status": signal_alerts.get("status"),
        "message": signal_alerts.get("message"),
        "severity_counts": signal_alerts.get("severity_counts") or {},
    }
    result["files_written"] = [
        summary_path.name,
        report_path.name,
        brief_path.name,
        today_scan_path.name,
        f"today_scans/today_scan_{result['as_of']}.json",
        snapshot_outputs["review_path"].name,
        str(snapshot_outputs["snapshot_path"].relative_to(_OUT)),
        alert_path.name,
        fundamentals_path.name,
        priority_fundamentals_path.name,
    ]
    if previous_path:
        result["files_written"].append(previous_path.name)

    return result
