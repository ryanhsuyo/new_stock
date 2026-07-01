"""PM 首頁工作佇列：把各子流程摘要收斂成今日優先順序。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.daily_check_service import get_daily_check_report
from app.services.decision_journal_service import build_universe_report_review_workflow_summary
from app.services.fundamental_service import get_fundamentals_status
from app.services.official_fundamentals_api_service import get_official_fundamentals_coverage_audit
from app.services.signals_service import get_universe, get_universe_report_json
from app.services.update_workflow_service import get_update_workflow_status
from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS
from app.services.workflow_outputs import (
    FUNDAMENTALS_PRIORITY_IMPORT_APPLY_COMMAND,
    FUNDAMENTALS_PRIORITY_IMPORT_COMMAND,
    FUNDAMENTALS_PRIORITY_IMPORT_OUTPUTS,
    FUNDAMENTALS_PRIORITY_TEMPLATE_COMMAND,
)
from app.services.workflow_service import get_workflow_status
from app.services.workflow_text import preview_numbered_lines

_DATA_REPAIR_COMMAND = "python3 scripts/daily_update.py --months 12"
_BACKEND = Path(__file__).resolve().parent.parent.parent
_PRICE_BASIS_LABEL = "最新收盤價（非即時市價）"
_SHORT_REASON_MAX = 42


def _short_display_reason(value: str) -> str:
    text = " ".join(str(value or "").split())
    for separator in ("。", "；", "\n"):
        if separator in text:
            text = text.split(separator, 1)[0]
            break
    if len(text) <= _SHORT_REASON_MAX:
        return text
    for separator in ("，", ","):
        prefix = text.split(separator, 1)[0]
        if 8 <= len(prefix) <= _SHORT_REASON_MAX:
            return prefix
    return f"{text[:_SHORT_REASON_MAX - 1]}…"


def _format_display_price(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _entry_primary_metric(row: dict[str, Any]) -> str:
    low = _format_display_price(row.get("entry_price_low"))
    high = _format_display_price(row.get("entry_price_high"))
    if low and high:
        return f"進場 {low}–{high}"
    if low or high:
        return f"進場 {low or high}"
    key_price = str(row.get("daily_key_price") or "").strip()
    if key_price:
        return key_price
    close = _format_display_price(row.get("close"))
    return f"收盤 {close}" if close else ""


def _normalize_action_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(payload or {})
    if normalized.get("kind") == "copy_text" and not normalized.get("preview_items"):
        normalized["preview_items"] = preview_numbered_lines(str(normalized.get("copy_text") or ""))
    return normalized


def _focus_codes_from_preview_items(payload: dict[str, Any] | None) -> list[str]:
    codes: list[str] = []
    for label in (payload or {}).get("preview_items") or []:
        code = str(label or "").strip().split(" ", 1)[0]
        if code and code.isdigit() and code not in codes:
            codes.append(code)
        if len(codes) >= 5:
            break
    return codes


def _parse_data_freshness_preview(label: str) -> dict[str, str]:
    text = " ".join(str(label or "").split())
    code, _, rest = text.partition(" ")
    name = rest
    data_as_of = ""
    marker = " 仍停在 "
    if marker in rest:
        name, data_as_of = rest.split(marker, 1)
    return {
        "code": code.strip(),
        "name": name.strip() or code.strip(),
        "data_as_of": data_as_of.strip(),
        "label": text,
    }


def _item(
    *,
    key: str,
    title: str,
    detail: str,
    priority: int,
    severity: str,
    action_type: str,
    action_label: str,
    command: str,
    source: str,
    metric: str,
    focus_codes: list[str] | None = None,
    action_payload: dict[str, Any] | None = None,
    status: str = "todo",
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "priority": priority,
        "severity": severity,
        "status": status,
        "action_type": action_type,
        "action_label": action_label,
        "command": command,
        "source": source,
        "metric": metric,
        "focus_codes": focus_codes or [],
        "action_payload": _normalize_action_payload(action_payload),
    }


def _update_workflow_item() -> dict[str, Any] | None:
    workflow = get_update_workflow_status()
    if str(workflow.get("overall_status") or "") == "ready":
        return None

    action = workflow.get("next_action") or {}
    command = str(action.get("command") or "")
    severity = "danger" if workflow.get("overall_status") == "blocked" else "warning"
    current_step = str(workflow.get("current_step") or "")
    return _item(
        key="update_workflow",
        title=str(action.get("title") or "先處理每日更新流程"),
        detail=str(action.get("detail") or workflow.get("headline") or "先確認資料與交易輸出是否同步。"),
        priority=120,
        severity=severity,
        action_type="update_workflow",
        action_label="複製指令" if command else "查看流程",
        command=command,
        source="update_workflow",
        metric=str(workflow.get("headline") or current_step),
        action_payload={
            "kind": "command" if command else "workflow",
            "command": command,
            "copy_command": str(action.get("copy_command") or command),
            "current_step": current_step,
            "expected_outputs": list(action.get("expected_outputs") or []),
        },
    )


def _data_repair_item() -> dict[str, Any] | None:
    missing = [
        item
        for item in get_universe()
        if str(item.get("data_status") or "") in {"no_data", "insufficient"}
    ]
    if not missing:
        return None
    missing.sort(key=lambda item: (0 if item.get("data_status") == "no_data" else 1, str(item.get("code") or "")))
    no_data_count = sum(1 for item in missing if item.get("data_status") == "no_data")
    insufficient_count = len(missing) - no_data_count
    return _item(
        key="data_repair",
        title="先修復追蹤股日線資料",
        detail=f"有 {len(missing)} 檔追蹤股缺日線或資料不足（無日線 {no_data_count} / 不足 {insufficient_count}）。",
        priority=100,
        severity="danger",
        action_type="data_repair",
        action_label="複製修復指令",
        command=_DATA_REPAIR_COMMAND,
        source="universe",
        metric=f"{len(missing)} 檔需修復",
        focus_codes=[str(item.get("code") or "") for item in missing[:5] if item.get("code")],
        action_payload={
            "kind": "command",
            "command": _DATA_REPAIR_COMMAND,
            "copy_command": f"cd {_BACKEND}\n{_DATA_REPAIR_COMMAND}",
            "expected_outputs": DAILY_UPDATE_OUTPUTS,
        },
    )


def _fundamentals_item() -> dict[str, Any] | None:
    workflow = (get_fundamentals_status().get("workflow_summary") or {})
    stage = str(workflow.get("stage") or "")
    if stage in {"", "complete"}:
        return None

    action = workflow.get("primary_action") or {}
    focus_targets = workflow.get("focus_targets") or []
    severity = "danger" if stage == "fix_priority_csv" else "warning"
    action_kind = str(action.get("kind") or "")
    action_payload: dict[str, Any] = {
        "kind": "copy_text",
        "copy_text": str(workflow.get("fill_targets_copy_text") or ""),
        "file_path": str(action.get("command") or ""),
        "focus_limit": min(5, len(focus_targets)),
        "write_template_command": FUNDAMENTALS_PRIORITY_TEMPLATE_COMMAND,
        "prepare_import_command": FUNDAMENTALS_PRIORITY_IMPORT_COMMAND,
        "prepare_import_apply_command": FUNDAMENTALS_PRIORITY_IMPORT_APPLY_COMMAND,
        "expected_outputs": list(FUNDAMENTALS_PRIORITY_IMPORT_OUTPUTS),
    }
    if action_kind == "api":
        action_payload = {
            "kind": "api",
            "method": "POST",
            "endpoint": "/api/system/fundamentals-priority-fill/merge",
            "dry_run": True,
            "confirm_message": "先預覽基本面避雷補資料合併結果，不會正式改寫 fundamentals.json。",
        }
    return _item(
        key="fundamentals",
        title=str(workflow.get("headline") or "補基本面避雷資料"),
        detail=str(workflow.get("detail") or "補齊必要欄位後，基本面避雷分數才可評分。"),
        priority=70,
        severity=severity,
        action_type="fundamentals",
        action_label="複製補資料清單" if action_payload.get("kind") == "copy_text" else str(action.get("label") or "看缺欄位"),
        command=str(action.get("command") or ""),
        source="fundamentals",
        metric=str(workflow.get("coverage_label") or ""),
        focus_codes=[str(item.get("code") or "") for item in focus_targets[:5] if item.get("code")],
        action_payload=action_payload,
    )


def _official_coverage_item(daily_check: dict[str, Any]) -> dict[str, Any] | None:
    if daily_check and not daily_check.get("snapshot_is_stale"):
        return None

    action_payload = {
        "kind": "api",
        "method": "GET",
        "endpoint": "/api/system/fundamentals-official/coverage-audit",
        "confirm_message": "只讀取官方基本面覆蓋率稽核，不會產生報告或寫入正式基本面資料。",
    }
    try:
        audit = get_official_fundamentals_coverage_audit()
    except FileNotFoundError as exc:
        return _item(
            key="official_fundamentals_coverage",
            title="官方基本面覆蓋率稽核尚未可讀",
            detail=f"{exc}。先產生或補齊 backend/out/fundamentals_priority_fill.csv，再重新檢查。",
            priority=55,
            severity="warning",
            action_type="fundamentals",
            action_label="查看覆蓋率狀態",
            command="GET /api/system/fundamentals-official/coverage-audit",
            source="official_fundamentals",
            metric="等待 priority CSV",
            action_payload=action_payload,
        )

    missing_reports = list(audit.get("missing_report_files") or [])
    try:
        coverage_pct = float(audit.get("coverage_pct") or 0)
    except (TypeError, ValueError):
        coverage_pct = 0.0
    if not missing_reports and coverage_pct >= 80:
        return None

    missing_label = "、".join(str(item) for item in missing_reports[:3])
    if len(missing_reports) > 3:
        missing_label = f"{missing_label} 等 {len(missing_reports)} 份"
    detail = f"官方 report-only 覆蓋率 {coverage_pct:.1f}%。"
    if missing_label:
        detail = f"{detail} 缺少 {missing_label}。"
    next_action = str(audit.get("next_action_label") or "查看缺少的 official report-only CSV 或缺列。")
    return _item(
        key="official_fundamentals_coverage",
        title="官方基本面覆蓋率待確認",
        detail=f"{detail} {next_action}",
        priority=55,
        severity="warning",
        action_type="fundamentals",
        action_label="查看覆蓋率狀態",
        command="GET /api/system/fundamentals-official/coverage-audit",
        source="official_fundamentals",
        metric=f"{coverage_pct:.1f}% 覆蓋",
        action_payload=action_payload,
    )


def _universe_review_item() -> dict[str, Any] | None:
    workflow = build_universe_report_review_workflow_summary(limit=10)
    if str(workflow.get("stage") or "") != "review_candidates":
        return None
    action = workflow.get("primary_action") or {}
    top_items = workflow.get("top_items") or []
    missing_count = int(workflow.get("missing_count") or 0)
    batch_limit = min(10, max(1, missing_count or 10))
    return _item(
        key="universe_report_review",
        title=str(workflow.get("headline") or "補候選股復盤紀錄"),
        detail=str(workflow.get("detail") or "把可行動候選寫入 decision_journal，方便 Daily Check 收斂。"),
        priority=60,
        severity="warning",
        action_type="decision_journal",
        action_label=str(action.get("label") or "補候選復盤"),
        command=str(action.get("command") or "POST /api/decision-journal/from-universe-report"),
        source="decision_journal",
        metric=str(workflow.get("progress_label") or ""),
        focus_codes=[str(item.get("code") or "") for item in top_items[:5] if item.get("code")],
        action_payload={
            "kind": "api",
            "method": "POST",
            "endpoint": "/api/decision-journal/from-universe-report",
            "date": workflow.get("as_of"),
            "limit": batch_limit,
            "confirm_message": (
                f"將從候選股報表批次建立前 {batch_limit} 筆復盤紀錄。"
                "這只會寫入決策日誌，不會修改交易紀錄、持倉或現金。是否繼續？"
            ),
        },
    )


def _daily_check_items(existing_keys: set[str]) -> list[dict[str, Any]]:
    report = get_daily_check_report() or {}
    mapped: list[dict[str, Any]] = []
    duplicate_map = {
        "data_repair": "data_repair",
        "decision_journal": "universe_report_review",
    }
    for action in report.get("top_actions") or []:
        key = str(action.get("key") or "")
        if duplicate_map.get(key, key) in existing_keys:
            continue
        payload = action.get("action_payload") if isinstance(action.get("action_payload"), dict) else None
        if key == "data_freshness":
            details = action.get("details") if isinstance(action.get("details"), dict) else {}
            stale_count = int(details.get("stale_count") or 0)
            missing_count = int(details.get("missing_date_count") or 0)
            total_issue_count = stale_count + missing_count
            if total_issue_count <= 0:
                total_issue_count = len((payload or {}).get("preview_items") or [])
            mapped.append(_item(
                key="data_freshness",
                title=str(action.get("title") or "追蹤股票資料日落後"),
                detail=str(action.get("message") or ""),
                priority=90,
                severity="warning",
                action_type="data_freshness",
                action_label="複製更新指令",
                command=str(action.get("next_action") or (payload or {}).get("command") or ""),
                source="daily_check",
                metric=f"{total_issue_count} 檔資料日落後" if total_issue_count else str(action.get("status") or "warn"),
                focus_codes=_focus_codes_from_preview_items(payload),
                action_payload=payload,
            ))
            continue
        mapped.append(_item(
            key=f"daily_check_{key or len(mapped) + 1}",
            title=str(action.get("title") or "Daily Check 待辦"),
            detail=str(action.get("message") or ""),
            priority=95 if action.get("status") == "block" else 40,
            severity="danger" if action.get("status") == "block" else "warning",
            action_type=str(action.get("action_type") or "daily_check"),
            action_label="查看 Daily Check",
            command=str(action.get("next_action") or ""),
            source="daily_check",
            metric=str(action.get("status") or "warn"),
            action_payload=payload,
        ))
    return mapped


def _focus_item(
    *,
    category: str,
    code: str,
    name: str,
    label: str,
    reason: str,
    next_action: str,
    severity: str,
    source: str,
    as_of: str | None,
    action_label: str = "查看詳情",
    primary_metric: str = "",
    short_reason: str | None = None,
    detail_reason: str | None = None,
) -> dict[str, Any]:
    full_reason = str(detail_reason or reason)
    return {
        "category": category,
        "code": code,
        "name": name,
        "label": label,
        "reason": reason,
        "short_reason": short_reason or _short_display_reason(reason),
        "detail_reason": full_reason,
        "next_action": next_action,
        "action_label": action_label,
        "primary_metric": primary_metric,
        "severity": severity,
        "source": source,
        "price_basis": _PRICE_BASIS_LABEL,
        "as_of": as_of,
    }


def _as_of_for_focus(workflow: dict[str, Any], daily_check: dict[str, Any], review_workflow: dict[str, Any]) -> str | None:
    return (
        workflow.get("data_as_of")
        or daily_check.get("data_as_of")
        or review_workflow.get("as_of")
    )


def _portfolio_focus_items(workflow: dict[str, Any], as_of: str | None) -> list[dict[str, Any]]:
    tasks = list(workflow.get("portfolio_tasks") or [])
    tasks.sort(key=lambda item: (int(item.get("priority") or 0), str(item.get("severity") or "")), reverse=True)
    focus: list[dict[str, Any]] = []
    for task in tasks[:3]:
        code = str(task.get("code") or "")
        focus.append(_focus_item(
            category="portfolio_risk",
            code=code,
            name=str(task.get("name") or code or "持股風險"),
            label=str(task.get("label") or "持股風險"),
            reason=str(task.get("reason") or "持股需要確認停利、停損或續抱條件。"),
            next_action=f"查看 {code} 技術分析與持股決策" if code else "回到持股風險區確認處理方式",
            severity=str(task.get("severity") or "warning"),
            source="portfolio",
            as_of=as_of,
            action_label="查看持股",
            primary_metric=str(task.get("key_price") or ""),
        ))
    return focus


def _entry_focus_items(can_use_trade_outputs: bool, as_of: str | None) -> list[dict[str, Any]]:
    if not can_use_trade_outputs:
        return []
    candidates: list[dict[str, Any]] = []
    for row in get_universe_report_json() or []:
        action = str(row.get("daily_action") or "")
        try:
            holding_shares = int(float(row.get("holding_shares") or 0))
        except (TypeError, ValueError):
            holding_shares = 0
        if holding_shares > 0 or action not in {"enter", "wait_pullback"}:
            continue
        candidates.append(row)

    action_rank = {"enter": 2, "wait_pullback": 1}
    candidates.sort(
        key=lambda row: (
            action_rank.get(str(row.get("daily_action") or ""), 0),
            int(float(row.get("daily_priority") or 0)),
        ),
        reverse=True,
    )

    focus: list[dict[str, Any]] = []
    for row in candidates[:3]:
        code = str(row.get("code") or "")
        action = str(row.get("daily_action") or "")
        label = str(row.get("daily_action_label") or ("可小試" if action == "enter" else "等回測"))
        focus.append(_focus_item(
            category="entry_candidate",
            code=code,
            name=str(row.get("name") or code or "候選股"),
            label=label,
            reason=str(row.get("daily_action_reason") or row.get("no_buy_reason") or "候選股符合今日觀察條件。"),
            next_action=f"查看 {code} 技術分析，確認進場區間、停損與 R/R" if code else "查看候選股篩選報告",
            severity="warning" if action == "wait_pullback" else "info",
            source="universe_report",
            as_of=as_of,
            action_label="查看進場計畫",
            primary_metric=_entry_primary_metric(row),
        ))
    return focus


def _review_focus_items(
    *,
    items: list[dict[str, Any]],
    primary_action: dict[str, Any] | None,
    review_workflow: dict[str, Any],
    can_use_trade_outputs: bool,
    as_of: str | None,
) -> list[dict[str, Any]]:
    focus: list[dict[str, Any]] = []
    if not can_use_trade_outputs:
        focus.append(_focus_item(
            category="review_needed",
            code="",
            name="交易輸出暫停使用",
            label="先解除交易輸出阻塞",
            reason="資料或交易輸出尚未通過檢查，不要用候選股做進場判斷。",
            next_action=str((primary_action or {}).get("command") or "先處理 Primary Action，再重新檢查 Dashboard。"),
            severity="danger",
            source="workflow",
            as_of=as_of,
            action_label="先解除阻塞",
        ))
        return focus

    top_items = review_workflow.get("top_items") or []
    for item in top_items[:3]:
        code = str(item.get("code") or "")
        focus.append(_focus_item(
            category="review_needed",
            code=code,
            name=str(item.get("name") or code or "待復盤候選"),
            label=str(item.get("daily_action_label") or "待復盤"),
            reason=str(item.get("daily_action_reason") or review_workflow.get("detail") or "候選股需要補決策日誌。"),
            next_action="補決策日誌，不會修改交易紀錄、持倉或現金。",
            severity="warning",
            source="pm_worklist",
            as_of=as_of,
            action_label="補復盤",
        ))

    if len(focus) >= 3:
        return focus[:3]

    if primary_action and primary_action.get("action_type") == "data_freshness":
        for label in (primary_action.get("action_payload") or {}).get("preview_items") or []:
            if len(focus) >= 3:
                return focus
            parsed = _parse_data_freshness_preview(str(label))
            code = parsed["code"]
            focus.append(_focus_item(
                category="review_needed",
                code=code,
                name=parsed["name"],
                label="資料日落後",
                reason=str(primary_action.get("detail") or "追蹤股票資料日落後，先更新日線資料再做盤後判斷。"),
                next_action=f"先更新日線資料：{primary_action.get('command') or 'python3 scripts/daily_update.py --months 1'}",
                severity=str(primary_action.get("severity") or "warning"),
                source=str(primary_action.get("source") or "daily_check"),
                as_of=as_of,
                action_label=str(primary_action.get("action_label") or "複製更新指令"),
                primary_metric=parsed["data_as_of"],
                short_reason="先更新日線資料",
                detail_reason=parsed["label"],
            ))

    for item in items:
        if primary_action and item.get("key") == primary_action.get("key"):
            continue
        for code in item.get("focus_codes") or []:
            if len(focus) >= 3:
                return focus
            focus.append(_focus_item(
                category="review_needed",
                code=str(code),
                name=str(code),
                label=str(item.get("title") or "待處理"),
                reason=str(item.get("detail") or "PM Worklist 待辦需要補處理。"),
                next_action=str(item.get("action_label") or item.get("command") or "查看 PM Worklist 明細"),
                severity=str(item.get("severity") or "warning"),
                source=str(item.get("source") or "pm_worklist"),
                as_of=as_of,
                action_label=str(item.get("action_label") or "查看待辦"),
                primary_metric=str(item.get("metric") or ""),
            ))
    return focus


def _build_today_focus(
    *,
    items: list[dict[str, Any]],
    primary_action: dict[str, Any] | None,
    update_workflow: dict[str, Any],
    review_workflow: dict[str, Any],
    daily_check: dict[str, Any],
) -> list[dict[str, Any]]:
    try:
        workflow = get_workflow_status()
    except Exception:
        workflow = {}
    as_of = _as_of_for_focus(workflow, daily_check, review_workflow)
    can_use_trade_outputs = bool(
        update_workflow.get("can_use_trade_outputs", True)
        and workflow.get("can_trade_today", True)
    )

    focus = []
    focus.extend(_portfolio_focus_items(workflow, as_of)[:3])
    focus.extend(_entry_focus_items(can_use_trade_outputs, as_of)[:3])
    focus.extend(_review_focus_items(
        items=items,
        primary_action=primary_action,
        review_workflow=review_workflow,
        can_use_trade_outputs=can_use_trade_outputs,
        as_of=as_of,
    )[:3])

    if not focus:
        focus.append(_focus_item(
            category="review_needed",
            code="",
            name="今日焦點已收斂",
            label="暫無持股風險或候選股",
            reason="目前沒有持股風險、可小試候選或待復盤項目。",
            next_action="維持觀察，若盤後資料更新再重新檢查 Dashboard。",
            severity="info",
            source="pm_worklist",
            as_of=as_of,
            action_label="維持觀察",
        ))
    return focus


def get_pm_worklist() -> dict[str, Any]:
    update_workflow = get_update_workflow_status()
    review_workflow = build_universe_report_review_workflow_summary(limit=10)
    daily_check = get_daily_check_report() or {}
    items = [
        item for item in [
            _update_workflow_item(),
            _data_repair_item(),
            _fundamentals_item(),
            _official_coverage_item(daily_check),
            _universe_review_item(),
        ] if item
    ]
    existing_keys = {str(item["key"]) for item in items}
    items.extend(_daily_check_items(existing_keys))
    severity_rank = {"danger": 2, "warning": 1, "info": 0}
    items.sort(key=lambda item: (int(item.get("priority") or 0), severity_rank.get(str(item.get("severity") or ""), 0)), reverse=True)
    primary_action = items[0] if items else None

    if items:
        status = "action_required"
        headline = f"今日 PM 工作佇列：{len(items)} 件待處理"
    else:
        status = "clear"
        headline = "今日 PM 工作佇列已清空"

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_status": status,
        "headline": headline,
        "primary_action": primary_action,
        "today_focus": _build_today_focus(
            items=items,
            primary_action=primary_action,
            update_workflow=update_workflow,
            review_workflow=review_workflow,
            daily_check=daily_check,
        ),
        "items": items[:8],
    }
