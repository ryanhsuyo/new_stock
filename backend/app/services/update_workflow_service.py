"""每日更新流程狀態服務。

此服務只彙整既有狀態，不直接執行回補、訊號或檔案 I/O。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from app.services.daily_check_service import get_daily_check_report
from app.services.update_service import get_data_status
from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS, SIGNAL_OUTPUTS, expected_outputs_for_command

DAILY_UPDATE_COMMAND = "python3 scripts/daily_update.py --months 1"
RUN_SIGNALS_COMMAND = "python3 scripts/run_signals.py"
DAILY_CHECK_COMMAND = "python3 scripts/daily_check.py --write-report"
DATA_COVERAGE_BLOCK_THRESHOLD = 80.0
_BACKEND = Path(__file__).resolve().parent.parent.parent


def _action(
    key: str,
    title: str,
    detail: str,
    command: str | None,
    expected_outputs: list[str],
    copy_command: str | None = None,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_copy_command = copy_command or (f"cd {_BACKEND}\n{command}" if command else None)
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "action_type": "copy_command" if command else "wait",
        "command": command,
        "copy_command": resolved_copy_command,
        "expected_outputs": expected_outputs,
        "action_payload": dict(action_payload or {}),
    }


def _step(key: str, label: str, status: str, message: str, command: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "message": message,
        "command": command,
    }


def _expected_outputs_for_command(command: str | None) -> list[str]:
    return expected_outputs_for_command(command)


def _file_view_command(payload: dict[str, Any]) -> str:
    if payload.get("kind") != "file":
        return ""
    file_path = str(payload.get("file_path") or "").strip()
    if not file_path:
        return ""
    return f"cat {file_path}"


def _daily_check_blocker_action(daily_check: dict[str, Any] | None) -> dict[str, Any]:
    actions = list((daily_check or {}).get("top_actions") or [])
    top = next((item for item in actions if item.get("status") == "block"), None) or (actions[0] if actions else {})
    payload = top.get("action_payload") if isinstance(top.get("action_payload"), dict) else {}
    command = str(payload.get("command") or _file_view_command(payload) or top.get("next_action") or "")
    copy_command = str(payload.get("copy_command") or "") or None
    expected_outputs = payload.get("expected_outputs")
    return _action(
        str(top.get("key") or "daily_check_blocker"),
        str(top.get("title") or "處理 Daily Check 阻塞"),
        str(top.get("message") or "Daily Check 判斷交易輸出不可使用，請先處理優先待辦。"),
        command or None,
        list(expected_outputs) if isinstance(expected_outputs, list) else _expected_outputs_for_command(command),
        copy_command=copy_command,
        action_payload=payload,
    )


def get_update_workflow_status() -> dict[str, Any]:
    """回傳 PM 視角的每日資料更新流程狀態。"""
    data_status = get_data_status()
    daily_check = get_daily_check_report()

    data_as_of = data_status.get("last_data_as_of")
    raw_as_of = data_status.get("raw_ohlcv_as_of")
    batch_id = data_status.get("batch_id")
    coverage_report_path = data_status.get("coverage_report_path")
    data_coverage_pct = data_status.get("data_coverage_pct")
    last_run_status = data_status.get("last_run_status")
    data_is_stale = bool(data_status.get("is_stale"))
    outputs_lag_raw_data = bool(data_status.get("outputs_lag_raw_data"))
    coverage_too_low = (
        data_coverage_pct is not None
        and float(data_coverage_pct) < DATA_COVERAGE_BLOCK_THRESHOLD
    )
    daily_check_missing = daily_check is None
    daily_check_stale = bool((daily_check or {}).get("snapshot_is_stale"))
    daily_check_can_trade = bool((daily_check or {}).get("can_use_trade_outputs", True))

    if last_run_status == "running":
        next_action = _action(
            "wait_update_running",
            "等待資料更新完成",
            "背景資料更新執行中，完成後再檢查訊號與 Daily Check。",
            None,
            DAILY_UPDATE_OUTPUTS,
        )
        current_step = "wait_update_running"
        overall_status = "action_required"
        headline = "資料更新執行中，先不要使用交易輸出。"
        can_use_trade_outputs = False
        data_step_status = "running"
        signal_step_status = "blocked"
        daily_step_status = "blocked"
    elif last_run_status in {"failed", "stalled"} or data_is_stale or not data_as_of:
        next_action = _action(
            "update_market_data",
            "先更新日線與訊號資料",
            "資料已過期或尚未建立，請先跑每日更新流程，再回來檢查 Dashboard。",
            DAILY_UPDATE_COMMAND,
            DAILY_UPDATE_OUTPUTS,
        )
        current_step = "update_market_data"
        overall_status = "blocked"
        headline = "資料日線需要更新，交易輸出暫停使用。"
        can_use_trade_outputs = False
        data_step_status = "blocked"
        signal_step_status = "blocked"
        daily_step_status = "blocked"
    elif outputs_lag_raw_data:
        next_action = _action(
            "regenerate_signals",
            "重新產生訊號與候選報告",
            "ohlcv.csv 已比交易輸出更新，必須重算 summary / universe_report / daily_brief。",
            RUN_SIGNALS_COMMAND,
            SIGNAL_OUTPUTS,
        )
        current_step = "regenerate_signals"
        overall_status = "blocked"
        headline = "原始日線已更新，但交易輸出仍落後。"
        can_use_trade_outputs = False
        data_step_status = "done"
        signal_step_status = "blocked"
        daily_step_status = "blocked"
    elif coverage_too_low:
        next_action = _action(
            "improve_data_coverage",
            "補齊追蹤清單日線覆蓋率",
            f"資料覆蓋率 {float(data_coverage_pct):.2f}% 低於 {DATA_COVERAGE_BLOCK_THRESHOLD:.0f}% 門檻，請重新執行每日更新。",
            DAILY_UPDATE_COMMAND,
            DAILY_UPDATE_OUTPUTS,
        )
        current_step = "improve_data_coverage"
        overall_status = "blocked"
        headline = "追蹤清單資料覆蓋率不足，交易輸出暫停使用。"
        can_use_trade_outputs = False
        data_step_status = "blocked"
        signal_step_status = "blocked"
        daily_step_status = "blocked"
    elif daily_check_missing or daily_check_stale:
        next_action = _action(
            "refresh_daily_check",
            "刷新 PM Daily Check",
            "交易輸出可讀，但每日 PM 摘要快照需重新產生，避免沿用舊待辦。",
            (daily_check or {}).get("snapshot_refresh_command") or DAILY_CHECK_COMMAND,
            ["backend/out/daily_check.json"],
        )
        current_step = "refresh_daily_check"
        overall_status = "action_required"
        headline = "交易輸出可用，但 PM 摘要需要刷新。"
        can_use_trade_outputs = daily_check_can_trade
        data_step_status = "done"
        signal_step_status = "done"
        daily_step_status = "warning"
    elif not daily_check_can_trade:
        next_action = _daily_check_blocker_action(daily_check)
        current_step = "resolve_daily_check_blocker"
        overall_status = "blocked"
        headline = "Daily Check 判斷交易輸出不可使用，需先處理阻塞。"
        can_use_trade_outputs = False
        data_step_status = "done"
        signal_step_status = "done"
        daily_step_status = "blocked"
    else:
        next_action = None
        current_step = "ready"
        overall_status = "ready"
        headline = "每日更新流程完成，可以使用最新交易輸出。"
        can_use_trade_outputs = daily_check_can_trade
        data_step_status = "done"
        signal_step_status = "done"
        daily_step_status = "done"

    steps = [
        _step(
            "update_market_data",
            "更新資料",
            data_step_status,
            (
                f"資料日 {data_as_of or '尚無'}，原始日線 {raw_as_of or '尚無'}。"
                if data_step_status == "done"
                else data_status.get("last_error_summary") or data_status.get("last_warning_summary") or "請先更新日線與訊號資料。"
            ),
            DAILY_UPDATE_COMMAND,
        ),
        _step(
            "regenerate_signals",
            "產生訊號",
            signal_step_status,
            data_status.get("raw_data_warning") or "summary、daily_brief 與 universe_report 需跟上最新 ohlcv.csv。",
            RUN_SIGNALS_COMMAND,
        ),
        _step(
            "refresh_daily_check",
            "刷新 PM 摘要",
            daily_step_status,
            (
                "尚無 daily_check.json，請產生每日摘要。"
                if daily_check_missing
                else (daily_check or {}).get("snapshot_stale_reason") or "Daily Check 快照已是今天。"
            ),
            DAILY_CHECK_COMMAND,
        ),
    ]

    return {
        "generated_at": date.today().isoformat(),
        "overall_status": overall_status,
        "headline": headline,
        "can_use_trade_outputs": can_use_trade_outputs,
        "current_step": current_step,
        "next_action": next_action,
        "steps": steps,
        "checks": {
            "data_as_of": data_as_of,
            "raw_ohlcv_as_of": raw_as_of,
            "last_run_status": last_run_status,
            "batch_id": batch_id,
            "coverage_report_path": coverage_report_path,
            "data_coverage_pct": data_coverage_pct,
            "data_is_stale": data_is_stale,
            "outputs_lag_raw_data": outputs_lag_raw_data,
            "daily_check_missing": daily_check_missing,
            "daily_check_is_stale": daily_check_stale,
        },
    }
