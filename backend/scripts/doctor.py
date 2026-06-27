#!/usr/bin/env python3
"""專案健康檢查：資料流、輸出同步、基本面覆蓋與復盤缺口。"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.fundamental_service import get_fundamentals_status  # noqa: E402
from app.services.workflow_outputs import (  # noqa: E402
    FUNDAMENTALS_PRIORITY_IMPORT_APPLY_COMMAND,
    FUNDAMENTALS_PRIORITY_IMPORT_COMMAND,
    FUNDAMENTALS_PRIORITY_IMPORT_OUTPUTS,
    FUNDAMENTALS_PRIORITY_TEMPLATE_COMMAND,
)
from app.services.workflow_outputs import expected_outputs_for_command  # noqa: E402
from app.services.workflow_text import preview_numbered_lines  # noqa: E402


_REQUIRED_PACKAGES = ("fastapi", "pydantic", "uvicorn", "pytest", "requests", "pandas", "numpy")
_ACTIONABLE_ACTIONS = {"enter", "wait_pullback", "reduce", "exit"}
_SEVERITY_RANK = {"ok": 0, "warn": 1, "block": 2}
_CD_BACKEND_PREFIX = "cd backend && "
_DAILY_UPDATE_COMMAND = "cd backend && python3 scripts/daily_update.py --months 1"
_COVERAGE_BLOCK_THRESHOLD = 80.0


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_universe(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _check(
    key: str,
    status: str,
    title: str,
    message: str,
    *,
    details: dict | None = None,
    next_action: str = "",
    action_payload: dict | None = None,
) -> dict:
    result = {
        "key": key,
        "status": status,
        "title": title,
        "message": message,
        "details": details or {},
        "next_action": next_action,
    }
    if action_payload:
        result["action_payload"] = action_payload
    return result


def _short_command(command: str) -> str:
    command = command.strip()
    if command.startswith(_CD_BACKEND_PREFIX):
        return command[len(_CD_BACKEND_PREFIX):].strip()
    return command


def _copy_command(command: str, backend: Path) -> str:
    command = _short_command(command)
    if command.startswith("python3 "):
        return f"cd {backend}\n{command}"
    return command


def _expected_outputs(command: str) -> list[str]:
    command = _short_command(command)
    outputs = expected_outputs_for_command(command)
    if outputs:
        return outputs
    if command == "python3 scripts/export_universe_review_todo.py":
        return ["backend/out/universe_report_review_todo.md"]
    return []


def _looks_like_command(command: str) -> bool:
    short = _short_command(command)
    return short.startswith("python3 ") or short.startswith("POST ")


def _normalize_check_action(check: dict, backend: Path) -> dict:
    next_action = str(check.get("next_action") or "")
    if next_action:
        check["next_action"] = _short_command(next_action)

    payload = check.get("action_payload")
    if isinstance(payload, dict):
        payload = dict(payload)
        command = str(payload.get("command") or "")
        if command:
            short = _short_command(command)
            payload["command"] = short
            if payload.get("kind") == "command" and not payload.get("copy_command"):
                payload["copy_command"] = _copy_command(short, backend)
            if payload.get("kind") == "command" and not payload.get("expected_outputs"):
                payload["expected_outputs"] = _expected_outputs(short)
        check["action_payload"] = payload
        return check

    if next_action and _looks_like_command(next_action):
        short = _short_command(next_action)
        check["action_payload"] = {
            "kind": "command",
            "command": short,
            "copy_command": _copy_command(short, backend),
            "expected_outputs": _expected_outputs(short),
        }
    return check


def _overall(checks: list[dict]) -> str:
    worst = max((_SEVERITY_RANK.get(check["status"], 0) for check in checks), default=0)
    for status, rank in _SEVERITY_RANK.items():
        if rank == worst:
            return status
    return "ok"


def _exit_code(status: str) -> int:
    return {"ok": 0, "warn": 1, "block": 2}.get(status, 1)


def _check_python() -> dict:
    missing = [pkg for pkg in _REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
    if missing:
        return _check(
            "python",
            "block",
            "Python 套件缺失",
            f"缺少必要套件：{', '.join(missing)}",
            details={"executable": sys.executable, "missing_packages": missing},
            next_action="cd backend && python3 -m pip install -r requirements.txt",
        )
    return _check(
        "python",
        "ok",
        "Python 環境可用",
        "必要套件已可 import。",
        details={"executable": sys.executable, "packages": list(_REQUIRED_PACKAGES)},
    )


def _check_outputs(backend: Path, universe_rows: list[dict[str, str]]) -> dict:
    out = backend / "out"
    update_status = _read_json(out / "update_status.json", {})
    summary = _read_json(out / "summary.json", {})
    daily_brief = _read_json(out / "daily_brief.json", {})

    required_paths = {
        "update_status": out / "update_status.json",
        "summary": out / "summary.json",
        "daily_brief": out / "daily_brief.json",
        "universe_report": out / "universe_report.csv",
    }
    missing = [name for name, path in required_paths.items() if not path.exists()]
    details = {
        "last_run_status": update_status.get("last_run_status"),
        "last_data_as_of": update_status.get("last_data_as_of"),
        "summary_as_of": summary.get("as_of"),
        "daily_brief_as_of": daily_brief.get("as_of") or (daily_brief.get("data_status") or {}).get("last_data_as_of"),
        "universe_as_of": universe_rows[0].get("data_as_of") if universe_rows else None,
        "missing_files": missing,
    }
    if missing:
        return _check(
            "outputs",
            "block",
            "交易輸出缺檔",
            f"缺少輸出檔：{', '.join(missing)}",
            details=details,
            next_action=_DAILY_UPDATE_COMMAND,
        )

    dates = [details["last_data_as_of"], details["summary_as_of"], details["daily_brief_as_of"], details["universe_as_of"]]
    non_empty_dates = [d for d in dates if d]
    if len(set(non_empty_dates)) > 1:
        return _check(
            "outputs",
            "block",
            "交易輸出日期不同步",
            "update_status、summary、daily_brief 或 universe_report 的資料日不一致。",
            details=details,
            next_action="cd backend && python3 scripts/run_signals.py",
        )
    if update_status.get("last_run_status") not in {"success", "stale"}:
        return _check(
            "outputs",
            "warn",
            "更新狀態不是成功",
            f"last_run_status={update_status.get('last_run_status') or '未執行'}",
            details=details,
            next_action=_DAILY_UPDATE_COMMAND,
        )
    return _check("outputs", "ok", "交易輸出同步", "summary、daily_brief、universe_report 的資料日一致。", details=details)


def _check_universe(universe_rows: list[dict[str, str]]) -> dict:
    row_count = len(universe_rows)
    data_ok_count = sum(1 for row in universe_rows if _truthy(row.get("data_ok")))
    actionable_count = sum(1 for row in universe_rows if (row.get("daily_action") or "") in _ACTIONABLE_ACTIONS)
    status = "ok" if row_count and data_ok_count == row_count else "warn"
    message = f"{data_ok_count}/{row_count} 檔資料可判斷；可行動 {actionable_count} 檔。"
    return _check(
        "universe_report",
        status,
        "候選股報告覆蓋",
        message,
        details={"row_count": row_count, "data_ok_count": data_ok_count, "actionable_count": actionable_count},
        next_action="" if status == "ok" else _DAILY_UPDATE_COMMAND,
    )


def _check_data_coverage(backend: Path) -> dict:
    path = backend / "out" / "data_coverage_report.json"
    report = _read_json(path, None)
    if not isinstance(report, dict):
        return _check(
            "data_coverage",
            "warn",
            "資料覆蓋率報告缺失",
            "尚無 data_coverage_report.json，無法確認追蹤清單日線覆蓋率。",
            details={"coverage_report_path": str(path)},
            next_action=_DAILY_UPDATE_COMMAND,
            action_payload={
                "kind": "command",
                "command": _DAILY_UPDATE_COMMAND,
            },
        )

    coverage_pct = float(report.get("coverage_pct") or 0.0)
    tracked_count = int(report.get("tracked_count") or 0)
    ok_count = int(report.get("ok_count") or 0)
    status = "ok"
    title = "資料覆蓋率可用"
    next_action = ""
    if tracked_count and coverage_pct < _COVERAGE_BLOCK_THRESHOLD:
        status = "block"
        title = "資料覆蓋率不足"
        next_action = _DAILY_UPDATE_COMMAND
    elif tracked_count and coverage_pct < 100.0:
        status = "warn"
        title = "資料覆蓋率未滿"
        next_action = _DAILY_UPDATE_COMMAND

    message = f"追蹤清單覆蓋率 {coverage_pct:.2f}%（{ok_count}/{tracked_count}）。"
    return _check(
        "data_coverage",
        status,
        title,
        message,
        details={
            "batch_id": report.get("batch_id"),
            "coverage_pct": coverage_pct,
            "tracked_count": tracked_count,
            "ok_count": ok_count,
            "expected_trading_day": report.get("expected_trading_day"),
            "raw_ohlcv_as_of": report.get("raw_ohlcv_as_of"),
            "coverage_report_path": str(path),
        },
        next_action=next_action,
        action_payload={
            "kind": "command",
            "command": _DAILY_UPDATE_COMMAND,
        } if next_action else None,
    )


def _format_priority_issue(validation: dict) -> str:
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    issue = (errors or warnings or [None])[0]
    if not issue:
        return ""
    kind = "錯誤" if errors else "警告"
    row = issue.get("row_number")
    code = issue.get("code") or "未填代碼"
    field = issue.get("field") or "欄位"
    value = issue.get("value")
    message = issue.get("message") or "請確認格式"
    return f"{kind}：第 {row} 列 {code} {field}={value!r}，{message}"


def _load_fundamentals_report(backend: Path) -> dict:
    report = _read_json(backend / "out" / "fundamentals_report.json", {})
    workflow = report.get("workflow_summary") or {}
    if workflow.get("fill_targets_copy_text"):
        return report
    try:
        if Path(backend).resolve() != Path(_BACKEND).resolve():
            return report
    except OSError:
        return report
    try:
        fresh = get_fundamentals_status()
    except Exception:
        return report
    return {**report, **fresh} if isinstance(fresh, dict) else report


def _check_fundamentals(backend: Path, universe_rows: list[dict[str, str]]) -> dict:
    total = len(universe_rows)
    complete = sum(1 for row in universe_rows if _truthy(row.get("fundamental_data_ok")))
    report = _load_fundamentals_report(backend)
    readiness = report.get("priority_fill_readiness") or {}
    validation = report.get("priority_csv_validation") or {}
    fill_status = readiness.get("status") or "unknown"
    error_count = len(validation.get("errors") or [])
    warning_count = len(validation.get("warnings") or [])
    first_issue = _format_priority_issue(validation)

    details = {
        "complete_count": complete,
        "total_count": total,
        "priority_fill_status": fill_status,
        "can_merge": bool(readiness.get("can_merge")),
        "complete_code_count": int(readiness.get("complete_code_count") or 0),
        "filled_code_count": int(readiness.get("filled_code_count") or 0),
        "filled_field_count": int(readiness.get("filled_field_count") or 0),
        "priority_fill_error_count": error_count,
        "priority_fill_warning_count": warning_count,
        "first_priority_issue": first_issue,
    }
    workflow = report.get("workflow_summary") or {}
    fill_targets_copy_text = str(workflow.get("fill_targets_copy_text") or "")
    priority_csv_path = str(backend / "out" / "fundamentals_priority_fill.csv")

    if fill_status == "invalid":
        return _check(
            "fundamentals",
            "block",
            "基本面避雷補資料有誤",
            f"priority CSV 有 {error_count} 個錯誤、{warning_count} 個警告，需先修正再合併。",
            details=details,
            next_action=readiness.get("suggested_action") or "修正 backend/data/fundamentals_priority_fill.csv 後重新預覽",
            action_payload={
                "kind": "file",
                "file_path": priority_csv_path,
                "confirm_message": "先修正 priority CSV 的錯誤值，再重新預覽合併。",
            },
        )

    if total and complete > 0:
        status = "ok"
        next_action = ""
    elif fill_status == "ready_to_merge":
        status = "warn"
        next_action = "到 Dashboard 預覽/合併，或 POST /api/system/fundamentals-priority-fill/merge；合併後執行 python3 scripts/run_signals.py"
        action_payload = {
            "kind": "api",
            "method": "POST",
            "endpoint": "/api/system/fundamentals-priority-fill/merge",
            "dry_run": True,
            "confirm_message": "先預覽基本面避雷補資料合併結果，不會正式改寫 fundamentals.json。",
        }
    elif fill_status in {"empty", "ready_to_preview"}:
        status = "warn"
        next_action = readiness.get("suggested_action") or "補齊 priority CSV 的必要欄位後重新預覽"
        action_payload = {
            "kind": "copy_text",
            "copy_text": fill_targets_copy_text,
            "file_path": priority_csv_path,
            "write_template_command": FUNDAMENTALS_PRIORITY_TEMPLATE_COMMAND,
            "prepare_import_command": FUNDAMENTALS_PRIORITY_IMPORT_COMMAND,
            "prepare_import_apply_command": FUNDAMENTALS_PRIORITY_IMPORT_APPLY_COMMAND,
            "expected_outputs": list(FUNDAMENTALS_PRIORITY_IMPORT_OUTPUTS),
        } if fill_targets_copy_text else {
            "kind": "file",
            "file_path": priority_csv_path,
            "write_template_command": FUNDAMENTALS_PRIORITY_TEMPLATE_COMMAND,
            "prepare_import_command": FUNDAMENTALS_PRIORITY_IMPORT_COMMAND,
            "prepare_import_apply_command": FUNDAMENTALS_PRIORITY_IMPORT_APPLY_COMMAND,
            "expected_outputs": list(FUNDAMENTALS_PRIORITY_IMPORT_OUTPUTS),
        }
    else:
        status = "warn"
        next_action = "cd backend && python3 scripts/check_fundamentals.py --write-priority-csv"
        action_payload = {
            "kind": "command",
            "command": next_action,
        }

    return _check(
        "fundamentals",
        status,
        "基本面避雷覆蓋",
        f"{complete}/{total} 檔可進行基本面避雷評分。",
        details=details,
        next_action=next_action,
        action_payload=action_payload if status != "ok" else None,
    )


def _check_decision_journal(backend: Path, universe_rows: list[dict[str, str]]) -> dict:
    entries = _read_json(backend / "data" / "decision_journal.json", [])
    if not isinstance(entries, list):
        entries = []
    as_of = universe_rows[0].get("data_as_of") if universe_rows else None
    actionable_codes = {
        row.get("code")
        for row in universe_rows
        if (row.get("daily_action") or "") in _ACTIONABLE_ACTIONS and row.get("code")
    }
    recorded_codes = {
        str(entry.get("code") or "")
        for entry in entries
        if entry.get("date") == as_of and entry.get("source") == "universe_report"
    }
    missing = sorted(code for code in actionable_codes if code not in recorded_codes)
    status = "ok" if not missing else "warn"
    review_todo_path = backend / "out" / "universe_report_review_todo.md"
    review_todo_exists = review_todo_path.exists()
    action_payload = None
    if status == "ok":
        next_action = ""
    elif review_todo_exists:
        next_action = f"依 {review_todo_path} 補 source='universe_report' 的決策日誌"
        action_payload = {
            "kind": "file",
            "file_path": str(review_todo_path),
            "confirm_message": "依候選股復盤草稿補 source='universe_report' 的決策日誌；此動作不會修改交易紀錄、持倉或現金。",
        }
    else:
        next_action = "cd backend && python3 scripts/export_universe_review_todo.py"
    return _check(
        "decision_journal",
        status,
        "候選股復盤紀錄",
        f"可行動 {len(actionable_codes)} 檔，尚未復盤 {len(missing)} 檔。",
        details={
            "as_of": as_of,
            "actionable_count": len(actionable_codes),
            "recorded_count": len(actionable_codes) - len(missing),
            "missing_actionable_count": len(missing),
            "missing_codes": missing[:20],
            "review_todo_exists": review_todo_exists,
            "review_todo_path": str(review_todo_path),
        },
        next_action=next_action,
        action_payload=action_payload,
    )


def _check_trades(backend: Path) -> dict:
    trades = _read_json(backend / "data" / "trades.json", [])
    positions = _read_json(backend / "data" / "positions.json", {})
    trade_count = len(trades) if isinstance(trades, list) else 0
    legacy_holdings = positions.get("holdings") if isinstance(positions, dict) else {}
    status = "ok"
    message = f"交易紀錄 {trade_count} 筆；持倉以 trades.json 自動推算。"
    if not isinstance(trades, list):
        status = "block"
        message = "trades.json 不是陣列，交易紀錄無法解析。"
    return _check(
        "trades",
        status,
        "交易與持倉來源",
        message,
        details={"trade_count": trade_count, "legacy_positions_holdings": len(legacy_holdings or {})},
        next_action="" if status == "ok" else "修正 backend/data/trades.json 格式，或從交易匯入流程重新匯入",
    )


def build_doctor_report(backend: Path = _BACKEND) -> dict:
    backend = Path(backend)
    universe_rows = _read_universe(backend / "out" / "universe_report.csv")
    checks = [
        _check_python(),
        _check_outputs(backend, universe_rows),
        _check_data_coverage(backend),
        _check_universe(universe_rows),
        _check_fundamentals(backend, universe_rows),
        _check_decision_journal(backend, universe_rows),
        _check_trades(backend),
    ]
    checks = [_normalize_check_action(check, backend) for check in checks]
    overall = _overall(checks)
    return {
        "generated_at": date.today().isoformat(),
        "backend": str(backend),
        "overall_status": overall,
        "exit_code": _exit_code(overall),
        "checks": checks,
    }


def print_report(report: dict) -> None:
    print(f"專案健康檢查：{report['overall_status'].upper()}")
    print(f"backend: {report['backend']}")
    for check in report["checks"]:
        marker = {"ok": "OK", "warn": "WARN", "block": "BLOCK"}.get(check["status"], check["status"].upper())
        print(f"[{marker}] {check['title']} - {check['message']}")
        first_issue = (check.get("details") or {}).get("first_priority_issue")
        if first_issue:
            print(f"       第一筆問題：{first_issue}")
        missing_codes = (check.get("details") or {}).get("missing_codes") or []
        if missing_codes:
            preview = ", ".join(str(code) for code in missing_codes[:10])
            suffix = " ..." if len(missing_codes) > 10 else ""
            print(f"       缺少復盤代碼：{preview}{suffix}")
        if check.get("next_action"):
            print(f"       下一步：{check['next_action']}")
        payload = check.get("action_payload") or {}
        if isinstance(payload, dict):
            kind = payload.get("kind")
            if kind == "file" and payload.get("file_path"):
                print(f"       查看檔案：{payload['file_path']}")
            elif kind == "copy_text":
                print("       可複製清單：已準備文字內容")
                preview_items = preview_numbered_lines(str(payload.get("copy_text") or ""))
                if preview_items:
                    print(f"       優先補基本面：{', '.join(preview_items)}")
                if payload.get("file_path"):
                    print(f"       目標檔案：{payload['file_path']}")
            elif kind == "api" and payload.get("method") and payload.get("endpoint"):
                print(f"       API 動作：{payload['method']} {payload['endpoint']}")
            if payload.get("confirm_message"):
                print(f"       提醒：{payload['confirm_message']}")
        expected_outputs = payload.get("expected_outputs") if isinstance(payload, dict) else None
        if expected_outputs:
            print("       跑完檢查：")
            for output in expected_outputs:
                print(f"         - {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="檢查資料流、輸出檔、基本面避雷覆蓋率與復盤缺口")
    parser.add_argument("--backend", type=Path, default=_BACKEND, help="backend 目錄路徑")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_doctor_report(args.backend)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    raise SystemExit(report["exit_code"])


if __name__ == "__main__":
    main()
