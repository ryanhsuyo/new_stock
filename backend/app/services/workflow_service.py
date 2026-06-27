"""
workflow_service.py — PM 視角的每日工作流健康檢查。

此 service 只彙整既有狀態，不重新計算訊號、不讀寫交易資料。
"""

from __future__ import annotations

from pathlib import Path

from app.services.fundamental_service import get_fundamentals_status
from app.services.signals_service import get_signals_status, get_universe_report_json
from app.services.update_service import get_data_status
from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS, SIGNAL_OUTPUTS, expected_outputs_for_command
from app.storage.decision_journal_store import load_decision_journal

_BACKEND = Path(__file__).resolve().parents[2]


def _copy_command(command: str | None) -> str | None:
    if not command:
        return None
    if command.startswith("python3 scripts/"):
        return f"cd {_BACKEND}\n{command}"
    return command


def _action(
    key: str,
    title: str,
    detail: str,
    priority: int,
    severity: str,
    action_type: str,
    command: str | None = None,
    success_check: str | None = None,
    expected_outputs: list[str] | None = None,
) -> dict:
    copy_command = _copy_command(command)
    outputs = expected_outputs or []
    action_payload: dict = {}
    if command:
        if command.startswith("POST "):
            _, endpoint = command.split(" ", 1)
            action_payload = {
                "kind": "api",
                "method": "POST",
                "endpoint": endpoint,
            }
        else:
            action_payload = {
                "kind": "command",
                "command": command,
                "copy_command": copy_command,
                "expected_outputs": outputs,
            }
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "priority": priority,
        "severity": severity,
        "action_type": action_type,
        "command": command,
        "copy_command": copy_command,
        "success_check": success_check,
        "expected_outputs": outputs,
        "action_payload": action_payload,
    }


def _expected_outputs_for_command(command: str | None) -> list[str]:
    return expected_outputs_for_command(command)


def _command_action_payload(command: str | None, expected_outputs: list[str] | None = None) -> dict:
    if not command:
        return {}
    outputs = expected_outputs if expected_outputs is not None else _expected_outputs_for_command(command)
    return {
        "kind": "command",
        "command": command,
        "copy_command": _copy_command(command),
        "expected_outputs": outputs,
    }


def _file_exists(status: dict, name: str) -> bool:
    return bool((status.get("out_files") or {}).get(name, {}).get("exists"))


def _file_parse_error(status: dict, name: str) -> str | None:
    value = (status.get("out_files") or {}).get(name, {}).get("parse_error")
    return str(value) if value else None


def _build_output_freshness(data_status: dict, signal_status: dict) -> dict:
    """確認交易輸出檔日期與資料日一致，避免用舊報表做今日判斷。"""
    expected = data_status.get("last_data_as_of")
    out_files = signal_status.get("out_files") or {}
    file_dates: dict[str, str | None] = {}
    for key in ("summary_json", "daily_brief_json", "universe_report_csv"):
        info = out_files.get(key) or {}
        file_dates[key] = info.get("as_of")

    mismatches = [
        {"file": key, "as_of": as_of, "expected": expected}
        for key, as_of in file_dates.items()
        if expected and as_of and as_of != expected
    ]
    missing_dates = [
        key
        for key, as_of in file_dates.items()
        if (out_files.get(key) or {}).get("exists") and not as_of
    ]

    if mismatches:
        labels = ", ".join(f"{item['file']}={item['as_of']}" for item in mismatches)
        return {
            "status": "blocked",
            "expected_as_of": expected,
            "file_dates": file_dates,
            "mismatches": mismatches,
            "missing_dates": missing_dates,
            "message": f"輸出檔日期與資料日不一致：{labels}；資料日應為 {expected}。",
        }
    if missing_dates:
        return {
            "status": "warning",
            "expected_as_of": expected,
            "file_dates": file_dates,
            "mismatches": [],
            "missing_dates": missing_dates,
            "message": f"部分輸出檔缺少 as_of 可稽核欄位：{', '.join(missing_dates)}。",
        }
    return {
        "status": "ready",
        "expected_as_of": expected,
        "file_dates": file_dates,
        "mismatches": [],
        "missing_dates": [],
        "message": f"輸出檔日期與資料日一致：{expected or '未知'}。",
    }


def _check_item(
    key: str,
    title: str,
    detail: str,
    status: str,
    action_type: str,
    priority: int,
) -> dict:
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "status": status,
        "action_type": action_type,
        "priority": priority,
    }


def _format_fundamentals_csv_issue(validation: dict) -> str:
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    first = errors[0] if errors else (warnings[0] if warnings else None)
    if not first:
        if validation.get("duplicate_codes"):
            return f"重複代碼：{', '.join(validation.get('duplicate_codes') or [])}"
        if validation.get("missing_code_rows"):
            return f"代碼空白列：{validation.get('missing_code_rows')}"
        return "priority CSV 有格式問題，請回 Dashboard 查看檢查提醒。"
    prefix = "錯誤" if errors else "警告"
    row = first.get("row_number")
    code = first.get("code") or "未填代碼"
    field = first.get("field") or "欄位"
    value = first.get("value")
    message = first.get("message") or "請確認格式"
    return f"{prefix}：第 {row} 列 {code} {field}={value!r}，{message}"


def _build_close_checklist(
    data_status: dict,
    signal_status: dict,
    reports_ready: bool,
) -> list[dict]:
    data_run_status = data_status.get("last_run_status")
    data_running = data_run_status == "running"
    signals_running = signal_status.get("run_status") == "running"
    summary_ready = _file_exists(signal_status, "summary_json") and not _file_parse_error(signal_status, "summary_json")
    daily_ready = (
        _file_exists(signal_status, "daily_brief_json")
        and not _file_parse_error(signal_status, "daily_brief_json")
        and not (signal_status.get("out_files") or {}).get("daily_brief_json", {}).get("update_required")
    )
    universe_ready = _file_exists(signal_status, "universe_report_csv") and not _file_parse_error(signal_status, "universe_report_csv")
    note_status = signal_status.get("manual_note_status") or {}

    data_needs_update = data_status.get("is_stale") or data_run_status in {"failed", "stalled"}
    data_step = "running" if data_running else ("todo" if data_needs_update else "done")
    note_step = "todo" if note_status.get("update_required") else "done"
    signal_step = "running" if signals_running else ("done" if reports_ready else "todo")
    daily_step = "done" if daily_ready else ("blocked" if not summary_ready or data_step in ("todo", "running") else "todo")
    universe_step = "done" if universe_ready else ("blocked" if not summary_ready or data_step in ("todo", "running") else "todo")
    portfolio_step = "done" if daily_ready and universe_ready else "blocked"

    return [
        _check_item(
            "update_data",
            "更新日線 / 籌碼 / 基本面模板",
            "確保 ohlcv、籌碼與 fundamentals 匯入流程是今天可用版本。",
            data_step,
            "update_data",
            100,
        ),
        _check_item(
            "market_note",
            "補盤後大盤筆記",
            "貼上今天大盤、櫃買、強弱族群與水位語氣。",
            note_step,
            "market_note",
            90,
        ),
        _check_item(
            "run_signals",
            "重算訊號與報表",
            "產生 summary、universe_report 與 daily_brief。",
            signal_step,
            "run_signals",
            80,
        ),
        _check_item(
            "daily_brief",
            "檢查每日作戰表",
            "確認水位、汰弱留強分類、明日任務與缺資料清單。",
            daily_step,
            "daily_brief",
            70,
        ),
        _check_item(
            "universe_report",
            "檢查候選股篩選報告",
            "確認可進場、等回測、風險處理與資料完整率。",
            universe_step,
            "universe_report",
            60,
        ),
        _check_item(
            "portfolio_risk",
            "檢查持股風險",
            "回到持倉頁確認持股是否跌破失效價或需要減碼。",
            portfolio_step,
            "portfolio",
            50,
        ),
    ]


def _portfolio_task_severity(action: str) -> str:
    if action in {"exit", "reduce"}:
        return "danger"
    if action in {"hold"}:
        return "success"
    if action in {"wait_pullback", "long_watch"}:
        return "info"
    return "warning"


def _build_portfolio_tasks(reports_ready: bool) -> list[dict]:
    if not reports_ready:
        return []

    rows = get_universe_report_json() or []
    tasks: list[dict] = []
    for row in rows:
        shares = row.get("holding_shares") or 0
        try:
            shares = int(shares)
        except (TypeError, ValueError):
            shares = 0
        if shares <= 0:
            continue

        action = str(row.get("daily_action") or "hold")
        priority = row.get("daily_priority")
        try:
            priority_int = int(priority) if priority is not None else 50
        except (TypeError, ValueError):
            priority_int = 50

        tasks.append({
            "code": str(row.get("code") or ""),
            "name": str(row.get("name") or row.get("code") or ""),
            "action": action,
            "label": str(row.get("daily_action_label") or action),
            "reason": str(row.get("daily_action_reason") or row.get("no_buy_reason") or "依持股作戰規則觀察"),
            "key_price": row.get("daily_key_price"),
            "invalidation": row.get("daily_invalidation"),
            "priority": priority_int,
            "severity": _portfolio_task_severity(action),
            "holding_shares": shares,
            "holding_position_pct": row.get("holding_position_pct"),
        })

    severity_rank = {"danger": 3, "warning": 2, "info": 1, "success": 0}
    tasks.sort(key=lambda item: (severity_rank.get(item["severity"], 0), item["priority"]), reverse=True)
    return tasks[:8]


def _build_workflow_metrics(
    actions: list[dict],
    close_checklist: list[dict],
    portfolio_tasks: list[dict],
    decision_journal_today_count: int = 0,
    portfolio_tasks_without_journal_count: int = 0,
    universe_actionable_count: int = 0,
    universe_actionable_without_journal_count: int = 0,
) -> dict:
    return {
        "blocker_count": sum(1 for item in actions if item.get("severity") == "danger"),
        "warning_count": sum(1 for item in actions if item.get("severity") == "warning"),
        "todo_step_count": sum(1 for item in close_checklist if item.get("status") == "todo"),
        "blocked_step_count": sum(1 for item in close_checklist if item.get("status") == "blocked"),
        "done_step_count": sum(1 for item in close_checklist if item.get("status") == "done"),
        "portfolio_task_count": len(portfolio_tasks),
        "portfolio_danger_count": sum(1 for item in portfolio_tasks if item.get("severity") == "danger"),
        "decision_journal_today_count": decision_journal_today_count,
        "portfolio_tasks_without_journal_count": portfolio_tasks_without_journal_count,
        "universe_actionable_count": universe_actionable_count,
        "universe_actionable_without_journal_count": universe_actionable_without_journal_count,
    }


def _build_decision_guardrails(
    data_status: dict,
    signal_status: dict,
    reports_ready: bool,
    output_freshness: dict | None = None,
) -> dict:
    def blocked_response(message: str, blocked_outputs: list[str], required_action: str) -> dict:
        expected_outputs = _expected_outputs_for_command(required_action)
        return {
            "can_use_trade_outputs": False,
            "message": message,
            "blocked_outputs": blocked_outputs,
            "required_action": required_action,
            "required_action_copy_command": _copy_command(required_action),
            "required_action_expected_outputs": expected_outputs,
            "action_payload": _command_action_payload(required_action, expected_outputs),
        }

    if data_status.get("is_stale"):
        data_as_of = data_status.get("last_data_as_of") or "未知"
        stale_days = data_status.get("stale_days")
        message = (
            f"資料最新日 {data_as_of}"
            f"{f'，已落後 {stale_days} 天' if stale_days is not None else ''}；"
            "候選股報告、每日作戰表與技術訊號只能回顧，不可作為今天進出場依據。"
        )
        return blocked_response(message, ["daily_brief", "universe_report", "technical_signals"], "python3 scripts/daily_update.py --months 1")

    if data_status.get("outputs_lag_raw_data"):
        return blocked_response(
            data_status.get("raw_data_warning") or "ohlcv.csv 比交易輸出新，需重新產生訊號與報表。",
            ["daily_brief", "universe_report", "technical_signals"],
            "python3 scripts/run_signals.py",
        )

    if not reports_ready:
        return blocked_response(
            "缺少 summary、universe_report 或 daily_brief，需先重算訊號與報表。",
            ["daily_brief", "universe_report", "technical_signals"],
            "python3 scripts/run_signals.py",
        )

    if output_freshness and output_freshness.get("status") == "blocked":
        return blocked_response(
            output_freshness.get("message") or "交易輸出檔日期與資料日不一致，需重新產生訊號。",
            ["daily_brief", "universe_report", "technical_signals"],
            "python3 scripts/run_signals.py",
        )

    daily_info = (signal_status.get("out_files") or {}).get("daily_brief_json", {})
    if daily_info.get("update_required"):
        return blocked_response(
            "每日作戰表標記為需更新，先重新跑每日更新流程再做交易判斷。",
            ["daily_brief"],
            "python3 scripts/daily_update.py --months 1",
        )

    return {
        "can_use_trade_outputs": True,
        "message": "資料流與交易輸出可供今天決策使用。",
        "blocked_outputs": [],
        "required_action": None,
        "required_action_copy_command": None,
        "required_action_expected_outputs": [],
        "action_payload": {},
    }


def _decision_journal_coverage(as_of: str | None, portfolio_tasks: list[dict]) -> dict:
    if not as_of or not portfolio_tasks:
        missing_codes = [task.get("code") for task in portfolio_tasks if task.get("code")]
        return {
            "as_of": as_of,
            "today_count": 0,
            "portfolio_tasks_without_journal_count": len(portfolio_tasks),
            "recorded_portfolio_codes": [],
            "missing_portfolio_codes": missing_codes,
            "parse_error": None,
        }

    try:
        entries = load_decision_journal()
    except Exception as exc:
        missing_codes = [task.get("code") for task in portfolio_tasks if task.get("code")]
        return {
            "as_of": as_of,
            "today_count": 0,
            "portfolio_tasks_without_journal_count": len(portfolio_tasks),
            "recorded_portfolio_codes": [],
            "missing_portfolio_codes": missing_codes,
            "parse_error": str(exc),
        }

    task_codes = {str(task.get("code") or "") for task in portfolio_tasks if task.get("code")}
    today_codes = {entry.code for entry in entries if entry.date == as_of and entry.code in task_codes}
    missing_codes = sorted(task_codes - today_codes)
    return {
        "as_of": as_of,
        "today_count": len(today_codes),
        "portfolio_tasks_without_journal_count": len(missing_codes),
        "recorded_portfolio_codes": sorted(today_codes),
        "missing_portfolio_codes": missing_codes,
        "parse_error": None,
    }


def _annotate_portfolio_tasks_with_journal(portfolio_tasks: list[dict], decision_journal: dict) -> None:
    recorded_codes = set(decision_journal.get("recorded_portfolio_codes") or [])
    for task in portfolio_tasks:
        task["journal_recorded"] = str(task.get("code") or "") in recorded_codes


def _universe_report_decision_journal_coverage(as_of: str | None, reports_ready: bool) -> dict:
    if not as_of or not reports_ready:
        return {
            "as_of": as_of,
            "actionable_count": 0,
            "recorded_actionable_count": 0,
            "actionable_without_journal_count": 0,
            "recorded_actionable_codes": [],
            "missing_actionable_codes": [],
            "missing_actionable_items": [],
            "today_universe_report_count": 0,
            "parse_error": None,
        }

    try:
        rows = get_universe_report_json() or []
        entries = load_decision_journal()
    except Exception as exc:
        return {
            "as_of": as_of,
            "actionable_count": 0,
            "recorded_actionable_count": 0,
            "actionable_without_journal_count": 0,
            "recorded_actionable_codes": [],
            "missing_actionable_codes": [],
            "missing_actionable_items": [],
            "today_universe_report_count": 0,
            "parse_error": str(exc),
        }

    actionable_actions = {"enter", "wait_pullback", "reduce", "exit"}
    action_urgency = {"exit": 0, "reduce": 1, "enter": 2, "wait_pullback": 3}
    actionable_rows = [
        row
        for row in rows
        if row.get("code") and str(row.get("daily_action") or "") in actionable_actions
    ]
    actionable_codes = {str(row.get("code") or "") for row in actionable_rows}
    today_report_codes = {
        entry.code
        for entry in entries
        if entry.date == as_of and entry.source == "universe_report" and entry.code
    }
    recorded_codes = actionable_codes & today_report_codes
    missing_codes = actionable_codes - recorded_codes
    missing_items = []
    for row in actionable_rows:
        code = str(row.get("code") or "")
        if code not in missing_codes:
            continue
        priority = row.get("daily_priority")
        try:
            priority_int = int(priority) if priority is not None else 50
        except (TypeError, ValueError):
            priority_int = 50
        action = str(row.get("daily_action") or "")
        missing_items.append({
            "code": code,
            "name": str(row.get("name") or code),
            "action": action,
            "label": str(row.get("daily_action_label") or row.get("daily_action") or ""),
            "reason": str(row.get("daily_action_reason") or row.get("no_buy_reason") or "依候選股報表補復盤理由"),
            "key_price": row.get("daily_key_price"),
            "invalidation": row.get("daily_invalidation"),
            "priority": priority_int,
            "_urgency": action_urgency.get(action, 99),
        })
    missing_items.sort(key=lambda item: (item["_urgency"], -item["priority"], item["code"]))
    for item in missing_items:
        item.pop("_urgency", None)
    return {
        "as_of": as_of,
        "actionable_count": len(actionable_codes),
        "recorded_actionable_count": len(recorded_codes),
        "actionable_without_journal_count": len(missing_codes),
        "recorded_actionable_codes": sorted(recorded_codes),
        "missing_actionable_codes": sorted(missing_codes),
        "missing_actionable_items": missing_items[:8],
        "today_universe_report_count": len(today_report_codes),
        "parse_error": None,
    }


def _review_section(
    key: str,
    label: str,
    status: str,
    message: str,
    next_action_key: str | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "next_action_key": next_action_key,
    }


def _build_readiness_review(
    data_status: dict,
    reports_ready: bool,
    signal_status: dict,
    fundamentals_status: dict,
    decision_journal: dict,
    universe_report_journal: dict | None = None,
    output_freshness: dict | None = None,
) -> dict:
    sections: list[dict] = []

    data_as_of = data_status.get("last_data_as_of") or "未知"
    stale_days = data_status.get("stale_days")
    data_run_status = data_status.get("last_run_status")
    if data_run_status == "stalled":
        data_section = _review_section(
            "data",
            "資料日",
            "blocked",
            data_status.get("last_error_summary") or data_status.get("last_error") or "資料更新執行過久，可能已中斷；請重新啟動每日更新。",
            "restart_stalled_update",
        )
    elif data_run_status == "failed":
        data_section = _review_section(
            "data",
            "資料日",
            "blocked",
            data_status.get("last_error_summary") or data_status.get("last_error") or "資料更新失敗，需先查看更新錯誤。",
            "fix_data_update",
        )
    elif data_status.get("is_stale"):
        data_section = _review_section(
            "data",
            "資料日",
            "blocked",
            f"資料最新日 {data_as_of}{f'，已落後 {stale_days} 天' if stale_days is not None else ''}。",
            "update_data",
        )
    else:
        data_section = _review_section(
            "data",
            "資料日",
            "ready",
            f"資料最新日 {data_as_of}，可進入報表檢查。",
        )
    sections.append(data_section)

    daily_info = (signal_status.get("out_files") or {}).get("daily_brief_json", {})
    if not reports_ready:
        report_section = _review_section(
            "reports",
            "交易報表",
            "blocked",
            "缺少 summary.json、universe_report.csv 或 daily_brief.json。",
            "run_signals",
        )
    elif daily_info.get("update_required"):
        report_section = _review_section(
            "reports",
            "交易報表",
            "blocked",
            "daily_brief.json 標記為需更新，需重新跑每日更新流程。",
            "refresh_daily_brief",
        )
    else:
        report_section = _review_section(
            "reports",
            "交易報表",
            "ready",
            "summary、候選股報告與每日作戰表都已存在。",
        )
    sections.append(report_section)

    if data_status.get("outputs_lag_raw_data"):
        raw_section = _review_section(
            "raw_outputs",
            "原始資料 / 報表",
            "blocked",
            data_status.get("raw_data_warning") or "ohlcv.csv 比交易輸出新，需重新產生訊號與報表。",
            "run_signals_for_raw_data",
        )
    else:
        raw_as_of = data_status.get("raw_ohlcv_as_of")
        raw_section = _review_section(
            "raw_outputs",
            "原始資料 / 報表",
            "ready",
            f"OHLCV 原始資料已與交易輸出對齊{f'：{raw_as_of}' if raw_as_of else '。'}",
        )
    sections.append(raw_section)

    if output_freshness:
        if output_freshness.get("status") == "blocked":
            output_section = _review_section(
                "output_freshness",
                "輸出日期",
                "blocked",
                output_freshness.get("message") or "輸出檔日期與資料日不一致。",
                "refresh_outputs",
            )
        elif output_freshness.get("status") == "warning":
            output_section = _review_section(
                "output_freshness",
                "輸出日期",
                "warning",
                output_freshness.get("message") or "部分輸出檔缺少日期稽核資訊。",
                "run_signals",
            )
        else:
            output_section = _review_section(
                "output_freshness",
                "輸出日期",
                "ready",
                output_freshness.get("message") or "輸出檔日期已對齊資料日。",
            )
        sections.append(output_section)

    note_status = signal_status.get("manual_note_status") or {}
    if note_status.get("update_required"):
        note_section = _review_section(
            "market_note",
            "人工盤後筆記",
            "warning",
            note_status.get("stale_reason") or "人工盤後筆記已過期，建議補今天版本。",
            "update_market_note",
        )
    else:
        note_section = _review_section(
            "market_note",
            "人工盤後筆記",
            "ready",
            "人工盤後筆記可用或目前不阻擋交易輸出。",
        )
    sections.append(note_section)

    total = int(fundamentals_status.get("total_codes") or 0)
    complete = int(fundamentals_status.get("complete_count") or 0)
    coverage = float(fundamentals_status.get("coverage_pct") or 0)
    fill_readiness = fundamentals_status.get("priority_fill_readiness") or {}
    if total <= 0 or complete >= total:
        fundamental_section = _review_section(
            "fundamentals",
            "基本面避雷資料",
            "ready",
            f"基本面完整 {complete}/{total} 檔，覆蓋率 {coverage:.1f}%。",
        )
    elif fill_readiness.get("status") == "invalid":
        fundamental_section = _review_section(
            "fundamentals",
            "基本面避雷資料",
            "blocked",
            "priority CSV 有格式問題，需先修正後再預覽合併。",
            "fix_fundamentals_csv",
        )
    elif fill_readiness.get("can_merge"):
        fundamental_section = _review_section(
            "fundamentals",
            "基本面避雷資料",
            "warning",
            f"已有 {int(fill_readiness.get('complete_code_count') or 0)} 檔可合併，合併後需重跑訊號。",
            "merge_fundamentals",
        )
    else:
        fundamental_section = _review_section(
            "fundamentals",
            "基本面避雷資料",
            "warning",
            f"基本面完整 {complete}/{total} 檔，覆蓋率 {coverage:.1f}%。",
            "fill_fundamentals",
        )
    sections.append(fundamental_section)

    missing_decisions = int(decision_journal.get("portfolio_tasks_without_journal_count") or 0)
    if missing_decisions > 0:
        journal_section = _review_section(
            "decision_journal",
            "持股決策紀錄",
            "warning",
            f"持股待辦還有 {missing_decisions} 檔尚未留下今天理由。",
            "record_decisions",
        )
    else:
        journal_section = _review_section(
            "decision_journal",
            "持股決策紀錄",
            "ready",
            "今日持股待辦都已有決策紀錄，或目前沒有持股待辦。",
        )
    sections.append(journal_section)

    universe_report_journal = universe_report_journal or {}
    missing_report_decisions = int(universe_report_journal.get("actionable_without_journal_count") or 0)
    actionable_count = int(universe_report_journal.get("actionable_count") or 0)
    if missing_report_decisions > 0:
        report_journal_section = _review_section(
            "universe_report_journal",
            "候選股復盤",
            "warning",
            f"今日候選股可行動清單 {actionable_count} 檔，尚有 {missing_report_decisions} 檔未由報表留下決策日誌。",
            "record_report_decisions",
        )
    else:
        report_journal_section = _review_section(
            "universe_report_journal",
            "候選股復盤",
            "ready",
            "候選股可行動清單都已記錄，或目前沒有可行動候選股。",
        )
    sections.append(report_journal_section)

    top_blocker = next((item for item in sections if item["status"] == "blocked"), None)
    if top_blocker:
        overall_label = "需先處理阻塞"
        top_blocker_key = top_blocker["key"]
    elif any(item["status"] == "warning" for item in sections):
        overall_label = "可用但有待補"
        top_blocker_key = None
    else:
        overall_label = "全部就緒"
        top_blocker_key = None

    return {
        "overall_label": overall_label,
        "top_blocker_key": top_blocker_key,
        "sections": sections,
    }


def get_workflow_status() -> dict:
    data_status = get_data_status()
    signal_status = get_signals_status()
    fundamentals_status = get_fundamentals_status()

    actions: list[dict] = []
    hard_blocked = False
    running = False

    data_run_status = data_status.get("last_run_status")
    data_running = data_run_status == "running"
    signals_running = signal_status.get("run_status") == "running"
    if data_running or signals_running:
        running = True
        actions.append(_action(
            key="wait_running_job",
            title="等待背景流程完成",
            detail="資料更新或訊號計算仍在執行中，完成後 Dashboard 會刷新。",
            priority=100,
            severity="info",
            action_type="wait",
        ))

    if data_run_status == "stalled":
        hard_blocked = True
        actions.append(_action(
            key="restart_stalled_update",
            title="資料更新可能卡住，重新啟動",
            detail=data_status.get("last_error_summary") or data_status.get("last_error") or "資料更新執行過久，可能已中斷；請重新啟動每日更新。",
            priority=99,
            severity="danger",
            action_type="update_data",
            command="python3 scripts/daily_update.py --months 1",
            success_check="確認 data_as_of 更新到最新交易日，且 summary.json / universe_report.csv / daily_brief.json 都已重新產生。",
            expected_outputs=DAILY_UPDATE_OUTPUTS,
        ))
    elif data_run_status == "failed":
        hard_blocked = True
        actions.append(_action(
            key="fix_data_update",
            title="資料更新失敗，先處理錯誤",
            detail=data_status.get("last_error_summary") or data_status.get("last_error") or "更新流程失敗，請查看後端 log。",
            priority=98,
            severity="danger",
            action_type="update_data",
            command="python3 scripts/daily_update.py --months 1",
            success_check="確認 data_as_of 更新到最新交易日，且 summary.json / universe_report.csv / daily_brief.json 都已重新產生。",
            expected_outputs=DAILY_UPDATE_OUTPUTS,
        ))
    elif data_status.get("is_stale"):
        hard_blocked = True
        stale_days = data_status.get("stale_days")
        detail = (
            f"資料最新日 {data_status.get('last_data_as_of') or '未知'}"
            f"{f'，已落後 {stale_days} 天' if stale_days is not None else ''}。"
        )
        actions.append(_action(
            key="update_data",
            title="先更新日線與訊號資料",
            detail=detail,
            priority=95,
            severity="danger",
            action_type="update_data",
            command="python3 scripts/daily_update.py --months 1",
            success_check="確認 data_as_of 更新到最新交易日，且 summary.json / universe_report.csv / daily_brief.json 都已重新產生。",
            expected_outputs=DAILY_UPDATE_OUTPUTS,
        ))

    if data_status.get("outputs_lag_raw_data"):
        hard_blocked = True
        actions.append(_action(
            key="run_signals_for_raw_data",
            title="原始日線已更新，重算交易輸出",
            detail=data_status.get("raw_data_warning") or "ohlcv.csv 比 summary / universe_report 新，需重新產生訊號與報表。",
            priority=93,
            severity="danger",
            action_type="run_signals",
            command="python3 scripts/run_signals.py",
            success_check="確認 summary.json、universe_report.csv、daily_brief.json 的 as_of 追上 raw_ohlcv_as_of。",
            expected_outputs=SIGNAL_OUTPUTS,
        ))

    for file_key, label in (
        ("summary_json", "summary.json"),
        ("universe_report_csv", "universe_report.csv"),
        ("daily_brief_json", "daily_brief.json"),
    ):
        parse_error = _file_parse_error(signal_status, file_key)
        if parse_error:
            hard_blocked = True
            actions.append(_action(
                key=f"fix_{file_key}",
                title=f"{label} 解析失敗",
                detail=parse_error,
                priority=92,
                severity="danger",
                action_type="run_signals",
                command="python3 scripts/run_signals.py",
                success_check="確認 summary.json、universe_report.csv、daily_brief.json 都存在且可解析。",
                expected_outputs=SIGNAL_OUTPUTS,
            ))

    base_reports_ready = (
        _file_exists(signal_status, "summary_json")
        and not _file_parse_error(signal_status, "summary_json")
        and _file_exists(signal_status, "universe_report_csv")
        and not _file_parse_error(signal_status, "universe_report_csv")
        and _file_exists(signal_status, "daily_brief_json")
        and not _file_parse_error(signal_status, "daily_brief_json")
    )
    output_freshness = _build_output_freshness(data_status, signal_status)
    reports_ready = base_reports_ready and output_freshness.get("status") != "blocked"
    decision_guardrails = _build_decision_guardrails(data_status, signal_status, base_reports_ready, output_freshness)
    close_checklist = _build_close_checklist(data_status, signal_status, reports_ready)
    portfolio_tasks = _build_portfolio_tasks(reports_ready)
    decision_journal = _decision_journal_coverage(data_status.get("last_data_as_of"), portfolio_tasks)
    _annotate_portfolio_tasks_with_journal(portfolio_tasks, decision_journal)
    universe_report_journal = _universe_report_decision_journal_coverage(data_status.get("last_data_as_of"), reports_ready)
    readiness_review = _build_readiness_review(
        data_status,
        base_reports_ready,
        signal_status,
        fundamentals_status,
        decision_journal,
        universe_report_journal,
        output_freshness,
    )
    if not base_reports_ready:
        hard_blocked = True
        actions.append(_action(
            key="run_signals",
            title="產生候選股與每日作戰表",
            detail="缺少 summary.json、universe_report.csv 或 daily_brief.json，報告頁無法完整判斷。",
            priority=90,
            severity="danger",
            action_type="run_signals",
            command="python3 scripts/run_signals.py",
            success_check="確認 summary.json、universe_report.csv、daily_brief.json 都存在且可解析。",
            expected_outputs=SIGNAL_OUTPUTS,
        ))

    if base_reports_ready and output_freshness.get("status") == "blocked":
        hard_blocked = True
        actions.append(_action(
            key="refresh_outputs",
            title="重新產生今日交易輸出",
            detail=output_freshness.get("message") or "summary、universe_report 或 daily_brief 的日期與資料日不一致。",
            priority=89,
            severity="danger",
            action_type="run_signals",
            command="python3 scripts/run_signals.py",
            success_check="確認 summary.json、universe_report.csv、daily_brief.json 的 as_of 都等於 data_as_of。",
            expected_outputs=SIGNAL_OUTPUTS,
        ))

    daily_info = (signal_status.get("out_files") or {}).get("daily_brief_json", {})
    if daily_info.get("update_required"):
        hard_blocked = True
        actions.append(_action(
            key="refresh_daily_brief",
            title="每日作戰表需要更新",
            detail="daily_brief.json 的資料狀態標記為需更新，先重新跑每日更新流程。",
            priority=88,
            severity="danger",
            action_type="update_data",
            command="python3 scripts/daily_update.py --months 1",
            success_check="確認 data_as_of 更新到最新交易日，且 summary.json / universe_report.csv / daily_brief.json 都已重新產生。",
            expected_outputs=DAILY_UPDATE_OUTPUTS,
        ))

    note_status = signal_status.get("manual_note_status") or {}
    if note_status.get("update_required"):
        actions.append(_action(
            key="update_market_note",
            title="補今天的人工盤後筆記",
            detail=note_status.get("stale_reason") or "人工盤後筆記已過期，水位與明日 checklist 可能不是今天版本。",
            priority=70,
            severity="warning",
            action_type="market_note",
        ))

    total = int(fundamentals_status.get("total_codes") or 0)
    complete = int(fundamentals_status.get("complete_count") or 0)
    coverage = float(fundamentals_status.get("coverage_pct") or 0)
    fill_readiness = fundamentals_status.get("priority_fill_readiness") or {}
    fill_guide = fundamentals_status.get("priority_fill_guide") or {}
    priority_validation = fundamentals_status.get("priority_csv_validation") or {}
    priority_error_count = len(priority_validation.get("errors") or [])
    priority_warning_count = len(priority_validation.get("warnings") or [])
    if total > 0 and complete < total:
        if fill_readiness.get("status") == "invalid":
            issue = _format_fundamentals_csv_issue(priority_validation)
            actions.append(_action(
                key="fix_fundamentals_csv",
                title="修正基本面避雷補資料 CSV",
                detail=f"{issue}。修正後再預覽合併。",
                priority=63,
                severity="danger",
                action_type="fundamentals",
                command="python3 scripts/check_fundamentals.py",
            ))
        elif fill_readiness.get("can_merge"):
            ready_count = int(fill_readiness.get("complete_code_count") or 0)
            label = fill_guide.get("next_action_label") or f"可先預覽合併 {ready_count} 檔"
            actions.append(_action(
                key="merge_fundamentals",
                title="合併基本面避雷補資料",
                detail=f"{label}；合併後需重新產生訊號，基本面避雷結果才會進正式 summary / report。",
                priority=62,
                severity="warning",
                action_type="fundamentals",
                command="POST /api/system/fundamentals-priority-fill/merge",
            ))
        else:
            suggestion = fill_readiness.get("suggested_action") or "先補齊優先 CSV，再預覽合併。"
            actions.append(_action(
                key="fill_fundamentals",
                title="補齊基本面避雷資料",
                detail=f"目前完整 {complete}/{total} 檔，覆蓋率 {coverage:.1f}%。{suggestion}",
                priority=35,
                severity="warning",
                action_type="fundamentals",
                command="python3 scripts/check_fundamentals.py",
            ))

    if decision_journal.get("portfolio_tasks_without_journal_count", 0) > 0:
        missing = decision_journal["portfolio_tasks_without_journal_count"]
        actions.append(_action(
            key="record_decisions",
            title="補齊今日持股決策紀錄",
            detail=f"持股待辦還有 {missing} 檔尚未留下今天的買賣 / 續抱理由，建議收盤後補齊方便復盤。",
            priority=45,
            severity="info",
            action_type="decision_journal",
        ))

    if universe_report_journal.get("actionable_without_journal_count", 0) > 0:
        missing = universe_report_journal["actionable_without_journal_count"]
        actions.append(_action(
            key="record_report_decisions",
            title="補候選股報表復盤紀錄",
            detail=f"今日可小試 / 等回測 / 減碼 / 出場的候選股還有 {missing} 檔未從報表留下決策日誌。",
            priority=33,
            severity="info",
            action_type="universe_report",
        ))

    actions.sort(key=lambda item: item["priority"], reverse=True)
    workflow_metrics = _build_workflow_metrics(
        actions,
        close_checklist,
        portfolio_tasks,
        decision_journal_today_count=int(decision_journal.get("today_count") or 0),
        portfolio_tasks_without_journal_count=int(decision_journal.get("portfolio_tasks_without_journal_count") or 0),
        universe_actionable_count=int(universe_report_journal.get("actionable_count") or 0),
        universe_actionable_without_journal_count=int(universe_report_journal.get("actionable_without_journal_count") or 0),
    )

    if running:
        overall = "running"
        headline = "背景流程執行中，先等待完成"
    elif hard_blocked:
        overall = "blocked"
        headline = "今日交易前仍有必要前置工作"
    elif any(item["severity"] == "warning" for item in actions):
        overall = "warning"
        headline = "短線工作流可用，但有資料待補"
    else:
        overall = "ready"
        headline = "資料、訊號與作戰表已就緒"

    return {
        "overall_status": overall,
        "can_trade_today": overall in ("ready", "warning"),
        "headline": headline,
        "data_as_of": data_status.get("last_data_as_of"),
        "next_actions": actions[:6],
        "close_checklist": close_checklist,
        "portfolio_tasks": portfolio_tasks,
        "workflow_metrics": workflow_metrics,
        "decision_guardrails": decision_guardrails,
        "readiness_review": readiness_review,
        "checks": {
            "data": {
                "status": data_status.get("last_run_status"),
                "is_stale": bool(data_status.get("is_stale")),
                "last_data_as_of": data_status.get("last_data_as_of"),
                "raw_ohlcv_as_of": data_status.get("raw_ohlcv_as_of"),
                "outputs_lag_raw_data": bool(data_status.get("outputs_lag_raw_data")),
                "raw_data_warning": data_status.get("raw_data_warning"),
            },
            "signals": {
                "status": signal_status.get("run_status"),
                "reports_ready": reports_ready,
            },
            "output_freshness": output_freshness,
            "fundamentals": {
                "complete_count": complete,
                "total_codes": total,
                "coverage_pct": coverage,
                "priority_fill_status": fill_readiness.get("status"),
                "priority_fill_can_merge": bool(fill_readiness.get("can_merge")),
                "priority_fill_complete_code_count": int(fill_readiness.get("complete_code_count") or 0),
                "priority_fill_error_count": priority_error_count,
                "priority_fill_warning_count": priority_warning_count,
            },
            "decision_journal": decision_journal,
            "universe_report_journal": universe_report_journal,
        },
    }
