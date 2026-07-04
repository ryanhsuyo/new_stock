#!/usr/bin/env python3
"""每日 PM 摘要入口：把 doctor 報告收斂成今天優先待辦。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.storage.atomic_write import atomic_write_text  # noqa: E402
from app.services.signal_alert_service import load_signal_alerts  # noqa: E402
from app.services.official_fundamentals_api_service import get_official_fundamentals_coverage_audit  # noqa: E402
from app.services.signals_service import get_universe  # noqa: E402
from app.services.today_scan_service import load_today_scan_report  # noqa: E402
from app.services.workflow_outputs import expected_outputs_for_command  # noqa: E402
from app.services.workflow_text import preview_numbered_lines  # noqa: E402
from doctor import build_doctor_report  # noqa: E402

_SEVERITY_RANK = {"block": 0, "warn": 1, "ok": 2}
_ACTION_KEY_RANK = {
    "outputs": 0,
    "signal_alerts": 1,
    "data_repair": 2,
    "data_freshness": 3,
    "manual_market_note": 4,
    "fundamentals": 5,
    "official_fundamentals_coverage": 6,
    "today_scan": 7,
    "decision_journal": 8,
}
_DATA_REPAIR_COMMAND = "python3 scripts/daily_update.py --months 12"
_DATA_FRESHNESS_COMMAND = "python3 scripts/daily_update.py --months 1"
_SIGNAL_ALERTS_FILE = "backend/out/signal_alerts.json"
_SIGNAL_ALERTS_COMMAND = f"cat {_SIGNAL_ALERTS_FILE}"
_DATA_REPAIR_REQUIRED_ROWS = 60

def _copy_command(command: str) -> str:
    return f"cd {_BACKEND}\n{command}"


def _expected_outputs_for_command(command: str) -> list[str]:
    return expected_outputs_for_command(command)


def _data_as_of_from_report(report: dict[str, Any]) -> str | None:
    for check in report.get("checks") or []:
        if check.get("key") != "outputs":
            continue
        details = check.get("details") or {}
        return (
            details.get("last_data_as_of")
            or details.get("summary_as_of")
            or details.get("daily_brief_as_of")
            or details.get("universe_as_of")
        )
    return None


def _can_use_trade_outputs(report: dict[str, Any]) -> bool:
    checks = report.get("checks") or []
    return not any(
        check.get("key") in {"outputs", "data_coverage"} and check.get("status") == "block"
        for check in checks
    )


def _data_repair_summary(universe: list[dict[str, Any]] | None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    counts = {"no_data": 0, "insufficient": 0}
    label_by_status = {
        "no_data": "尚未回補",
        "insufficient": "資料不足",
    }

    for raw in universe or []:
        status = str(raw.get("data_status") or "")
        if status not in counts:
            continue
        counts[status] += 1
        items.append({
            "code": str(raw.get("code") or ""),
            "name": str(raw.get("name") or raw.get("code") or ""),
            "status": status,
            "status_label": label_by_status[status],
            "row_count": int(raw.get("row_count") or 0),
            "required_rows": _DATA_REPAIR_REQUIRED_ROWS,
            "last_data_as_of": raw.get("last_data_as_of"),
        })

    items.sort(key=lambda item: (0 if item["status"] == "no_data" else 1, item["code"]))
    return {
        "total_count": len(items),
        "no_data_count": counts["no_data"],
        "insufficient_count": counts["insufficient"],
        "command": _DATA_REPAIR_COMMAND,
        "top_items": items[:8],
    }


def _data_repair_action(repair: dict[str, Any]) -> dict[str, Any] | None:
    total = int(repair.get("total_count") or 0)
    if total <= 0:
        return None
    return {
        "key": "data_repair",
        "status": "warn",
        "title": "追蹤股票資料修復",
        "message": (
            f"有 {total} 檔追蹤股票缺日線或資料不足"
            f"（無日線 {repair.get('no_data_count') or 0} / 不足 {repair.get('insufficient_count') or 0}）。"
        ),
        "next_action": str(repair.get("command") or _DATA_REPAIR_COMMAND),
        "action_payload": {
            "kind": "command",
            "command": str(repair.get("command") or _DATA_REPAIR_COMMAND),
            "copy_command": _copy_command(str(repair.get("command") or _DATA_REPAIR_COMMAND)),
            "expected_outputs": _expected_outputs_for_command(str(repair.get("command") or _DATA_REPAIR_COMMAND)),
        },
    }


def _official_coverage_action() -> dict[str, Any] | None:
    payload = {
        "kind": "api",
        "method": "GET",
        "endpoint": "/api/system/fundamentals-official/coverage-audit",
        "confirm_message": "只讀取官方基本面覆蓋率稽核，不會產生報告或寫入正式基本面資料。",
    }
    try:
        audit = get_official_fundamentals_coverage_audit()
    except FileNotFoundError as exc:
        return {
            "key": "official_fundamentals_coverage",
            "status": "warn",
            "title": "官方基本面覆蓋率稽核尚未可讀",
            "message": f"{exc}。先產生或補齊 backend/out/fundamentals_priority_fill.csv，再重新檢查。",
            "next_action": "GET /api/system/fundamentals-official/coverage-audit",
            "details": {
                "missing_priority_csv": True,
                "blocked_reason": str(exc),
            },
            "action_payload": payload,
        }

    missing_reports = list(audit.get("missing_report_files") or [])
    try:
        coverage_pct = float(audit.get("coverage_pct") or 0)
    except (TypeError, ValueError):
        coverage_pct = 0.0
    if not missing_reports and coverage_pct >= 80:
        return None

    next_action = str(audit.get("next_action_label") or "查看官方基本面覆蓋率稽核，確認缺少的 report-only CSV 或缺列。")
    blocked_fields = list(audit.get("blocked_formal_fields") or [])
    missing_label = "、".join(str(item) for item in missing_reports[:3])
    if len(missing_reports) > 3:
        missing_label = f"{missing_label} 等 {len(missing_reports)} 份"
    message = f"官方 report-only 覆蓋率 {coverage_pct:.1f}%"
    if missing_label:
        message = f"{message}，缺少 {missing_label}"
    return {
        "key": "official_fundamentals_coverage",
        "status": "warn",
        "title": "官方基本面覆蓋率待確認",
        "message": f"{message}。",
        "next_action": next_action,
        "details": {
            "target_count": int(audit.get("target_count") or 0),
            "coverage_pct": coverage_pct,
            "available_cell_count": int(audit.get("available_cell_count") or 0),
            "missing_report_files": missing_reports,
            "blocked_formal_fields": blocked_fields,
        },
        "action_payload": payload,
    }


def _signal_alert_action(alerts: dict[str, Any] | None) -> dict[str, Any] | None:
    if not alerts or int(alerts.get("alert_count") or 0) <= 0:
        return None
    severity_counts = alerts.get("severity_counts") or {}
    status = "block" if int(severity_counts.get("block") or 0) > 0 else "warn"
    alert_count = int(alerts.get("alert_count") or 0)
    severity_rank = {"block": 0, "warn": 1, "info": 2}
    sorted_alerts = sorted(
        alerts.get("alerts") or [],
        key=lambda item: (
            severity_rank.get(str(item.get("severity") or ""), 9),
            str(item.get("code") or ""),
        ),
    )

    def _preview_item(item: dict[str, Any]) -> str:
        base = f"{item.get('code')} {item.get('name')}：{item.get('title')}"
        action_label = str(item.get("action_label") or "").strip()
        return f"{base}｜{action_label}" if action_label else base

    def _preview_alert(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "severity": str(item.get("severity") or ""),
            "code": str(item.get("code") or ""),
            "name": str(item.get("name") or ""),
            "title": str(item.get("title") or ""),
            "action_label": str(item.get("action_label") or ""),
            "review_focus": list(item.get("review_focus") or []),
        }

    def _review_focus_counts(items: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            for focus in item.get("review_focus") or []:
                key = str(focus or "").strip()
                if key:
                    counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def _review_checklist_item(item: dict[str, Any]) -> str:
        code = str(item.get("code") or "")
        name = str(item.get("name") or "")
        action_label = str(item.get("action_label") or "復盤").strip()
        focus_items = [str(focus) for focus in item.get("review_focus") or [] if str(focus).strip()]
        focus_text = " / ".join(focus_items) if focus_items else "訊號變化原因"
        return f"{code} {name}：{action_label}；檢查 {focus_text}。"

    preview_alerts = sorted_alerts[:5]
    review_checklist = [_review_checklist_item(item) for item in preview_alerts]
    return {
        "key": "signal_alerts",
        "status": status,
        "title": "訊號快照變化警示",
        "message": str(alerts.get("message") or f"有 {alert_count} 筆訊號快照變化警示。"),
        "next_action": "查看 backend/out/signal_alerts.json 並先處理 block / warn 項目。",
        "details": {
            "as_of": alerts.get("as_of"),
            "previous_as_of": alerts.get("previous_as_of"),
            "alert_count": alert_count,
            "severity_counts": severity_counts,
            "block_count": int(severity_counts.get("block") or 0),
            "warn_count": int(severity_counts.get("warn") or 0),
            "info_count": int(severity_counts.get("info") or 0),
        },
        "action_payload": {
            "kind": "file",
            "file_path": _SIGNAL_ALERTS_FILE,
            "copy_command": _copy_command(_SIGNAL_ALERTS_COMMAND),
            "expected_outputs": [_SIGNAL_ALERTS_FILE],
            "preview_items": [_preview_item(item) for item in preview_alerts],
            "preview_alerts": [_preview_alert(item) for item in preview_alerts],
            "review_focus_counts": _review_focus_counts(preview_alerts),
            "review_checklist": review_checklist,
            "review_checklist_copy_text": "\n".join(
                ["訊號快照復盤清單"]
                + [f"{index}. {item}" for index, item in enumerate(review_checklist, start=1)]
            ),
        },
    }


def _manual_market_note_action(signals_summary: dict[str, Any] | None, data_as_of: str | None = None) -> dict[str, Any] | None:
    note = (signals_summary or {}).get("manual_market_note") or {}
    if not note.get("update_required") and not note.get("is_stale"):
        return None
    note_date = str(note.get("date") or "")
    title = str(note.get("title") or "人工盤後筆記")
    status_label = str(note.get("status_label") or "需更新")
    stale_reason = str(note.get("stale_reason") or "人工盤後筆記已過期，請更新今天盤勢。")
    preview = f"{status_label}{f' {note_date}' if note_date else ''}：{title}"
    return {
        "key": "manual_market_note",
        "status": "warn",
        "title": "更新人工盤後筆記",
        "message": stale_reason,
        "next_action": "POST /api/stocks/market-notes",
        "details": {
            "note_date": note_date,
            "stale_trading_days": note.get("stale_trading_days"),
            "status_label": status_label,
        },
        "action_payload": {
            "kind": "api",
            "method": "POST",
            "endpoint": "/api/stocks/market-notes",
            "confirm_message": "只更新盤後筆記，不改交易紀錄。",
            "preview_items": [preview],
            "required_fields": [
                "date",
                "title",
                "risk_level",
                "headline",
                "market_actions",
                "index_notes",
                "stock_notes",
                "rules",
            ],
            "writing_checklist": [
                "填入這次盤後筆記適用日期。",
                "用你自己的盤後觀察填 headline / market_actions / index_notes。",
                "只送出盤後筆記，不會修改交易紀錄、持倉或現金。",
            ],
            "example_payload": {
                "date": str(data_as_of or ""),
                "title": "",
                "risk_level": "",
                "headline": "",
                "source": "manual",
                "market_actions": [],
                "index_notes": [],
                "stock_notes": [],
                "rules": [],
            },
        },
        "action_type": "market_note",
    }


def _item_label(item: dict[str, Any]) -> str:
    code = str(item.get("code") or "")
    name = str(item.get("name") or code)
    return f"{code} {name}".strip()


def _today_scan_summary(today_scan: dict[str, Any] | None) -> dict[str, Any]:
    today_scan = today_scan or {}
    formal_entries = today_scan.get("formal_entries") or []
    old_wang = today_scan.get("old_wang_candidates") or []
    steady = today_scan.get("steady_momentum_candidates") or []
    risks = today_scan.get("risk_items") or []
    return {
        "as_of": today_scan.get("as_of"),
        "generated_at": today_scan.get("generated_at"),
        "formal_entry_count": len(formal_entries),
        "old_wang_count": len(old_wang),
        "steady_momentum_count": len(steady),
        "risk_count": len(risks),
        "data_freshness": today_scan.get("data_freshness") or {},
        "notes": today_scan.get("notes") or [],
        "top_formal_entries": formal_entries[:5],
        "top_risk_items": risks[:5],
    }


def _today_scan_action(today_scan_summary: dict[str, Any], can_use_trade_outputs: bool) -> dict[str, Any] | None:
    if not can_use_trade_outputs:
        return None
    counts = {
        "formal": int(today_scan_summary.get("formal_entry_count") or 0),
        "old_wang": int(today_scan_summary.get("old_wang_count") or 0),
        "steady": int(today_scan_summary.get("steady_momentum_count") or 0),
        "risk": int(today_scan_summary.get("risk_count") or 0),
    }
    if not any(counts.values()):
        return None
    preview_items: list[str] = []
    formal_labels = [_item_label(item) for item in today_scan_summary.get("top_formal_entries") or []]
    risk_labels = [_item_label(item) for item in today_scan_summary.get("top_risk_items") or []]
    if formal_labels:
        preview_items.append(f"可小試：{', '.join(formal_labels[:5])}")
    if risk_labels:
        preview_items.append(f"風險：{', '.join(risk_labels[:5])}")
    freshness = today_scan_summary.get("data_freshness") or {}
    stale_items = freshness.get("top_stale_items") or []
    stale_count = int(freshness.get("stale_count") or 0)
    if stale_count:
        stale_labels = [
            f"{_item_label(item)} 仍停在 {item.get('data_as_of') or '—'}"
            for item in stale_items[:3]
        ]
        if stale_labels:
            preview_items.append(f"資料日落後：{', '.join(stale_labels)}")
    return {
        "key": "today_scan",
        "status": "warn" if counts["formal"] or counts["risk"] else "ok",
        "title": "今日規則掃描",
        "message": (
            f"可小試 {counts['formal']} 檔、老王觀察 {counts['old_wang']} 檔、"
            f"穩健動能 {counts['steady']} 檔、風險處理 {counts['risk']} 檔。"
        ),
        "next_action": "查看 backend/out/today_scan.json，依分桶做盤後復盤。",
        "details": {
            "as_of": today_scan_summary.get("as_of"),
            "formal_entry_count": counts["formal"],
            "old_wang_count": counts["old_wang"],
            "steady_momentum_count": counts["steady"],
            "risk_count": counts["risk"],
            "data_freshness": freshness,
        },
        "action_payload": {
            "kind": "file",
            "file_path": "backend/out/today_scan.json",
            "preview_items": preview_items,
        },
    }


def _data_freshness_action(today_scan_summary: dict[str, Any], can_use_trade_outputs: bool) -> dict[str, Any] | None:
    if not can_use_trade_outputs:
        return None
    freshness = today_scan_summary.get("data_freshness") or {}
    stale_count = int(freshness.get("stale_count") or 0)
    missing_count = int(freshness.get("missing_date_count") or 0)
    if stale_count <= 0 and missing_count <= 0:
        return None

    stale_items = freshness.get("top_stale_items") or []
    preview_items = [
        f"{_item_label(item)} 仍停在 {item.get('data_as_of') or '—'}"
        for item in stale_items[:8]
    ]
    if missing_count:
        preview_items.append(f"另有 {missing_count} 檔缺少資料日。")

    expected_as_of = freshness.get("expected_as_of") or today_scan_summary.get("as_of") or "最新交易日"
    return {
        "key": "data_freshness",
        "status": "warn",
        "title": "追蹤股票資料日落後",
        "message": f"有 {stale_count} 檔股票資料日落後，目標資料日為 {expected_as_of}。",
        "next_action": _DATA_FRESHNESS_COMMAND,
        "details": {
            "expected_as_of": expected_as_of,
            "row_count": int(freshness.get("row_count") or 0),
            "fresh_count": int(freshness.get("fresh_count") or 0),
            "stale_count": stale_count,
            "missing_date_count": missing_count,
            "top_stale_items": stale_items,
        },
        "action_payload": {
            "kind": "command",
            "command": _DATA_FRESHNESS_COMMAND,
            "copy_command": _copy_command(_DATA_FRESHNESS_COMMAND),
            "expected_outputs": _expected_outputs_for_command(_DATA_FRESHNESS_COMMAND),
            "preview_items": preview_items,
        },
    }


def _normalize_action_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    command = str(normalized.get("command") or "")
    if normalized.get("kind") == "command" and command and not normalized.get("copy_command"):
        normalized["copy_command"] = _copy_command(command)
    if normalized.get("kind") == "command" and command and not normalized.get("expected_outputs"):
        normalized["expected_outputs"] = _expected_outputs_for_command(command)
    if normalized.get("kind") == "copy_text" and not normalized.get("preview_items"):
        normalized["preview_items"] = preview_numbered_lines(str(normalized.get("copy_text") or ""))
    return normalized


def _action_type_for_key(key: str) -> str:
    mapping = {
        "data_repair": "data_repair",
        "data_freshness": "data_freshness",
        "decision_journal": "decision_journal",
        "fundamentals": "fundamentals",
        "official_fundamentals_coverage": "fundamentals",
        "signal_alerts": "signal_alerts",
        "today_scan": "today_scan",
    }
    return mapping.get(key, "daily_check")


def _with_action_type(action: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(action)
    key = str(normalized.get("key") or "")
    normalized["action_type"] = str(normalized.get("action_type") or _action_type_for_key(key))
    return normalized


def _print_action_payload(payload: dict[str, Any]) -> None:
    kind = payload.get("kind")
    preview_items = payload.get("preview_items") or []
    if preview_items:
        print("   預覽：")
        for item in preview_items[:8]:
            print(f"     - {item}")
    if kind == "file" and payload.get("file_path"):
        print(f"   查看檔案：{payload['file_path']}")
    elif kind == "copy_text":
        copy_preview_items = preview_numbered_lines(str(payload.get("copy_text") or ""))
        if copy_preview_items:
            print(f"   優先補基本面：{', '.join(copy_preview_items)}")
        if payload.get("file_path"):
            print(f"   目標檔案：{payload['file_path']}")
        if payload.get("write_template_command"):
            print(f"   產生模板：{payload['write_template_command']}")
        if payload.get("prepare_import_command"):
            print(f"   匯入預覽：{payload['prepare_import_command']}")
        if payload.get("prepare_import_apply_command"):
            print(f"   正式寫入：{payload['prepare_import_apply_command']}")
    elif kind == "api" and payload.get("method") and payload.get("endpoint"):
        print(f"   API 動作：{payload['method']} {payload['endpoint']}")
    if payload.get("confirm_message"):
        print(f"   提醒：{payload['confirm_message']}")
    expected_outputs = payload.get("expected_outputs")
    if expected_outputs:
        print("   跑完檢查：")
        for output in expected_outputs:
            print(f"     - {output}")


def _top_actions(
    report: dict[str, Any],
    limit: int,
    extra_actions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidates = []
    for check in report.get("checks") or []:
        if check.get("status") == "ok" or not check.get("next_action"):
            continue
        item = {
            "key": str(check.get("key") or ""),
            "action_type": _action_type_for_key(str(check.get("key") or "")),
            "status": str(check.get("status") or ""),
            "title": str(check.get("title") or ""),
            "message": str(check.get("message") or ""),
            "next_action": str(check.get("next_action") or ""),
            "details": dict(check.get("details") or {}),
        }
        if isinstance(check.get("action_payload"), dict):
            item["action_payload"] = _normalize_action_payload(check["action_payload"])
        candidates.append(item)
    candidates.extend(_with_action_type(action) for action in (extra_actions or []))
    candidates.sort(
        key=lambda item: (
            _SEVERITY_RANK.get(item["status"], 9),
            _ACTION_KEY_RANK.get(item["key"], 99),
            item["key"],
        )
    )
    return candidates[: max(1, limit)]


def _blocked_by(report: dict[str, Any], extra_actions: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for item in list(report.get("checks") or []) + list(extra_actions or []):
        if item.get("status") != "block":
            continue
        blockers.append({
            "key": str(item.get("key") or ""),
            "title": str(item.get("title") or ""),
            "message": str(item.get("message") or ""),
        })
    return blockers


def _status_reason(
    report: dict[str, Any],
    top_actions: list[dict[str, Any]],
    blockers: list[dict[str, str]],
) -> str:
    if blockers:
        first = blockers[0]
        title = first.get("title") or first.get("key") or "阻塞項目"
        message = first.get("message") or "需先處理阻塞項目。"
        return f"{title} 阻塞交易輸出：{message}"

    status = str(report.get("overall_status") or "unknown")
    if status == "ok":
        return "Daily Check 未發現阻塞或警示，交易輸出可回顧。"

    for action in top_actions:
        if action.get("key") == "fundamentals":
            return "基本面避雷資料不足，因此 Daily Check 維持 WARN；這不會阻塞交易輸出，但基本面輔助分數需保守看待。"
    if top_actions:
        first = top_actions[0]
        title = first.get("title") or first.get("key") or "待辦"
        message = first.get("message") or "有待處理項目。"
        return f"{title} 需要處理：{message}"
    return "Daily Check 狀態不是 OK，但目前沒有可排序的待辦，請查看 doctor report。"


def _trade_outputs_note(can_use_trade_outputs: bool, top_actions: list[dict[str, Any]]) -> str:
    if not can_use_trade_outputs:
        return "交易輸出目前不可作為今天判斷依據；請先處理 blocked 項目並重新產生輸出。"
    if any(action.get("key") == "fundamentals" for action in top_actions):
        return "交易輸出仍可回顧；但基本面避雷資料不足，穩健動能的基本面輔助分數需保守看待。"
    return "交易輸出可回顧；仍請依 top actions 檢查警示與盤後待辦。"


def build_daily_summary(
    report: dict[str, Any],
    limit: int = 3,
    universe: list[dict[str, Any]] | None = None,
    signal_alerts: dict[str, Any] | None = None,
    today_scan: dict[str, Any] | None = None,
    signals_summary: dict[str, Any] | None = None,
    include_official_coverage: bool = False,
) -> dict[str, Any]:
    generated_at = report.get("generated_at")
    data_repair = _data_repair_summary(universe)
    can_use_trade_outputs = _can_use_trade_outputs(report)
    today_scan_summary = _today_scan_summary(today_scan)
    data_as_of = _data_as_of_from_report(report)
    extra_actions = [
        action
        for action in [
            _signal_alert_action(signal_alerts),
            _data_freshness_action(today_scan_summary, can_use_trade_outputs),
            _manual_market_note_action(signals_summary, data_as_of),
            _today_scan_action(today_scan_summary, can_use_trade_outputs),
            _data_repair_action(data_repair),
            _official_coverage_action() if include_official_coverage else None,
        ]
        if action
    ]
    top_actions = _top_actions(report, limit=limit, extra_actions=extra_actions)
    blockers = _blocked_by(report, extra_actions)
    effective_can_use_trade_outputs = can_use_trade_outputs and not blockers
    return {
        "overall_status": report.get("overall_status"),
        "exit_code": int(report.get("exit_code") or 0),
        "generated_at": generated_at,
        "source_report_generated_at": generated_at,
        "data_as_of": data_as_of,
        "can_use_trade_outputs": effective_can_use_trade_outputs,
        "status_reason": _status_reason(report, top_actions, blockers),
        "trade_outputs_note": _trade_outputs_note(effective_can_use_trade_outputs, top_actions),
        "blocked_by": blockers,
        "data_repair": data_repair,
        "today_scan": today_scan_summary,
        "signal_alerts": signal_alerts or {
            "alert_count": 0,
            "severity_counts": {},
            "alerts": [],
            "message": "尚未產生 signal_alerts.json，請先執行 run_signals.py。",
        },
        "top_actions": top_actions,
    }


def print_daily_summary(summary: dict[str, Any]) -> None:
    status = str(summary.get("overall_status") or "unknown").upper()
    data_as_of = summary.get("data_as_of") or "unknown"
    trade_status = "可使用/可回顧" if summary.get("can_use_trade_outputs") else "不可作為今天交易依據"
    repair = summary.get("data_repair") or {}
    print(f"每日檢查：{status}")
    print(f"資料日：{data_as_of}")
    print(f"交易輸出：{trade_status}")
    if repair.get("total_count"):
        print(
            "資料修復："
            f"{repair.get('total_count')} 檔"
            f"（無日線 {repair.get('no_data_count') or 0} / 不足 {repair.get('insufficient_count') or 0}）"
        )
    today_scan = summary.get("today_scan") or {}
    if any(int(today_scan.get(key) or 0) for key in ("formal_entry_count", "old_wang_count", "steady_momentum_count", "risk_count")):
        print(
            "今日掃描："
            f"可小試 {today_scan.get('formal_entry_count') or 0} / "
            f"老王 {today_scan.get('old_wang_count') or 0} / "
            f"穩健 {today_scan.get('steady_momentum_count') or 0} / "
            f"風險 {today_scan.get('risk_count') or 0}"
        )

    actions = summary.get("top_actions") or []
    if not actions:
        print("優先待辦：無")
        return

    print("優先待辦：")
    for idx, action in enumerate(actions, start=1):
        print(f"{idx}. [{action['status'].upper()}] {action['title']}")
        print(f"   {action['message']}")
        missing_codes = (action.get("details") or {}).get("missing_codes") or []
        if missing_codes:
            preview = ", ".join(str(code) for code in missing_codes[:10])
            suffix = " ..." if len(missing_codes) > 10 else ""
            print(f"   缺少復盤代碼：{preview}{suffix}")
        print(f"   下一步：{action['next_action']}")
        payload = action.get("action_payload")
        if isinstance(payload, dict):
            _print_action_payload(payload)


def write_daily_summary(summary: dict[str, Any], backend: Path) -> Path:
    path = backend / "out" / "daily_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(summary, ensure_ascii=False, indent=2))
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每日 PM 摘要：資料日、交易輸出狀態與 Top N 待辦")
    parser.add_argument("--backend", type=Path, default=_BACKEND, help="backend 目錄路徑")
    parser.add_argument("--limit", type=int, default=3, help="最多顯示幾個優先待辦")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    parser.add_argument("--write-report", action="store_true", help="寫出 backend/out/daily_check.json")
    return parser.parse_args(argv)


def load_universe_for_daily_check() -> list[dict[str, Any]]:
    try:
        return get_universe()
    except Exception as exc:  # pragma: no cover - 防止每日摘要因資料狀態查詢失敗而中斷
        print(f"[WARN] 無法載入 universe 資料修復狀態：{exc}", file=sys.stderr)
        return []


def load_summary_for_daily_check(backend: Path) -> dict[str, Any] | None:
    path = backend / "out" / "summary.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - 防止每日摘要因 summary 解析失敗而中斷
        print(f"[WARN] 無法載入 summary.json 人工筆記狀態：{exc}", file=sys.stderr)
        return None


def run_daily_check(args: argparse.Namespace) -> int:
    report = build_doctor_report(args.backend)
    summary = build_daily_summary(
        report,
        limit=args.limit,
        universe=load_universe_for_daily_check(),
        signal_alerts=load_signal_alerts(args.backend / "out"),
        today_scan=load_today_scan_report(args.backend / "out"),
        signals_summary=load_summary_for_daily_check(args.backend),
        include_official_coverage=args.backend.resolve() == _BACKEND.resolve(),
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_daily_summary(summary)
    if args.write_report:
        path = write_daily_summary(summary, args.backend)
        if not args.json:
            print(f"已寫出：{path}")
    return int(summary.get("exit_code") or 0)


def main() -> None:
    raise SystemExit(run_daily_check(parse_args()))


if __name__ == "__main__":
    main()
