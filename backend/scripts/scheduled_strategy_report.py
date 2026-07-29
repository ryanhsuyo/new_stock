#!/usr/bin/env python3
"""每日分市場刷新資料並產生策略報告；成功一次後當日不重跑。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, time as dtime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from scheduled_update import should_run

_BACKEND = Path(__file__).resolve().parent.parent
_OUT = _BACKEND / "out"

REPORTS = {
    "us": {"threshold": dtime(10, 0)},
    "tw": {"threshold": dtime(15, 40)},
}


def _read_marker(path: Path) -> datetime | None:
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="刷新指定市場並產生獨立策略報告")
    parser.add_argument("--market", choices=sorted(REPORTS), required=True)
    parser.add_argument("--force", action="store_true", help="忽略時間與成功 marker 立即執行")
    parser.add_argument("--dry-run", action="store_true", help="只顯示是否執行")
    args = parser.parse_args(argv)

    _OUT.mkdir(parents=True, exist_ok=True)
    marker = _OUT / f".strategy_report_last_success_{args.market}"
    now = datetime.now()
    run, reason = (
        (True, "--force")
        if args.force
        else should_run(now, _read_marker(marker), REPORTS[args.market]["threshold"])
    )
    print(f"[{now:%Y-%m-%d %H:%M:%S}] market={args.market} run={run} ({reason})")
    if args.dry_run or not run:
        return 0

    commands = [
        [sys.executable, "scripts/scheduled_update.py", "--market", args.market, "--force"],
        [sys.executable, "scripts/generate_strategy_trade_report.py", "--market", args.market],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=_BACKEND)
        if result.returncode != 0:
            print(f"失敗 exit={result.returncode}: {' '.join(command)}", file=sys.stderr)
            return result.returncode

    done = datetime.now()
    marker.write_text(done.isoformat(), encoding="utf-8")
    print(f"報告完成，marker 已更新：{marker.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
