#!/usr/bin/env python3
"""
update_all_data.py — 統一資料更新入口

步驟：
    1. 回補 OHLCV（backfill_ohlcv_twse.py --months N --include-current-month）
    2. 更新籌碼（update_chips.py）
    3. 重算訊號（run_daily_signals）
    4. 寫入 backend/out/update_status.json
    5. 寫入 backend/out/daily_check.json

用法（直接執行）：
    cd backend
    python3 scripts/update_all_data.py              # 補最近 1 個月
    python3 scripts/update_all_data.py --months 3   # 補最近 3 個月

用法（排程 / launchd / cron，需絕對路徑）：
    /usr/local/bin/python3 /path/to/backend/scripts/update_all_data.py --months 1

選項：
    --months N          回補月數（預設 1）
    --log-file PATH     log 輸出路徑（預設 backend/out/update.log，傳 'none' 停用）
    --no-lock           略過並發保護（測試用）

輸出：
    backend/out/summary.json
    backend/out/universe_report.csv
    backend/out/update_status.json
    backend/out/daily_check.json
    backend/out/update.log           （追加模式）
"""

import argparse
import logging
import os
import sys
from pathlib import Path

_HERE    = Path(__file__).resolve().parent   # backend/scripts/
_BACKEND = _HERE.parent                      # backend/

sys.path.insert(0, str(_BACKEND))

from app.services.notify_service import notify_update_failure, notify_update_success  # noqa: E402
from app.services.update_service import run_full_update  # noqa: E402
from daily_check import build_daily_summary, write_daily_summary  # noqa: E402

# 模組層級路徑常數：測試時可 monkeypatch
_DEFAULT_LOG = _BACKEND / "out" / "update.log"
_PID_FILE    = _BACKEND / "out" / "update.pid"


# ---------------------------------------------------------------------------
# 並發保護（PID 檔案）
# ---------------------------------------------------------------------------

def _pid_is_running(pid: int) -> bool:
    """回傳 True 若指定 PID 目前仍在執行（Unix）。"""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def acquire_lock() -> bool:
    """
    寫入 PID 檔以取得執行鎖。
    若同一 PID 仍活著，回傳 False（表示已有另一個 instance 在跑）。
    PID 已結束或檔案損毀時，覆寫並回傳 True。
    """
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
            if _pid_is_running(old_pid) and old_pid != os.getpid():
                return False
        except (ValueError, OSError):
            pass   # 檔案損毀，直接覆寫
    _PID_FILE.write_text(str(os.getpid()))
    return True


def release_lock() -> None:
    """移除 PID 檔。"""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_file: Path | None) -> None:
    """
    設定 logging：
      - 永遠輸出到 stdout
      - 若 log_file 非 None，同時以追加模式寫入檔案
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def write_daily_check_report(backend: Path = _BACKEND) -> Path:
    """更新流程結束後寫出 PM Daily Check 快照，供 Dashboard 讀取。"""
    import doctor

    report = doctor.build_doctor_report(backend)
    summary = build_daily_summary(report, limit=3)
    return write_daily_summary(summary, backend)


# ---------------------------------------------------------------------------
# 引數解析
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
    description="統一更新 OHLCV + 籌碼 + 訊號，並寫入 update_status.json"
    )
    parser.add_argument(
        "--months", type=int, default=1, metavar="N",
        help="回補幾個月（預設 1，每日更新用；初次建資料用 12）",
    )
    parser.add_argument(
        "--log-file", type=str, default=str(_DEFAULT_LOG), metavar="PATH",
        help="log 輸出路徑（預設 backend/out/update.log，傳 'none' 停用）",
    )
    parser.add_argument(
        "--no-lock", action="store_true",
        help="略過 PID 並發保護（測試用）",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 核心邏輯（可被測試直接呼叫）
# ---------------------------------------------------------------------------

def run_update_job(
    months: int,
    log_file: Path | None = _DEFAULT_LOG,
    skip_lock: bool = False,
) -> int:
    """
    執行完整更新流程。

    回傳碼：
        0 — 成功
        1 — 更新失敗（backfill 或 signals 錯誤）
        2 — 已有另一個 instance 在執行（跳過本次）
    """
    setup_logging(log_file)
    log = logging.getLogger(__name__)

    log.info("=== update_all_data 開始  months=%d ===", months)

    # 並發保護
    if not skip_lock:
        if not acquire_lock():
            log.warning("偵測到另一個 update_all_data 仍在執行（PID 檔存在），跳過本次。")
            return 2

    try:
        status = run_full_update(months=months)
        try:
            path = write_daily_check_report(_BACKEND)
            log.info("✓ Daily Check 已更新：%s", path)
        except Exception as exc:
            log.warning("Daily Check 寫入失敗：%s", exc)

        if status["last_run_status"] == "success":
            log.info(
                "✓ 更新成功  資料最新日=%s  stale=%s(%s天)",
                status["last_data_as_of"],
                status["is_stale"],
                status["stale_days"],
            )
            notify_update_success(status["last_data_as_of"], status["stale_days"])
            return 0
        elif status["last_run_status"] == "stale":
            log.warning(
                "⚠ 更新完成但資料仍過期  資料最新日=%s  stale=%s(%s天)  %s",
                status["last_data_as_of"],
                status["is_stale"],
                status["stale_days"],
                status.get("last_warning") or "",
            )
            notify_update_failure(
                status.get("last_warning") or "更新完成但資料仍過期",
                status["last_run_started_at"],
            )
            return 1
        else:
            log.error("✗ 更新失敗  錯誤=%s", status["last_error"])
            notify_update_failure(
                status["last_error"] or "未知錯誤",
                status["last_run_started_at"],
            )
            return 1

    except Exception as exc:
        log.exception("未預期錯誤: %s", exc)
        notify_update_failure(str(exc))
        return 1

    finally:
        if not skip_lock:
            release_lock()
        log.info("=== update_all_data 結束 ===")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    raw_log = args.log_file.strip()
    log_file: Path | None = None if raw_log.lower() == "none" else Path(raw_log)

    exit_code = run_update_job(
        months=args.months,
        log_file=log_file,
        skip_lock=args.no_lock,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
