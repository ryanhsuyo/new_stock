"""Workflow command output contracts shared by PM status services and scripts."""

from __future__ import annotations

DAILY_UPDATE_OUTPUTS = [
    "backend/data/ohlcv.csv",
    "backend/out/update_status.json",
    "backend/out/summary.json",
    "backend/out/universe_report.csv",
    "backend/out/daily_brief.json",
    "backend/out/daily_check.json",
]

SIGNAL_OUTPUTS = [
    "backend/out/summary.json",
    "backend/out/universe_report.csv",
    "backend/out/daily_brief.json",
    "backend/out/daily_check.json",
]

DAILY_CHECK_OUTPUTS = ["backend/out/daily_check.json"]


def expected_outputs_for_command(command: str | None) -> list[str]:
    command = str(command or "").strip()
    if command.startswith("python3 scripts/daily_update.py"):
        return list(DAILY_UPDATE_OUTPUTS)
    if command == "python3 scripts/run_signals.py":
        return list(SIGNAL_OUTPUTS)
    if command == "python3 scripts/daily_check.py --write-report":
        return list(DAILY_CHECK_OUTPUTS)
    return []
