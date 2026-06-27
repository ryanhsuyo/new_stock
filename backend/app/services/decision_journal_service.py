from datetime import datetime
from pathlib import Path
import sys
from uuid import uuid4

from app.models.decision_journal import (
    DecisionJournalBulkCreateResult,
    DecisionJournalCreate,
    DecisionJournalEntry,
    DecisionJournalSummary,
)
from app.services.signals_service import get_universe_report_json
from app.services.workflow_service import get_workflow_status
from app.storage.decision_journal_store import load_decision_journal, save_decision_journal

ALLOWED_DECISIONS = {"buy", "sell", "hold", "skip", "reduce", "watch"}
_BACKEND = Path(__file__).resolve().parent.parent.parent
_OUT = _BACKEND / "out"
_SCRIPTS = _BACKEND / "scripts"
_ACTIONABLE_REPORT_ACTIONS = {"enter", "wait_pullback", "reduce", "exit"}
_REPORT_ACTION_URGENCY = {"exit": 0, "reduce": 1, "enter": 2, "wait_pullback": 3}


def _clean_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} 不可空白")
    return cleaned


def _workflow_snapshot() -> tuple[str | None, str | None]:
    workflow = get_workflow_status()
    return workflow.get("overall_status"), workflow.get("headline")


def _decision_from_workflow_action(action: str | None) -> str:
    if action == "exit":
        return "sell"
    if action == "reduce":
        return "reduce"
    if action == "enter":
        return "buy"
    if action == "avoid":
        return "skip"
    if action == "hold":
        return "hold"
    return "watch"


def _positive_int(value: object) -> int:
    try:
        parsed = int(float(str(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _decision_from_report_action(action: str | None, holding_shares: object = None) -> str:
    has_holding = _positive_int(holding_shares) > 0
    if action == "exit":
        return "sell" if has_holding else "skip"
    if action == "reduce":
        return "reduce" if has_holding else "skip"
    if action == "enter":
        return "buy"
    return "watch"


def _write_daily_check_report() -> None:
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))

    from app.services.signal_alert_service import load_signal_alerts
    from app.services.today_scan_service import load_today_scan_report
    from daily_check import build_daily_summary, write_daily_summary
    from doctor import build_doctor_report

    report = build_doctor_report(_BACKEND)
    summary = build_daily_summary(
        report,
        limit=3,
        signal_alerts=load_signal_alerts(_BACKEND / "out"),
        today_scan=load_today_scan_report(_BACKEND / "out"),
    )
    write_daily_summary(summary, _BACKEND)


def _refresh_daily_check_safely() -> None:
    try:
        _write_daily_check_report()
    except Exception:
        # 決策紀錄是主資料，Daily Check 只是 Dashboard 快照；快照失敗不能中斷紀錄。
        pass


def _validate_payload(payload: DecisionJournalCreate) -> dict:
    decision = payload.decision.strip().lower()
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"decision 必須是 {', '.join(sorted(ALLOWED_DECISIONS))} 其中之一")
    if payload.price is not None and payload.price <= 0:
        raise ValueError("price 必須大於 0")
    if payload.shares is not None and payload.shares <= 0:
        raise ValueError("shares 必須大於 0")

    return {
        "date": _clean_text(payload.date, "date"),
        "code": _clean_text(payload.code, "code"),
        "name": _clean_text(payload.name, "name"),
        "decision": decision,
        "reason": _clean_text(payload.reason, "reason"),
        "price": payload.price,
        "shares": payload.shares,
        "key_price": payload.key_price.strip() if payload.key_price else None,
        "invalidation": payload.invalidation.strip() if payload.invalidation else None,
        "source": payload.source.strip() if payload.source else "manual",
    }


def list_decision_journal(
    limit: int = 100,
    code: str | None = None,
    date: str | None = None,
    decision: str | None = None,
) -> list[DecisionJournalEntry]:
    entries = load_decision_journal()
    if code:
        wanted = code.strip()
        entries = [entry for entry in entries if entry.code == wanted]
    if date:
        wanted_date = date.strip()
        entries = [entry for entry in entries if entry.date == wanted_date]
    if decision:
        wanted_decision = decision.strip().lower()
        if wanted_decision not in ALLOWED_DECISIONS:
            raise ValueError(f"decision 必須是 {', '.join(sorted(ALLOWED_DECISIONS))} 其中之一")
        entries = [entry for entry in entries if entry.decision == wanted_decision]
    indexed_entries = list(enumerate(entries))
    indexed_entries.sort(key=lambda item: (item[1].date, item[1].created_at, item[0]), reverse=True)
    sorted_entries = [entry for _, entry in indexed_entries]
    return sorted_entries[: max(1, min(limit, 500))]


def get_decision_journal_summary(date: str | None = None) -> DecisionJournalSummary:
    entries = load_decision_journal()
    target_date = date.strip() if date else None
    if target_date is None and entries:
        target_date = max(entry.date for entry in entries)

    scoped = [entry for entry in entries if target_date is None or entry.date == target_date]
    scoped = list(reversed(scoped))
    by_decision: dict[str, int] = {}
    for entry in scoped:
        by_decision[entry.decision] = by_decision.get(entry.decision, 0) + 1

    return DecisionJournalSummary(
        date=target_date,
        total_count=len(scoped),
        by_decision=dict(sorted(by_decision.items())),
        recent_codes=[entry.code for entry in scoped[:8]],
    )


def create_decision_journal_entry(payload: DecisionJournalCreate) -> DecisionJournalEntry:
    values = _validate_payload(payload)
    workflow_status, workflow_headline = _workflow_snapshot()
    entry = DecisionJournalEntry(
        id=uuid4().hex,
        created_at=datetime.now().isoformat(timespec="microseconds"),
        updated_at=None,
        workflow_status=workflow_status,
        workflow_headline=workflow_headline,
        **values,
    )

    entries = load_decision_journal()
    entries.append(entry)
    save_decision_journal(entries)
    _refresh_daily_check_safely()
    return entry


def create_missing_portfolio_task_entries(date: str | None = None) -> DecisionJournalBulkCreateResult:
    workflow = get_workflow_status()
    target_date = (date or workflow.get("data_as_of") or "").strip()
    if not target_date:
        raise ValueError("date 不可空白，且 workflow data_as_of 不存在")

    portfolio_tasks = workflow.get("portfolio_tasks") or []
    entries = load_decision_journal()
    existing_codes = {entry.code for entry in entries if entry.date == target_date}

    workflow_status = workflow.get("overall_status")
    workflow_headline = workflow.get("headline")
    created: list[DecisionJournalEntry] = []
    skipped_codes: list[str] = []

    for task in portfolio_tasks:
        code = str(task.get("code") or "").strip()
        name = str(task.get("name") or code).strip()
        if not code or code in existing_codes:
            if code:
                skipped_codes.append(code)
            continue

        reason = str(task.get("reason") or task.get("label") or "依持股作戰規則記錄").strip()
        key_price = task.get("key_price")
        invalidation = task.get("invalidation")
        holding_shares = task.get("holding_shares")
        try:
            shares = int(holding_shares) if holding_shares not in (None, "") else None
        except (TypeError, ValueError):
            shares = None

        entry = DecisionJournalEntry(
            id=uuid4().hex,
            created_at=datetime.now().isoformat(timespec="microseconds"),
            updated_at=None,
            date=target_date,
            code=code,
            name=name,
            decision=_decision_from_workflow_action(str(task.get("action") or "")),
            reason=reason,
            price=None,
            shares=shares,
            key_price=str(key_price).strip() if key_price else None,
            invalidation=str(invalidation).strip() if invalidation else None,
            source="workflow_bulk",
            workflow_status=workflow_status,
            workflow_headline=workflow_headline,
        )
        entries.append(entry)
        created.append(entry)
        existing_codes.add(code)

    if created:
        save_decision_journal(entries)
        _refresh_daily_check_safely()

    return DecisionJournalBulkCreateResult(
        date=target_date,
        total_task_count=len(portfolio_tasks),
        created_count=len(created),
        skipped_count=len(skipped_codes),
        skipped_codes=skipped_codes,
        created_entries=created,
    )


def create_missing_universe_report_entries(
    date: str | None = None,
    limit: int = 10,
) -> DecisionJournalBulkCreateResult:
    draft = build_universe_report_review_draft(as_of=date, limit=limit)
    target_date = str(draft.get("as_of") or date or "").strip()
    if not target_date:
        raise ValueError("date 不可空白，且 universe_report data_as_of 不存在")

    workflow_status, workflow_headline = _workflow_snapshot()
    entries = load_decision_journal()
    existing_codes = {
        entry.code
        for entry in entries
        if entry.date == target_date and entry.source == "universe_report"
    }
    created: list[DecisionJournalEntry] = []
    skipped_codes: list[str] = []

    for item in draft.get("items") or []:
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or code).strip()
        if not code or code in existing_codes:
            if code:
                skipped_codes.append(code)
            continue

        entry = DecisionJournalEntry(
            id=uuid4().hex,
            created_at=datetime.now().isoformat(timespec="microseconds"),
            updated_at=None,
            date=target_date,
            code=code,
            name=name,
            decision=str(item.get("decision_suggestion") or "watch"),
            reason=str(item.get("reason") or "依候選股報表補復盤理由"),
            price=None,
            shares=None,
            key_price=str(item.get("key_price")).strip() if item.get("key_price") else None,
            invalidation=str(item.get("invalidation")).strip() if item.get("invalidation") else None,
            source="universe_report",
            workflow_status=workflow_status,
            workflow_headline=workflow_headline,
        )
        entries.append(entry)
        created.append(entry)
        existing_codes.add(code)

    if created:
        save_decision_journal(entries)
        _refresh_daily_check_safely()

    return DecisionJournalBulkCreateResult(
        date=target_date,
        total_task_count=int(draft.get("missing_count") or len(draft.get("items") or [])),
        created_count=len(created),
        skipped_count=len(skipped_codes),
        skipped_codes=skipped_codes,
        created_entries=created,
    )


def build_universe_report_review_draft(
    as_of: str | None = None,
    limit: int | None = None,
) -> dict:
    rows = get_universe_report_json() or []
    target_date = (as_of or "").strip()
    if not target_date:
        target_date = str((rows[0] or {}).get("data_as_of") or "") if rows else ""

    entries = load_decision_journal()
    recorded_codes = {
        entry.code
        for entry in entries
        if entry.date == target_date and entry.source == "universe_report" and entry.code
    }

    actionable_rows = [
        row
        for row in rows
        if row.get("code")
        and str(row.get("daily_action") or "") in _ACTIONABLE_REPORT_ACTIONS
        and (not target_date or str(row.get("data_as_of") or target_date) == target_date)
    ]
    actionable_codes = {str(row.get("code") or "") for row in actionable_rows}
    missing_codes = actionable_codes - recorded_codes

    items: list[dict] = []
    for row in actionable_rows:
        code = str(row.get("code") or "")
        if code not in missing_codes:
            continue
        action = str(row.get("daily_action") or "")
        try:
            priority = int(row.get("daily_priority") or 50)
        except (TypeError, ValueError):
            priority = 50
        items.append({
            "code": code,
            "name": str(row.get("name") or code),
            "action": action,
            "label": str(row.get("daily_action_label") or action),
            "decision_suggestion": _decision_from_report_action(action, row.get("holding_shares")),
            "reason": str(row.get("daily_action_reason") or row.get("no_buy_reason") or "依候選股報表補復盤理由"),
            "key_price": row.get("daily_key_price"),
            "invalidation": row.get("daily_invalidation"),
            "priority": priority,
            "_urgency": _REPORT_ACTION_URGENCY.get(action, 99),
        })
    items.sort(key=lambda item: (item["_urgency"], -item["priority"], item["code"]))
    for item in items:
        item.pop("_urgency", None)
    if limit is not None:
        items = items[: max(0, limit)]

    return {
        "as_of": target_date,
        "actionable_count": len(actionable_codes),
        "recorded_count": len(actionable_codes & recorded_codes),
        "missing_count": len(missing_codes),
        "items": items,
    }


def _review_workflow_step(key: str, label: str, detail: str, status: str) -> dict:
    return {
        "key": key,
        "label": label,
        "detail": detail,
        "status": status,
    }


def build_universe_report_review_workflow_summary(
    as_of: str | None = None,
    limit: int | None = 10,
) -> dict:
    draft = build_universe_report_review_draft(as_of=as_of, limit=limit)
    actionable_count = int(draft.get("actionable_count") or 0)
    recorded_count = int(draft.get("recorded_count") or 0)
    missing_count = int(draft.get("missing_count") or 0)
    items = draft.get("items") or []
    batch_count = min(len(items), 10)

    if actionable_count == 0:
        stage = "no_actionable_candidates"
        headline = "今天沒有候選股復盤待辦"
        detail = "universe_report 目前沒有 enter / wait_pullback / reduce / exit 類可行動項目。"
        primary_action = {
            "label": "查看候選報告",
            "command": "GET /api/stocks/signals/universe-report/json",
            "kind": "link",
        }
        checklist_status = ("done", "done", "done")
    elif missing_count == 0:
        stage = "complete"
        headline = "候選股復盤已完成"
        detail = f"{draft.get('as_of') or '最新資料日'} 的 {actionable_count} 檔可行動候選都已記錄。"
        primary_action = {
            "label": "查看紀錄",
            "command": "GET /api/decision-journal",
            "kind": "link",
        }
        checklist_status = ("done", "done", "done")
    else:
        stage = "review_candidates"
        headline = "補候選股復盤紀錄"
        detail = (
            f"{draft.get('as_of') or '最新資料日'} 有 {missing_count} 檔尚未復盤；"
            "這只寫入 decision_journal，不會改交易紀錄、持倉或現金。"
        )
        primary_action = {
            "label": f"批次記錄前 {batch_count} 檔",
            "command": "POST /api/decision-journal/from-universe-report",
            "kind": "api",
        }
        checklist_status = ("done", "todo", "blocked")

    return {
        "stage": stage,
        "headline": headline,
        "detail": detail,
        "as_of": draft.get("as_of"),
        "progress_label": f"{recorded_count}/{actionable_count} 已復盤",
        "actionable_count": actionable_count,
        "recorded_count": recorded_count,
        "missing_count": missing_count,
        "primary_action": primary_action,
        "checklist": [
            _review_workflow_step(
                "load_universe_report",
                "讀取候選報告",
                "使用 universe_report.csv 的 daily_action 判斷可行動候選。",
                checklist_status[0],
            ),
            _review_workflow_step(
                "record_missing_decisions",
                "補復盤紀錄",
                "將未記錄候選寫入 decision_journal；未持有的 exit / reduce 會記為 skip。",
                checklist_status[1],
            ),
            _review_workflow_step(
                "refresh_daily_check",
                "刷新 PM 待辦",
                "新增或批次新增後刷新 daily_check.json，Dashboard 待辦會同步下降。",
                checklist_status[2],
            ),
        ],
        "top_items": items[:5],
    }


def render_universe_report_review_markdown(draft: dict) -> str:
    as_of = draft.get("as_of") or "unknown"
    lines = [
        f"# 候選股復盤待辦 - {as_of}",
        "",
        f"- 可行動檔數：{draft.get('actionable_count', 0)}",
        f"- 已記錄：{draft.get('recorded_count', 0)}",
        f"- 待補：{draft.get('missing_count', 0)}",
        "",
    ]
    items = draft.get("items") or []
    if not items:
        lines.extend(["目前沒有待補復盤項目。", ""])
        return "\n".join(lines)

    for idx, item in enumerate(items, start=1):
        lines.extend([
            f"## {idx}. {item.get('code')} {item.get('name')}",
            "",
            f"- 報表動作：{item.get('label')} ({item.get('action')})",
            f"- 建議 decision: {item.get('decision_suggestion')}",
            f"- 關鍵價：{item.get('key_price') or '-'}",
            f"- 失效條件：{item.get('invalidation') or '-'}",
            f"- 報表理由：{item.get('reason') or '-'}",
            "- 實際決策：",
            "- 最終理由：",
            "",
        ])
    return "\n".join(lines)


def write_universe_report_review_markdown(
    out_dir: Path | None = None,
    as_of: str | None = None,
    limit: int | None = None,
) -> Path:
    target_dir = out_dir or _OUT
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "universe_report_review_todo.md"
    draft = build_universe_report_review_draft(as_of=as_of, limit=limit)
    path.write_text(render_universe_report_review_markdown(draft), encoding="utf-8")
    return path


def delete_decision_journal_entry(entry_id: str) -> dict:
    wanted_id = entry_id.strip()
    if not wanted_id:
        raise ValueError("entry_id 不可空白")

    entries = load_decision_journal()
    remaining = [entry for entry in entries if entry.id != wanted_id]
    if len(remaining) == len(entries):
        raise FileNotFoundError(f"找不到決策日誌：{wanted_id}")

    save_decision_journal(remaining)
    _refresh_daily_check_safely()
    return {"deleted": wanted_id}


def update_decision_journal_entry(entry_id: str, payload: DecisionJournalCreate) -> DecisionJournalEntry:
    wanted_id = entry_id.strip()
    if not wanted_id:
        raise ValueError("entry_id 不可空白")

    values = _validate_payload(payload)
    entries = load_decision_journal()
    for idx, existing in enumerate(entries):
        if existing.id != wanted_id:
            continue

        updated = DecisionJournalEntry(
            id=existing.id,
            created_at=existing.created_at,
            updated_at=datetime.now().isoformat(timespec="seconds"),
            workflow_status=existing.workflow_status,
            workflow_headline=existing.workflow_headline,
            **values,
        )
        entries[idx] = updated
        save_decision_journal(entries)
        _refresh_daily_check_safely()
        return updated

    raise FileNotFoundError(f"找不到決策日誌：{wanted_id}")
