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
    "us": {
        "threshold": dtime(10, 0),
        "artifacts": ["strategy_trade_report_us_2026-05-01.md"],
        # 快照沒寫出來，今天的觀察就永遠驗不回來了
        "artifact_globs": ["us_signal_snapshots/us_signal_snapshot_*.json"],
    },
    "tw": {
        "threshold": dtime(15, 40),
        # 台股一次產三份 profile 報告；少一份就不能算整批成功
        "artifacts": [
            "strategy_trade_report_tw_2026-05-01.md",
            "strategy_trade_report_tw_old_wang_2026-05-01.md",
            "strategy_trade_report_tw_steady_momentum_2026-05-01.md",
            "strategy_trade_audit_tw_2026-05-01.md",
        ],
    },
}


def _read_marker(path: Path) -> datetime | None:
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def stale_artifacts(market: str, started_at: datetime, out_dir: Path | None = None) -> list[str]:
    """回傳這次沒有真的重新產生的 artifact。

    產生器中途失敗時，先寫好的幾份看起來是新的，剩下的還停在昨天；
    只看 exit code 會讓「部分成功」被當成整批成功。
    """
    out_dir = out_dir or _OUT
    cutoff = started_at.timestamp()
    config = REPORTS[market]
    stale: list[str] = []
    for name in config["artifacts"]:
        path = out_dir / name
        if not path.exists() or path.stat().st_mtime < cutoff:
            stale.append(name)
    for pattern in config.get("artifact_globs", []):
        if not any(p.stat().st_mtime >= cutoff for p in out_dir.glob(pattern)):
            stale.append(pattern)
    return stale


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
    started_at = datetime.now()
    for command in commands:
        result = subprocess.run(command, cwd=_BACKEND)
        if result.returncode != 0:
            print(f"失敗 exit={result.returncode}: {' '.join(command)}", file=sys.stderr)
            return result.returncode

    stale = stale_artifacts(args.market, started_at)
    if stale:
        print(f"未重新產生：{'、'.join(stale)}；不寫成功 marker", file=sys.stderr)
        return 1

    done = datetime.now()
    marker.write_text(done.isoformat(), encoding="utf-8")
    print(f"報告完成（{len(REPORTS[args.market]['artifacts'])} 份），marker 已更新：{marker.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
