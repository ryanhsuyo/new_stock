#!/usr/bin/env python3
"""
scheduled_update.py — launchd 排程 wrapper：錯過就補跑、一天成功一次就停。

背景：launchd 的 StartCalendarInterval 睡眠會補發、但**跨重開機不會**；
機器若在排程時間關機，當天更新就永遠不跑（2026-07-06 後實際發生一週）。
解法：plist 改用 RunAtLoad + StartInterval（每小時醒來檢查），由本 wrapper 判斷：

    「現在已過今天的目標時間，且今天目標時間後尚未成功跑過」→ 執行
    否則 → 1 秒內退出（無 I/O 負擔）

成功（子程序 exit 0）才寫 marker；失敗則下個整點自動重試——「直到做一次為止」。
兩個市場的更新腳本皆冪等（merge 去重），重複執行無害。

用法（launchd 呼叫；也可手動）：
    python3 scripts/scheduled_update.py --market tw            # 台股（目標 15:30）
    python3 scripts/scheduled_update.py --market us            # 美股（目標 08:30，美股收盤=台灣清晨）
    python3 scripts/scheduled_update.py --market tw --dry-run  # 只顯示決策不執行
    python3 scripts/scheduled_update.py --market us --force    # 忽略 marker 立即執行

安裝 / 移除：scripts/setup_schedule.sh / scripts/remove_schedule.sh。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, time as dtime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_OUT = _BACKEND / "out"

MARKETS: dict[str, dict] = {
    "tw": {
        "threshold": dtime(15, 30),  # 台股收盤 13:30，TWSE 資料 ~15:00 上架
        "cmd": ["scripts/daily_update.py", "--months", "1",
                "--log-file", str(_OUT / "update.log")],
    },
    "us": {
        "threshold": dtime(8, 30),   # 美股收盤 = 台灣清晨 4-5 點，08:30 資料已齊
        "cmd": ["scripts/backfill_ohlcv_us.py", "--months", "1"],
    },
}


def should_run(now: datetime, last_success: datetime | None, threshold: dtime) -> tuple[bool, str]:
    """回傳 (是否該跑, 原因)。規則：now 已過今天門檻，且門檻後尚未成功過。"""
    threshold_today = now.replace(hour=threshold.hour, minute=threshold.minute,
                                  second=0, microsecond=0)
    if now < threshold_today:
        return False, f"尚未到今天目標時間 {threshold_today:%H:%M}"
    if last_success is not None and last_success >= threshold_today:
        return False, f"今天已成功（{last_success:%Y-%m-%d %H:%M}），跳過"
    return True, ("今天目標時間後尚未成功，補跑" if last_success else "無成功紀錄，執行")


def _read_marker(path: Path) -> datetime | None:
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="排程 wrapper：錯過補跑、日成功一次即止")
    parser.add_argument("--market", choices=sorted(MARKETS), required=True)
    parser.add_argument("--force", action="store_true", help="忽略 marker 與時間門檻，立即執行")
    parser.add_argument("--dry-run", action="store_true", help="只顯示決策，不執行")
    args = parser.parse_args()

    cfg = MARKETS[args.market]
    marker = _OUT / f".sched_last_success_{args.market}"
    log_path = _OUT / f"scheduled_update_{args.market}.log"
    now = datetime.now()
    last = _read_marker(marker)

    run, reason = (True, "--force") if args.force else should_run(now, last, cfg["threshold"])
    line = f"[{now:%Y-%m-%d %H:%M:%S}] market={args.market} run={run} ({reason})"
    print(line)
    if args.dry_run or not run:
        return 0

    _OUT.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, *cfg["cmd"]]
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n{line}\n  cmd: {' '.join(cmd)}\n")
        log.flush()
        rc = subprocess.run(cmd, cwd=_BACKEND, stdout=log,
                            stderr=subprocess.STDOUT).returncode
        done = datetime.now()
        log.write(f"[{done:%Y-%m-%d %H:%M:%S}] exit={rc}\n")

    if rc == 0:
        marker.write_text(done.isoformat(), encoding="utf-8")
        print(f"成功，marker 已更新：{marker.name}")
    else:
        print(f"失敗 exit={rc}，marker 不更新（下個整點自動重試）", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
