"""
daily_brief_service.py — 將 summary.json 整理成每日盤後作戰報告。

此 service 只負責整理既有 summary 訊號，不重新計算技術指標。
正式 BUY / SELL / HOLD 仍以 signals_service 的輸出為準。
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text
from app.utils import count_missed_trading_days

_BACKEND = Path(__file__).resolve().parent.parent.parent
_OUT = _BACKEND / "out"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _split_signal(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, list):
        return {str(v) for v in value if v}
    return {part.strip() for part in str(value).split(",") if part.strip()}


def _compute_data_stale(last_data_as_of: str | None) -> tuple[bool, int | None]:
    if not last_data_as_of:
        return True, None
    try:
        data_date = date.fromisoformat(last_data_as_of)
    except ValueError:
        return True, None
    stale_days = (date.today() - data_date).days
    return count_missed_trading_days(data_date) > 0, stale_days


def _data_status(summary: dict) -> dict:
    last_data_as_of = summary.get("as_of")
    is_stale, stale_days = _compute_data_stale(last_data_as_of)
    signals = list(summary.get("signals") or [])
    universe_size = int(summary.get("universe_size") or len(summary.get("signals") or []))
    data_ok_count = int(summary.get("data_ok_count") or 0)
    data_missing_count = int(summary.get("data_missing_count") or max(universe_size - data_ok_count, 0))
    data_ok_pct = round(data_ok_count / universe_size * 100, 1) if universe_size else 0.0
    missing_stocks = [
        {
            "code": sig.get("code"),
            "name": sig.get("name") or sig.get("code"),
            "reason": sig.get("data_missing_reason") or sig.get("no_buy_reason") or "資料不足",
        }
        for sig in signals
        if sig.get("data_missing") or sig.get("data_ok") is False
    ][:20]
    update_required = is_stale or data_missing_count > 0

    if is_stale:
        label = "資料可能過期"
        message = f"資料最新日 {last_data_as_of or '—'}，請先執行每日更新再做盤後判斷"
    elif data_missing_count > 0:
        label = "資料缺漏"
        message = f"資料最新日 {last_data_as_of}，但仍有 {data_missing_count} 檔資料不足"
    else:
        label = "資料最新"
        message = f"資料最新日 {last_data_as_of}，覆蓋率 {data_ok_pct:.1f}%"
    files_written = list(summary.get("files_written") or [])
    if not files_written:
        files_written = ["summary.json", "universe_report.csv", "daily_brief.json"]

    return {
        "last_data_as_of": last_data_as_of,
        "generated_at": summary.get("generated_at"),
        "requested_as_of": summary.get("requested_as_of"),
        "universe_size": universe_size,
        "data_ok_count": data_ok_count,
        "data_missing_count": data_missing_count,
        "data_ok_pct": data_ok_pct,
        "is_stale": is_stale,
        "stale_days": stale_days,
        "status_label": label,
        "message": message,
        "update_required": update_required,
        "update_command": "python3 scripts/daily_update.py --months 1",
        "missing_stocks": missing_stocks,
        "files_written": files_written,
    }


def _brief_stock(sig: dict, *, reason_key: str = "daily_action_reason") -> dict:
    return {
        "code": sig.get("code"),
        "name": sig.get("name") or sig.get("code"),
        "internal_signal": sig.get("internal_signal"),
        "close": sig.get("close"),
        "score": sig.get("score"),
        "old_wang_score": sig.get("old_wang_score"),
        "old_wang_sector": sig.get("old_wang_sector"),
        "old_wang_signal": sig.get("old_wang_signal"),
        "strategy_alignment": sig.get("strategy_alignment"),
        "aligned_strategies": sig.get("aligned_strategies") or [],
        "strategy_conflict_notes": sig.get("strategy_conflict_notes") or [],
        "daily_action": sig.get("daily_action"),
        "daily_action_label": sig.get("daily_action_label"),
        "daily_key_price": sig.get("daily_key_price"),
        "daily_invalidation": sig.get("daily_invalidation"),
        "entry_price_low": sig.get("entry_price_low"),
        "entry_price_high": sig.get("entry_price_high"),
        "stop_price": sig.get("stop_price"),
        "target_price": sig.get("target_price"),
        "price_plan_note": sig.get("price_plan_note"),
        "reason": sig.get(reason_key) or sig.get("no_buy_reason") or sig.get("old_wang_reason") or "",
    }


def _fmt_task_price(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text


def _entry_plan(sig: dict) -> str:
    low = sig.get("entry_price_low")
    high = sig.get("entry_price_high")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        if round(float(low), 2) == round(float(high), 2):
            return _fmt_task_price(low)
        return f"{_fmt_task_price(low)} - {_fmt_task_price(high)}"
    return "不建議新進場"


def _exit_plan(sig: dict) -> str:
    target = sig.get("target_price")
    if isinstance(target, (int, float)):
        return f"目標/壓力 {_fmt_task_price(target)}"
    return "先看失效條件"


def _task_bucket(sig: dict) -> str:
    action = sig.get("daily_action")
    internal = sig.get("internal_signal")
    if action in {"reduce", "exit"} or internal in {"exit_warning", "invalidated"} or sig.get("strategy_alignment") == "conflict":
        return "priority_reduce"
    if action == "enter" or internal in {"entry_confirmed", "ready_to_enter"}:
        return "entry_candidates"
    if action == "hold" or internal == "hold":
        return "continue_hold"
    if action == "wait_pullback":
        return "wait_pullback"
    if action == "avoid" or internal == "take_profit_warning":
        return "avoid_no_chase"
    if action == "long_watch":
        return "long_watch"
    return "unassigned_watch"


def _tomorrow_task(sig: dict) -> dict:
    bucket = _task_bucket(sig)
    return {
        "bucket": bucket,
        "code": sig.get("code"),
        "name": sig.get("name") or sig.get("code"),
        "trigger_action": sig.get("daily_action_label") or sig.get("daily_action") or "觀察",
        "daily_action": sig.get("daily_action"),
        "watch_price": sig.get("daily_key_price") or "",
        "entry_plan": _entry_plan(sig),
        "stop_plan": f"停損/失效 {_fmt_task_price(sig.get('stop_price'))}" if isinstance(sig.get("stop_price"), (int, float)) else sig.get("daily_invalidation") or "",
        "exit_plan": _exit_plan(sig),
        "invalidation": sig.get("daily_invalidation") or "",
        "priority": sig.get("daily_priority") or 0,
        "reason": sig.get("daily_action_reason") or sig.get("no_buy_reason") or sig.get("old_wang_reason") or "",
        "price_plan_note": sig.get("price_plan_note") or "",
    }


def _tomorrow_tasks(signals: list[dict]) -> list[dict]:
    bucket_rank = {
        "priority_reduce": 0,
        "entry_candidates": 1,
        "continue_hold": 2,
        "wait_pullback": 3,
        "avoid_no_chase": 4,
        "long_watch": 5,
        "unassigned_watch": 6,
    }

    tasks = [_tomorrow_task(sig) for sig in signals if sig.get("code")]
    return sorted(
        tasks,
        key=lambda task: (
            bucket_rank.get(str(task.get("bucket")), 99),
            -_as_float(task.get("priority")),
            str(task.get("code") or ""),
        ),
    )


def _decision_hint(bucket: str, sig: dict | None = None) -> str:
    if sig and sig.get("daily_action_label"):
        return str(sig.get("daily_action_label"))
    return {
        "priority_reduce": "優先處理風險",
        "entry_candidates": "可分批評估",
        "continue_hold": "續抱觀察",
        "wait_pullback": "等回測",
        "avoid_no_chase": "不追價",
        "long_watch": "長期觀察",
        "unassigned_watch": "觀察",
    }.get(bucket, "觀察")


def _manual_watchlist_review(active_manual_note: dict | None, signals: list[dict]) -> dict:
    playbook = (active_manual_note or {}).get("playbook") if active_manual_note else None
    watch_codes = list((playbook or {}).get("watch_codes") or [])
    by_code = {str(sig.get("code")): sig for sig in signals if sig.get("code")}
    items: list[dict] = []
    summary = {
        "total": len(watch_codes),
        "found_count": 0,
        "missing_count": 0,
        "continue_hold_count": 0,
        "wait_pullback_count": 0,
        "entry_candidates_count": 0,
        "priority_reduce_count": 0,
        "avoid_no_chase_count": 0,
        "long_watch_count": 0,
        "unassigned_watch_count": 0,
    }

    for code in watch_codes:
        sig = by_code.get(str(code))
        if not sig:
            summary["missing_count"] += 1
            items.append({
                "code": str(code),
                "name": str(code),
                "found": False,
                "bucket": "missing",
                "decision_hint": "不在追蹤清單",
                "reason": "人工筆記提到，但目前 signals universe 沒有此代碼",
                "watch_price": "",
                "entry_plan": "不建議新進場",
                "stop_plan": "",
                "invalidation": "",
            })
            continue

        task = _tomorrow_task(sig)
        bucket = str(task.get("bucket") or "unassigned_watch")
        counter_key = f"{bucket}_count"
        if counter_key in summary:
            summary[counter_key] += 1
        summary["found_count"] += 1
        items.append({
            **_brief_stock(sig),
            "found": True,
            "bucket": bucket,
            "decision_hint": _decision_hint(bucket, sig),
            "watch_price": task.get("watch_price") or "",
            "entry_plan": task.get("entry_plan") or "",
            "stop_plan": task.get("stop_plan") or "",
            "exit_plan": task.get("exit_plan") or "",
            "invalidation": task.get("invalidation") or "",
            "reason": task.get("reason") or "",
            "price_plan_note": task.get("price_plan_note") or "",
        })

    return {"items": items, "summary": summary}


def _rotation_plan(signals: list[dict]) -> dict:
    def sort_key(sig: dict) -> tuple:
        alignment_rank = {
            "strong_alignment": 3,
            "single_strategy": 2,
            "conflict": 1,
            "no_alignment": 0,
        }.get(str(sig.get("strategy_alignment") or ""), 0)
        return (
            alignment_rank,
            _as_float(sig.get("daily_priority")),
            _as_float(sig.get("old_wang_score")),
            _as_float(sig.get("score")),
        )

    def code_of(sig: dict) -> str:
        return str(sig.get("code") or "")

    def unique(items: list[dict], assigned: set[str]) -> list[dict]:
        result: list[dict] = []
        for item in items:
            code = code_of(item)
            if not code or code in assigned:
                continue
            assigned.add(code)
            result.append(item)
        return result

    raw_continue_hold = [
        sig for sig in signals
        if sig.get("daily_action") == "hold"
        or sig.get("internal_signal") == "hold"
    ]
    raw_wait_pullback = [
        sig for sig in signals
        if sig.get("daily_action") == "wait_pullback"
    ]
    raw_entry_candidates = [
        sig for sig in signals
        if sig.get("daily_action") == "enter"
        or sig.get("internal_signal") in {"entry_confirmed", "ready_to_enter"}
    ]
    raw_priority_reduce = [
        sig for sig in signals
        if sig.get("daily_action") in {"reduce", "exit"}
        or sig.get("internal_signal") in {"exit_warning", "invalidated"}
        or sig.get("strategy_alignment") == "conflict"
    ]
    raw_avoid_no_chase = [
        sig for sig in signals
        if sig.get("daily_action") == "avoid"
        or sig.get("internal_signal") == "take_profit_warning"
    ]

    assigned: set[str] = set()
    priority_reduce = unique(sorted(raw_priority_reduce, key=sort_key, reverse=True), assigned)
    entry_candidates = unique(sorted(raw_entry_candidates, key=sort_key, reverse=True), assigned)
    continue_hold = unique(sorted(raw_continue_hold, key=sort_key, reverse=True), assigned)
    wait_pullback = unique(sorted(raw_wait_pullback, key=sort_key, reverse=True), assigned)
    avoid_no_chase = unique(sorted(raw_avoid_no_chase, key=sort_key, reverse=True), assigned)

    return {
        "continue_hold": [_brief_stock(sig) for sig in continue_hold[:20]],
        "wait_pullback": [_brief_stock(sig) for sig in wait_pullback[:20]],
        "entry_candidates": [_brief_stock(sig) for sig in entry_candidates[:15]],
        "priority_reduce": [_brief_stock(sig) for sig in priority_reduce[:20]],
        "avoid_no_chase": [_brief_stock(sig) for sig in avoid_no_chase[:20]],
        "summary": {
            "continue_hold_count": len(continue_hold),
            "wait_pullback_count": len(wait_pullback),
            "entry_candidates_count": len(entry_candidates),
            "priority_reduce_count": len(priority_reduce),
            "avoid_no_chase_count": len(avoid_no_chase),
        },
    }


def _position_level(manual_note: dict | None, market_context: dict) -> dict:
    note = manual_note or {}
    source = note.get("source") or "system"
    text = " ".join(str(note.get(key, "")) for key in ("headline", "position_guidance", "title"))
    target_level = "依系統水位"
    if "五成" in text:
        target_level = "五成"
    elif "三成" in text:
        target_level = "三成"
    elif "七成" in text:
        target_level = "七成"

    return {
        "target_level": target_level,
        "risk_level": note.get("risk_level") or market_context.get("old_wang_market_filter") or market_context.get("market_filter") or "neutral",
        "source": source,
        "reason": note.get("position_guidance") or market_context.get("old_wang_market_reason") or market_context.get("reason") or "",
        "market_filter": market_context.get("market_filter"),
        "old_wang_market_filter": market_context.get("old_wang_market_filter"),
        "old_wang_market_reason": market_context.get("old_wang_market_reason"),
    }


def _manual_note_status(manual_note: dict | None) -> dict | None:
    if not manual_note:
        return None
    return {
        "date": manual_note.get("date"),
        "applies_to_as_of": manual_note.get("applies_to_as_of"),
        "title": manual_note.get("title"),
        "is_stale": bool(manual_note.get("is_stale")),
        "update_required": bool(manual_note.get("update_required") or manual_note.get("is_stale")),
        "stale_trading_days": manual_note.get("stale_trading_days"),
        "status_label": manual_note.get("status_label"),
        "stale_reason": manual_note.get("stale_reason") or "",
    }


def _sector_focus(signals: list[dict]) -> list[dict]:
    sectors: dict[str, dict] = defaultdict(lambda: {
        "sector": "",
        "old_wang_count": 0,
        "watch_count": 0,
        "avg_old_wang_score": 0.0,
        "top_stocks": [],
        "_score_sum": 0.0,
    })

    for sig in signals:
        sector = str(sig.get("old_wang_sector") or "").strip()
        if not sector:
            continue
        item = sectors[sector]
        item["sector"] = sector
        score = _as_float(sig.get("old_wang_score"))
        item["_score_sum"] += score
        if _as_bool(sig.get("old_wang_flag")):
            item["old_wang_count"] += 1
        if sig.get("internal_signal") in {"watchlist", "hold", "take_profit_warning"}:
            item["watch_count"] += 1
        item["top_stocks"].append({
            "code": sig.get("code"),
            "name": sig.get("name") or sig.get("code"),
            "old_wang_score": score,
            "old_wang_signal": sig.get("old_wang_signal"),
        })

    result = []
    for item in sectors.values():
        total = len(item["top_stocks"]) or 1
        item["avg_old_wang_score"] = round(item["_score_sum"] / total, 1)
        item["top_stocks"] = sorted(
            item["top_stocks"],
            key=lambda s: _as_float(s.get("old_wang_score")),
            reverse=True,
        )[:5]
        item.pop("_score_sum", None)
        result.append(item)

    return sorted(
        result,
        key=lambda s: (s["old_wang_count"], s["avg_old_wang_score"]),
        reverse=True,
    )[:8]


def build_daily_brief(summary: dict) -> dict:
    signals = list(summary.get("signals") or [])
    market_context = summary.get("market_context") or {}
    manual_note = summary.get("manual_market_note") or None
    active_manual_note = None if (manual_note or {}).get("is_stale") else manual_note

    def old_wang_score(sig: dict) -> float:
        return _as_float(sig.get("old_wang_score"))

    def has_any_old_wang_signal(sig: dict, names: set[str]) -> bool:
        return bool(_split_signal(sig.get("old_wang_signal")) & names)

    keep_strong = [
        sig for sig in signals
        if _as_bool(sig.get("old_wang_flag"))
        and sig.get("internal_signal") in {"watchlist", "hold", "take_profit_warning"}
        and (
            sig.get("old_wang_support_state") in {"short_stop_trend_intact", "all_ma_reclaim"}
            or has_any_old_wang_signal(sig, {"previous_high_breakout", "volume_low_support", "parabolic_ma10_hold", "gap_up_support"})
        )
    ]
    keep_strong.sort(key=old_wang_score, reverse=True)

    no_chase_keywords = ("RSI", "R/R", "風險報酬", "距 MA20 過遠", "過熱", "不追價")
    no_chase = [
        sig for sig in signals
        if sig.get("internal_signal") in {"watchlist", "take_profit_warning"}
        and any(keyword in str(sig.get("no_buy_reason") or "") for keyword in no_chase_keywords)
    ]
    no_chase.sort(key=old_wang_score, reverse=True)

    trim_weak = [
        sig for sig in signals
        if sig.get("internal_signal") in {"exit_warning", "invalidated"}
    ]
    trim_weak.sort(key=lambda sig: (sig.get("internal_signal") != "invalidated", _as_float(sig.get("score"))))

    entry_watch = [
        sig for sig in signals
        if sig.get("internal_signal") in {"entry_confirmed", "ready_to_enter"} or sig.get("signal") == "BUY"
    ]
    entry_watch.sort(
        key=lambda sig: (_as_float(sig.get("entry_score")), _as_float(sig.get("reward_risk_ratio"))),
        reverse=True,
    )

    buffett_total = sum(1 for sig in signals if sig.get("buffett_data_ok") is not None)
    buffett_ready = sum(1 for sig in signals if _as_bool(sig.get("buffett_data_ok")))
    buffett_candidates = [
        _brief_stock(sig, reason_key="buffett_reason")
        for sig in signals
        if _as_bool(sig.get("buffett_flag"))
    ]

    note_rules = []
    if active_manual_note:
        note_rules = list(active_manual_note.get("rules") or active_manual_note.get("market_actions") or [])[:8]

    sector_focus = _sector_focus(signals)
    return {
        "as_of": summary.get("as_of"),
        "generated_at": summary.get("generated_at"),
        "brief_generated_from": "summary.json",
        "data_status": _data_status(summary),
        "position_guidance": _position_level(active_manual_note, market_context),
        "manual_playbook": (active_manual_note or {}).get("playbook") if active_manual_note else None,
        "manual_watchlist_review": _manual_watchlist_review(active_manual_note, signals),
        "manual_note_title": (manual_note or {}).get("title"),
        "manual_note_status": _manual_note_status(manual_note),
        "market_context": market_context,
        "sector_focus": sector_focus,
        "rotation_plan": _rotation_plan(signals),
        "tomorrow_tasks": _tomorrow_tasks(signals),
        "keep_strong": [_brief_stock(sig, reason_key="old_wang_reason") for sig in keep_strong[:15]],
        "no_chase": [_brief_stock(sig, reason_key="no_buy_reason") for sig in no_chase[:15]],
        "trim_weak": [_brief_stock(sig, reason_key="no_buy_reason") for sig in trim_weak[:20]],
        "entry_watch": [_brief_stock(sig) for sig in entry_watch[:15]],
        "buffett_status": {
            "total": buffett_total,
            "ready": buffett_ready,
            "missing": max(buffett_total - buffett_ready, 0),
            "candidates": buffett_candidates[:15],
            "note": "Buffett 方案需要 fundamentals.csv 欄位補齊後才會產生候選。",
        },
        "tomorrow_checklist": note_rules,
        "summary": {
            "keep_strong_count": len(keep_strong),
            "no_chase_count": len(no_chase),
            "trim_weak_count": len(trim_weak),
            "entry_watch_count": len(entry_watch),
            "sector_focus_count": len(sector_focus),
        },
    }


def write_daily_brief(summary: dict, out_dir: Path | None = None) -> Path:
    target_dir = out_dir or _OUT
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "daily_brief.json"
    atomic_write_text(path, json.dumps(build_daily_brief(summary), ensure_ascii=False, indent=2))
    return path


def get_daily_brief(out_dir: Path | None = None) -> dict | None:
    target_dir = out_dir or _OUT
    path = target_dir / "daily_brief.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_manual_watchlist_review(out_dir: Path | None = None) -> dict | None:
    brief = get_daily_brief(out_dir)
    if not brief:
        return None
    review = brief.get("manual_watchlist_review")
    if not isinstance(review, dict):
        return None
    return {
        "as_of": brief.get("as_of"),
        "generated_at": brief.get("generated_at"),
        "manual_note_title": brief.get("manual_note_title"),
        "position_guidance": brief.get("position_guidance"),
        "manual_playbook": brief.get("manual_playbook"),
        "items": list(review.get("items") or []),
        "summary": dict(review.get("summary") or {}),
    }
