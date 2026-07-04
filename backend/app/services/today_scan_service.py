from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"
TODAY_SCAN_FILENAME = "today_scan.json"
TODAY_SCAN_SNAPSHOT_DIR = "today_scans"
DEFAULT_SCAN_LIMIT = 1000

_ENTRY_SIGNALS = {"entry_confirmed", "ready_to_enter"}
_ENTRY_ACTIONS = {"enter", "add"}
_RISK_SIGNALS = {"exit_warning", "invalidated"}
_RISK_ACTIONS = {"reduce", "exit"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_universe(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except OSError:
        return []


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _score_level(score: int) -> str:
    if score >= 85:
        return "high"
    if score >= 70:
        return "mid"
    return "low"


def _strategy_score_summary(row: dict[str, Any]) -> dict[str, Any]:
    old_wang_score = _as_int(row.get("old_wang_score"))
    steady_score = _as_int(row.get("steady_momentum_score"))
    if old_wang_score <= 0 and steady_score <= 0:
        return {
            "primary_strategy": "none",
            "primary_label": "尚未成形",
            "primary_score": 0,
            "old_wang_level": "low",
            "steady_momentum_level": "low",
            "score_gap": 0,
            "summary_label": "兩策略分數皆未成形",
        }

    if old_wang_score >= steady_score:
        primary_strategy = "old_wang"
        primary_label = "第一 老王"
        primary_score = old_wang_score
        summary_label = f"第一 老王 {old_wang_score}，高於第二 穩健 {steady_score}"
    else:
        primary_strategy = "steady_momentum"
        primary_label = "第二 穩健"
        primary_score = steady_score
        summary_label = f"第二 穩健 {steady_score}，高於第一 老王 {old_wang_score}"

    return {
        "primary_strategy": primary_strategy,
        "primary_label": primary_label,
        "primary_score": primary_score,
        "old_wang_level": _score_level(old_wang_score),
        "steady_momentum_level": _score_level(steady_score),
        "score_gap": abs(old_wang_score - steady_score),
        "summary_label": summary_label,
    }


def _reason(row: dict[str, Any]) -> str:
    for key in (
        "daily_action_reason",
        "old_wang_reason",
        "steady_momentum_reason",
        "no_buy_reason",
        "risk_note",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _compact_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(row.get("code") or ""),
        "name": str(row.get("name") or row.get("code") or ""),
        "close": _as_float(row.get("close")),
        "internal_signal": row.get("internal_signal"),
        "daily_action": row.get("daily_action"),
        "daily_action_label": row.get("daily_action_label"),
        "old_wang_score": _as_int(row.get("old_wang_score")),
        "old_wang_signal": row.get("old_wang_signal"),
        "steady_momentum_score": _as_int(row.get("steady_momentum_score")),
        "steady_momentum_signal": row.get("steady_momentum_signal"),
        "strategy_score_summary": _strategy_score_summary(row),
        "entry_score": _as_int(row.get("entry_score")),
        "risk_score": _as_int(row.get("risk_score")),
        "entry_price_low": _as_float(row.get("entry_price_low")),
        "entry_price_high": _as_float(row.get("entry_price_high")),
        "stop_price": _as_float(row.get("stop_price")),
        "target_price": _as_float(row.get("target_price")),
        "reward_risk_ratio": _as_float(row.get("reward_risk_ratio")),
        "vol_ratio": _as_float(row.get("vol_ratio")),
        "rsi14": _as_float(row.get("rsi14")),
        "data_as_of": row.get("data_as_of"),
        "reason": _reason(row),
    }


def _market_context(summary: dict[str, Any]) -> dict[str, Any]:
    context = summary.get("market_context")
    if isinstance(context, dict):
        return dict(context)
    return {
        "market_regime": summary.get("market_regime"),
        "market_filter": summary.get("market_filter"),
        "old_wang_market_regime": summary.get("old_wang_market_regime"),
        "old_wang_market_filter": summary.get("old_wang_market_filter"),
        "old_wang_market_reason": summary.get("old_wang_market_reason"),
    }


def _data_freshness(summary_as_of: str, universe_rows: list[dict[str, str]]) -> dict[str, Any]:
    date_counts = Counter(str(row.get("data_as_of") or "").strip() or "missing" for row in universe_rows)
    stale_items = [
        {
            "code": str(row.get("code") or ""),
            "name": str(row.get("name") or row.get("code") or ""),
            "data_as_of": str(row.get("data_as_of") or "").strip() or None,
        }
        for row in universe_rows
        if summary_as_of and str(row.get("data_as_of") or "").strip() and str(row.get("data_as_of") or "").strip() < summary_as_of
    ]
    stale_items.sort(key=lambda item: (str(item.get("data_as_of") or ""), str(item.get("code") or "")))
    fresh_count = int(date_counts.get(summary_as_of, 0)) if summary_as_of else 0
    missing_count = int(date_counts.get("missing", 0))
    stale_count = len(stale_items)
    return {
        "expected_as_of": summary_as_of or None,
        "row_count": len(universe_rows),
        "fresh_count": fresh_count,
        "stale_count": stale_count,
        "missing_date_count": missing_count,
        "date_counts": dict(sorted(date_counts.items())),
        "top_stale_items": stale_items[:8],
    }


def _notes(
    summary: dict[str, Any],
    market_context: dict[str, Any],
    universe_rows: list[dict[str, str]],
    data_freshness: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if str(market_context.get("old_wang_market_filter") or "").lower() == "block":
        reason = market_context.get("old_wang_market_reason") or "大盤短均線條件未通過"
        notes.append(f"老王大盤濾網目前封鎖追價：{reason}。符合老王條件者先列觀察，不直接追高。")
    summary_as_of = str(summary.get("as_of") or "")
    row_dates = {str(row.get("data_as_of") or "") for row in universe_rows if row.get("data_as_of")}
    if summary_as_of and row_dates and row_dates != {summary_as_of}:
        stale_count = int(data_freshness.get("stale_count") or 0)
        stale_items = data_freshness.get("top_stale_items") or []
        stale_label = ""
        if stale_count:
            names = ", ".join(f"{item.get('code')} {item.get('name')}({item.get('data_as_of') or '—'})" for item in stale_items[:4])
            stale_label = f"，其中 {stale_count} 檔股票資料日落後"
            if names:
                stale_label = f"{stale_label}：{names}"
        notes.append(f"universe_report 資料日不完全一致：summary={summary_as_of}，rows={', '.join(sorted(row_dates))}{stale_label}。")
    if not universe_rows:
        notes.append("尚未產生 universe_report.csv，請先執行 run_signals.py 或 daily_update.py。")
    return notes


def _bucket_notes() -> dict[str, str]:
    return {
        "formal_entries": "可小試候選仍需照價格計畫分批，確認進場區、停損與風險報酬後才行動。",
        "old_wang_candidates": "老王短波段觀察名單，重點是資金發動與支撐是否延續；大盤或個股過熱時不追高。",
        "steady_momentum_candidates": "Quality Momentum Lite 候選，仍需檢查 R/R、過熱控制、進場位置與輕量基本面避雷。",
        "risk_items": "風險項目先處理風險，再考慮新增部位；優先檢查停損、減碼或訊號失效原因。",
    }


def _usage_status(out_dir: Path, *, has_candidates: bool) -> dict[str, Any]:
    daily_check = _read_json(out_dir / "daily_check.json")
    top_actions = daily_check.get("top_actions") if isinstance(daily_check.get("top_actions"), list) else []
    blocker = next(
        (
            action
            for action in top_actions
            if isinstance(action, dict) and str(action.get("status") or "").lower() == "block"
        ),
        None,
    )
    if daily_check.get("can_use_trade_outputs") is False or blocker:
        title = str((blocker or {}).get("title") or "Daily Check 阻塞")
        message = str((blocker or {}).get("message") or "Daily Check 尚未允許交易輸出。")
        return {
            "can_use_trade_outputs": False,
            "status": "blocked_by_daily_check",
            "headline": "Today Scan 可供復盤，但交易輸出暫不可用",
            "reason": f"{title}：{message}",
            "next_action": str((blocker or {}).get("next_action") or "先處理 Daily Check block 項目。"),
            "blocking_action_key": (blocker or {}).get("key"),
            "blocking_action_status": (blocker or {}).get("status"),
        }
    if not has_candidates:
        return {
            "can_use_trade_outputs": True,
            "status": "no_candidates",
            "headline": "Today Scan 目前沒有候選",
            "reason": "掃描已完成，但沒有可小試、策略候選或風險項目。",
            "next_action": "維持觀察，等待下一次盤後更新或訊號轉強。",
            "blocking_action_key": None,
            "blocking_action_status": None,
        }
    return {
        "can_use_trade_outputs": True,
        "status": "ready",
        "headline": "Today Scan 可供盤後復盤",
        "reason": "Daily Check 未封鎖交易輸出；仍需依價格計畫、停損與風險報酬檢查候選。",
        "next_action": "先看可小試與風險分桶，再逐檔確認價格計畫。",
        "blocking_action_key": None,
        "blocking_action_status": None,
    }


def _sort(items: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: tuple(-_as_int(item.get(key)) for key in keys) + (item.get("code") or "",))


def build_today_scan_report(out_dir: Path | None = None, *, limit: int = DEFAULT_SCAN_LIMIT) -> dict[str, Any]:
    out_dir = out_dir or _OUT
    summary = _read_json(out_dir / "summary.json")
    daily_brief = _read_json(out_dir / "daily_brief.json")
    universe_rows = _read_universe(out_dir / "universe_report.csv")
    market_context = _market_context(summary)
    summary_as_of = str(summary.get("as_of") or daily_brief.get("as_of") or "")
    data_freshness = _data_freshness(summary_as_of, universe_rows)

    formal_entries: list[dict[str, Any]] = []
    old_wang_candidates: list[dict[str, Any]] = []
    steady_momentum_candidates: list[dict[str, Any]] = []
    risk_items: list[dict[str, Any]] = []

    for row in universe_rows:
        internal_signal = str(row.get("internal_signal") or "")
        daily_action = str(row.get("daily_action") or "")
        item = _compact_item(row)
        if internal_signal in _ENTRY_SIGNALS or daily_action in _ENTRY_ACTIONS:
            formal_entries.append(item)
        if _as_bool(row.get("old_wang_flag")):
            old_wang_candidates.append(item)
        if _as_bool(row.get("steady_momentum_flag")):
            steady_momentum_candidates.append(item)
        if internal_signal in _RISK_SIGNALS or daily_action in _RISK_ACTIONS:
            risk_items.append(item)

    formal_entries = _sort(formal_entries, "entry_score", "steady_momentum_score")[:limit]
    old_wang_candidates = _sort(old_wang_candidates, "old_wang_score", "entry_score")[:limit]
    steady_momentum_candidates = _sort(steady_momentum_candidates, "steady_momentum_score", "entry_score")[:limit]
    risk_items = _sort(risk_items, "risk_score")[:limit]
    has_candidates = any((formal_entries, old_wang_candidates, steady_momentum_candidates, risk_items))

    return {
        "as_of": summary.get("as_of") or daily_brief.get("as_of"),
        "generated_at": summary.get("generated_at") or daily_brief.get("generated_at"),
        "rules_version": summary.get("rules_version"),
        "rules_metadata": summary.get("rules_metadata") or {},
        "data_status": {
            "universe_size": summary.get("universe_size") or len(universe_rows),
            "data_ok_count": summary.get("data_ok_count"),
            "data_missing_count": summary.get("data_missing_count"),
        },
        "market_context": market_context,
        "signal_counts": summary.get("signal_counts") or {},
        "formal_entries": formal_entries,
        "old_wang_candidates": old_wang_candidates,
        "steady_momentum_candidates": steady_momentum_candidates,
        "risk_items": risk_items,
        "usage_status": _usage_status(out_dir, has_candidates=has_candidates),
        "bucket_notes": _bucket_notes(),
        "data_freshness": data_freshness,
        "notes": _notes(summary, market_context, universe_rows, data_freshness),
    }


def write_today_scan_report(out_dir: Path | None = None, *, limit: int = DEFAULT_SCAN_LIMIT) -> Path:
    out_dir = out_dir or _OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / TODAY_SCAN_FILENAME
    payload = build_today_scan_report(out_dir, limit=limit)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    as_of = str(payload.get("as_of") or "").strip()
    if as_of:
        snapshot_path = out_dir / TODAY_SCAN_SNAPSHOT_DIR / f"today_scan_{as_of}.json"
        atomic_write_text(snapshot_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_today_scan_report(out_dir: Path | None = None) -> dict[str, Any] | None:
    out_dir = out_dir or _OUT
    path = out_dir / TODAY_SCAN_FILENAME
    if not path.exists():
        return None
    data = _read_json(path)
    return data or None
