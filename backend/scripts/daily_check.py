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
from app.services.signals_service import get_universe  # noqa: E402
from app.services.workflow_outputs import expected_outputs_for_command  # noqa: E402
from app.services.workflow_text import preview_numbered_lines  # noqa: E402
from doctor import build_doctor_report  # noqa: E402

_SEVERITY_RANK = {"block": 0, "warn": 1, "ok": 2}
_DATA_REPAIR_COMMAND = "python3 scripts/daily_update.py --months 12"
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
        check.get("key") == "outputs" and check.get("status") == "block"
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


def _print_action_payload(payload: dict[str, Any]) -> None:
    kind = payload.get("kind")
    if kind == "file" and payload.get("file_path"):
        print(f"   查看檔案：{payload['file_path']}")
    elif kind == "copy_text":
        preview_items = preview_numbered_lines(str(payload.get("copy_text") or ""))
        if preview_items:
            print(f"   優先補基本面：{', '.join(preview_items)}")
        if payload.get("file_path"):
            print(f"   目標檔案：{payload['file_path']}")
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
            "status": str(check.get("status") or ""),
            "title": str(check.get("title") or ""),
            "message": str(check.get("message") or ""),
            "next_action": str(check.get("next_action") or ""),
            "details": dict(check.get("details") or {}),
        }
        if isinstance(check.get("action_payload"), dict):
            item["action_payload"] = _normalize_action_payload(check["action_payload"])
        candidates.append(item)
    candidates.extend(extra_actions or [])
    candidates.sort(key=lambda item: (_SEVERITY_RANK.get(item["status"], 9), item["key"]))
    return candidates[: max(1, limit)]


def build_daily_summary(
    report: dict[str, Any],
    limit: int = 3,
    universe: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    generated_at = report.get("generated_at")
    data_repair = _data_repair_summary(universe)
    extra_actions = [action for action in [_data_repair_action(data_repair)] if action]
    return {
        "overall_status": report.get("overall_status"),
        "exit_code": int(report.get("exit_code") or 0),
        "generated_at": generated_at,
        "source_report_generated_at": generated_at,
        "data_as_of": _data_as_of_from_report(report),
        "can_use_trade_outputs": _can_use_trade_outputs(report),
        "data_repair": data_repair,
        "top_actions": _top_actions(report, limit=limit, extra_actions=extra_actions),
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


def run_daily_check(args: argparse.Namespace) -> int:
    report = build_doctor_report(args.backend)
    summary = build_daily_summary(report, limit=args.limit, universe=load_universe_for_daily_check())
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
