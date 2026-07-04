"""
update_service.py — 統一更新服務

職責：
  1. 協調 backfill + run_signals 兩個步驟
  2. 寫入 / 讀取 update_status.json
  3. 計算 is_stale / stale_days

設計說明：
  - backfill 透過 subprocess 執行（避免網路呼叫污染主進程）
  - 每日更新需包含當月資料，避免月初仍只分析上月底資料
  - signals 在進程內執行（已有完整 service 層）
  - _run_backfill 設計為模組層級函式，方便測試時 monkeypatch
"""

import sys
import csv
import hashlib
import inspect
import subprocess
import threading
from datetime import date, datetime
from pathlib import Path

import app.storage.update_store as update_store
from app.services.data_coverage_service import build_data_coverage_report, write_data_coverage_report
from app.services.fundamental_service import _load_leader_codes
from app.services.signals_service import OHLCV_PATH, get_summary, run_daily_signals
from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS
from app.storage.fundamental_store import (
    FUNDAMENTALS_CSV_PATH,
    format_csv_validation_error,
    load_fundamentals_from_csv,
    save_fundamentals,
    sync_fundamentals_csv,
    validate_fundamentals_csv,
)
from app.storage.update_store import load_update_status, save_update_status
from app.utils import count_missed_trading_days

# 防止 API 重複觸發背景更新
_bg_lock = threading.Lock()

_BACKEND = Path(__file__).resolve().parent.parent.parent
_BACKFILL_SCRIPT = _BACKEND / "scripts" / "backfill_ohlcv_twse.py"
_CHIPS_SCRIPT = _BACKEND / "scripts" / "update_chips.py"
_SCRIPTS = _BACKEND / "scripts"
RUNNING_STALLED_AFTER_SECONDS = 2 * 60 * 60
DAILY_UPDATE_COMMAND = "python3 scripts/daily_update.py --months 1"


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _run_subprocess(
    command: list[str],
    *,
    stream_output: bool = False,
) -> tuple[bool, str]:
    if not stream_output:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        return result.returncode == 0, output.strip()

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    output_parts: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            print(line, end="", flush=True)
            output_parts.append(line)
    returncode = process.wait()
    return returncode == 0, "".join(output_parts).strip()


def _run_backfill(months: int, *, stream_output: bool = False) -> tuple[bool, str]:
    """
    以 subprocess 執行 backfill_ohlcv_twse.py。
    回傳 (成功, 輸出文字)。

    此函式為模組層級，測試時可直接 monkeypatch。
    """
    return _run_subprocess(
        [
            sys.executable,
            str(_BACKFILL_SCRIPT),
            "--months",
            str(months),
            "--include-current-month",
        ],
        stream_output=stream_output,
    )


def _run_chips_update(*, stream_output: bool = False) -> tuple[bool, str]:
    """以 subprocess 執行 update_chips.py。"""
    return _run_subprocess(
        [sys.executable, str(_CHIPS_SCRIPT)],
        stream_output=stream_output,
    )


def _call_backfill(months: int, *, stream_output: bool) -> tuple[bool, str]:
    if stream_output:
        try:
            parameters = inspect.signature(_run_backfill).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "stream_output" in parameters:
            return _run_backfill(months, stream_output=True)
    return _run_backfill(months)


def _call_chips_update(*, stream_output: bool) -> tuple[bool, str]:
    if stream_output:
        try:
            parameters = inspect.signature(_run_chips_update).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "stream_output" in parameters:
            return _run_chips_update(stream_output=True)
    return _run_chips_update()


def _import_fundamentals() -> tuple[bool, str]:
    """若 fundamentals.csv 存在，匯入為 fundamentals.json。"""
    if not FUNDAMENTALS_CSV_PATH.exists():
        return True, "fundamentals.csv 不存在，略過基本面匯入"
    validation = validate_fundamentals_csv(FUNDAMENTALS_CSV_PATH)
    if not validation["valid"]:
        return False, format_csv_validation_error(validation, label="fundamentals.csv")
    data = load_fundamentals_from_csv(FUNDAMENTALS_CSV_PATH)
    save_fundamentals(data)
    return True, f"已匯入 {len(data)} 檔 fundamentals"


def _sync_fundamentals_template() -> tuple[bool, str]:
    """依 leaders.json 補齊 fundamentals.csv，不覆蓋既有值。"""
    codes = _load_leader_codes()
    if not codes:
        return True, "leaders.json 無股票清單，略過 fundamentals.csv 同步"
    result = sync_fundamentals_csv(codes)
    return True, f"fundamentals.csv 同步完成，新增 {result['added_count']} 檔"


def _get_last_data_as_of() -> str | None:
    """從 summary.json 的 as_of 欄位取得資料最新日。"""
    summary = get_summary()
    if summary:
        return summary.get("as_of")
    return None


def _get_raw_ohlcv_as_of() -> str | None:
    """從 ohlcv.csv 取得原始日線資料最新日，用來偵測回補後尚未重算 signals。"""
    if not OHLCV_PATH.exists():
        return None
    latest: str | None = None
    with OHLCV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            value = (row.get("date") or "").strip()
            if value and (latest is None or value > latest):
                latest = value
    return latest


def _summarize_error(err: str | None, max_len: int = 120) -> str | None:
    """取錯誤訊息的第一個有意義行，截斷至 max_len，供前端 banner 顯示。"""
    if not err:
        return None
    lines = [ln.strip() for ln in err.splitlines() if ln.strip()]
    first = lines[0] if lines else err
    return first[:max_len]


def _file_snapshot(path: Path) -> dict:
    try:
        stat = path.stat()
    except OSError:
        return {"input_ohlcv_mtime": None, "input_ohlcv_size": None}
    return {
        "input_ohlcv_mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "input_ohlcv_size": stat.st_size,
    }


def _build_batch_lineage(started_at: str) -> dict:
    snapshot = _file_snapshot(OHLCV_PATH)
    raw_as_of = _get_raw_ohlcv_as_of()
    seed = "|".join(
        [
            started_at,
            str(snapshot.get("input_ohlcv_mtime")),
            str(snapshot.get("input_ohlcv_size")),
            str(raw_as_of),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    compact_time = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return {
        "batch_id": f"{compact_time}-{digest}",
        "source": "daily_update",
        "run_started_at": started_at,
        "raw_ohlcv_as_of": raw_as_of,
        "coverage_report_path": None,
        **snapshot,
    }


def _run_signals_with_optional_lineage(lineage: dict) -> dict:
    try:
        parameters = inspect.signature(run_daily_signals).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "lineage" in parameters:
        return run_daily_signals(lineage=lineage)
    return run_daily_signals()


def _compute_stale(last_data_as_of: str | None) -> tuple[bool, int | None]:
    """
    回傳 (is_stale, stale_days)。
    stale_days 為日曆天數（供顯示用）；is_stale 以交易日判斷。
    若 last_data_as_of 為 None，視為 stale，stale_days = None。
    """
    if not last_data_as_of:
        return True, None
    try:
        data_date = date.fromisoformat(last_data_as_of)
        delta = (date.today() - data_date).days
        missed = count_missed_trading_days(data_date)
        return missed > 0, delta
    except ValueError:
        return True, None


def _schedule_health(status: str, overdue: bool, message: str) -> dict:
    return {
        "schedule_health_status": status,
        "schedule_is_overdue": overdue,
        "schedule_health_message": message,
    }


def _compute_schedule_health(
    last_run_status: str | None,
    last_run_finished_at: str | None,
    *,
    today: date | None = None,
) -> dict:
    if last_run_status == "stalled":
        return _schedule_health(
            "stalled",
            True,
            "資料更新執行超過 2 小時，可能已中斷；可重新啟動每日更新。",
        )
    if last_run_status == "running":
        return _schedule_health("running", False, "資料更新目前執行中。")
    if last_run_status == "failed":
        return _schedule_health(
            "failed",
            False,
            "最近一次資料更新失敗，請先查看錯誤摘要。",
        )
    if not last_run_status and not last_run_finished_at:
        return _schedule_health("never_run", False, "尚無自動更新完成紀錄。")
    if not last_run_finished_at:
        return _schedule_health(
            "invalid_timestamp",
            False,
            "更新狀態缺少完成時間，無法判斷排程健康。",
        )
    try:
        finished_date = datetime.fromisoformat(last_run_finished_at).date()
    except ValueError:
        return _schedule_health(
            "invalid_timestamp",
            False,
            "更新完成時間格式無效，無法判斷排程健康。",
        )

    missed = count_missed_trading_days(finished_date, today=today)
    if missed > 0:
        return _schedule_health(
            "overdue",
            True,
            f"自最近一次完成後已錯過 {missed} 個平日更新。",
        )
    return _schedule_health(
        "healthy",
        False,
        "最近一次排程更新已完成，未錯過已結束的平日。",
    )


def _manual_update_action() -> dict:
    return {
        "action_type": "copy_command",
        "command": DAILY_UPDATE_COMMAND,
        "copy_command": f"cd {_BACKEND}\n{DAILY_UPDATE_COMMAND}",
        "expected_outputs": list(DAILY_UPDATE_OUTPUTS),
        "label": "手動執行每日更新",
        "description": "安全 fallback：補 OHLCV、更新籌碼、重算策略輸出並刷新 Daily Check。",
    }


def _choose_last_data_as_of(
    status_as_of: str | None,
    summary_as_of: str | None,
) -> str | None:
    """選擇較新的資料日，避免手動重算 signals 後 update_status 落後。"""
    if not status_as_of:
        return summary_as_of
    if not summary_as_of:
        return status_as_of
    try:
        status_date = date.fromisoformat(status_as_of)
    except ValueError:
        return summary_as_of
    try:
        summary_date = date.fromisoformat(summary_as_of)
    except ValueError:
        return status_as_of
    return summary_as_of if summary_date > status_date else status_as_of


def _normalize_status_freshness(status: dict, is_stale: bool) -> dict:
    """若較新的 summary 已讓資料不再過期，避免 API 繼續顯示舊 stale 狀態。"""
    normalized = dict(status)
    if not is_stale and normalized.get("last_run_status") == "stale":
        normalized["last_run_status"] = "success"
        normalized["last_warning"] = None
        normalized["last_warning_summary"] = None
    return normalized


def _is_running_stalled(status: dict, *, now: datetime | None = None) -> bool:
    if status.get("last_run_status") != "running":
        return False
    started_raw = status.get("last_run_started_at")
    if not started_raw:
        return True
    try:
        started_at = datetime.fromisoformat(str(started_raw))
    except ValueError:
        return True
    current = now or datetime.now()
    return (current - started_at).total_seconds() > RUNNING_STALLED_AFTER_SECONDS


def _normalize_stalled_running(status: dict) -> dict:
    if not _is_running_stalled(status):
        return status
    normalized = dict(status)
    message = "資料更新執行超過 2 小時，可能已中斷；可重新啟動每日更新。"
    normalized["last_run_status"] = "stalled"
    normalized["last_error"] = normalized.get("last_error") or message
    normalized["last_error_summary"] = _summarize_error(normalized["last_error"])
    return normalized


def _write_daily_check_report() -> None:
    """背景更新結束後刷新 daily_check.json；失敗時由呼叫端記錄但不影響更新結果。"""
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
        # Daily Check 是 Dashboard 快照，不能讓快照寫入失敗覆蓋原本資料更新結果。
        pass


def _mark_update_failed(
    status: dict,
    message: str,
    *,
    refresh_daily_check: bool = True,
) -> None:
    """將目前更新批次標記為 failed，避免中斷後狀態長期停在 running。"""
    err_str = str(message)[:2000]
    status.update(
        last_run_finished_at=datetime.now().isoformat(timespec="seconds"),
        last_run_status="failed",
        last_error=err_str,
        last_error_summary=_summarize_error(err_str),
    )
    save_update_status(status)
    if refresh_daily_check:
        _refresh_daily_check_safely()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_data_status() -> dict:
    """
    讀取 update_status.json，補上 is_stale / stale_days。

    last_data_as_of 優先從狀態檔取，若無則嘗試讀 summary.json。
    """
    status = load_update_status()
    status = _normalize_stalled_running(status)
    last_data_as_of = _choose_last_data_as_of(
        status.get("last_data_as_of"),
        _get_last_data_as_of(),
    )
    raw_ohlcv_as_of = _get_raw_ohlcv_as_of()
    outputs_lag_raw_data = bool(
        raw_ohlcv_as_of
        and last_data_as_of
        and raw_ohlcv_as_of > last_data_as_of
    )
    is_stale, stale_days = _compute_stale(last_data_as_of)
    status = _normalize_status_freshness(status, is_stale)
    schedule_health = _compute_schedule_health(
        status.get("last_run_status"),
        status.get("last_run_finished_at"),
    )
    raw_data_warning = None
    if outputs_lag_raw_data:
        raw_data_warning = (
            f"ohlcv.csv 已更新到 {raw_ohlcv_as_of}，但交易輸出仍停在 {last_data_as_of}；"
            "請重新產生訊號與報表。"
        )
    return {
        **status,
        **schedule_health,
        "manual_update_action": _manual_update_action(),
        "last_data_as_of": last_data_as_of,
        "raw_ohlcv_as_of": raw_ohlcv_as_of,
        "outputs_lag_raw_data": outputs_lag_raw_data,
        "raw_data_warning": raw_data_warning,
        "price_basis": "latest_close",
        "price_basis_label": "最新收盤價",
        "price_basis_note": "投組估值與正式訊號使用 ohlcv.csv 最新收盤價，不是盤中即時市價。",
        "is_stale": is_stale,
        "stale_days": stale_days,
    }


def trigger_background_update(months: int = 1) -> dict:
    """
    在背景 thread 執行 run_full_update，立即回傳。

    若目前已在執行中（status file 或 lock），回傳 {"status": "already_running"}。
    否則回傳 {"status": "started"}。
    """
    # 先查狀態檔（快速檢查）
    current = load_update_status()
    if current.get("last_run_status") == "running" and not _is_running_stalled(current):
        return {"status": "already_running"}

    # 嘗試取得鎖（非阻塞）
    acquired = _bg_lock.acquire(blocking=False)
    if not acquired:
        return {"status": "already_running"}

    def _run() -> None:
        try:
            run_full_update(months)
        finally:
            _bg_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


def run_full_update(months: int = 1, *, stream_subprocess_output: bool = False) -> dict:
    """
    統一更新流程：backfill → run_signals → 寫狀態檔。

    回傳最新 data_status（含 is_stale / stale_days）。
    失敗時仍寫入狀態檔（last_run_status = "failed"，附 last_error）。
    """
    started_at = datetime.now().isoformat(timespec="seconds")
    lineage = _build_batch_lineage(started_at)
    status: dict = {
        "last_run_started_at": started_at,
        "last_run_finished_at": None,
        "last_run_status": "running",
        "last_error": None,
        "last_data_as_of": None,
        "batch_id": lineage["batch_id"],
        "lineage": lineage,
    }
    save_update_status(status)

    # ── Step 1: backfill ──
    try:
        ok, output = _call_backfill(
            months,
            stream_output=stream_subprocess_output,
        )
        if not ok:
            raise RuntimeError(f"backfill 失敗:\n{output}")
    except KeyboardInterrupt:
        _mark_update_failed(status, "資料更新被使用者中斷，尚未完成 backfill。")
        raise
    except Exception as exc:
        _mark_update_failed(status, str(exc))
        return get_data_status()

    # ── Step 2: update chips ──
    # 籌碼是輔助資料；若外部來源暫時失敗，保留舊 chips.json 並繼續跑日線訊號。
    chip_warning: str | None = None
    try:
        ok, output = _call_chips_update(
            stream_output=stream_subprocess_output,
        )
        if not ok:
            chip_warning = f"chips 更新失敗:\n{output}"[:2000]
    except Exception as exc:
        chip_warning = f"chips 更新失敗: {exc}"[:2000]
    if chip_warning:
        status.update(
            last_chip_error=chip_warning,
            last_chip_error_summary=_summarize_error(chip_warning),
        )
        save_update_status(status)

    # ── Step 3: sync + import fundamentals ──
    try:
        ok, output = _sync_fundamentals_template()
        if not ok:
            raise RuntimeError(output)
        ok, output = _import_fundamentals()
        if not ok:
            raise RuntimeError(output)
    except KeyboardInterrupt:
        _mark_update_failed(status, "資料更新被使用者中斷，尚未完成基本面資料同步。")
        raise
    except Exception as exc:
        _mark_update_failed(status, f"fundamentals 匯入失敗: {exc}")
        return get_data_status()

    # ── Step 4: write data coverage report ──
    coverage_warning: str | None = None
    try:
        coverage = build_data_coverage_report(batch_id=lineage["batch_id"])
        coverage_path = write_data_coverage_report(
            coverage,
            update_store.UPDATE_STATUS_PATH.parent,
        )
        lineage["coverage_report_path"] = str(coverage_path)
        lineage["raw_ohlcv_as_of"] = coverage.get("raw_ohlcv_as_of") or lineage.get("raw_ohlcv_as_of")
        status.update(
            batch_id=lineage["batch_id"],
            lineage=lineage,
            coverage_report_path=str(coverage_path),
            data_coverage_pct=coverage.get("coverage_pct"),
        )
        save_update_status(status)
    except Exception as exc:
        coverage_warning = f"coverage report 產生失敗: {exc}"[:2000]
        status.update(
            last_warning=coverage_warning,
            last_warning_summary=_summarize_error(coverage_warning),
            batch_id=lineage["batch_id"],
            lineage=lineage,
        )
        save_update_status(status)

    # ── Step 5: run signals ──
    try:
        result = _run_signals_with_optional_lineage(lineage)
        last_data_as_of: str | None = result.get("as_of")
    except KeyboardInterrupt:
        _mark_update_failed(status, "資料更新被使用者中斷，尚未完成 signals 重算。")
        raise
    except Exception as exc:
        _mark_update_failed(status, f"signals 失敗: {exc}")
        return get_data_status()

    # ── Completed ──
    finished_at = datetime.now().isoformat(timespec="seconds")
    is_stale, stale_days = _compute_stale(last_data_as_of)
    warning = None
    if is_stale:
        warning = f"更新完成但資料仍過期：資料最新日={last_data_as_of or '—'} stale_days={stale_days}"
    status.update(
        last_run_finished_at=finished_at,
        last_run_status="stale" if is_stale else "success",
        last_error=None,
        last_error_summary=None,
        last_warning=warning,
        last_warning_summary=_summarize_error(warning),
        last_chip_error=chip_warning,
        last_chip_error_summary=_summarize_error(chip_warning),
        last_data_as_of=last_data_as_of,
        batch_id=lineage["batch_id"],
        lineage=lineage,
        coverage_report_path=lineage.get("coverage_report_path"),
        data_coverage_pct=status.get("data_coverage_pct"),
    )
    if coverage_warning and not warning:
        status["last_warning"] = coverage_warning
        status["last_warning_summary"] = _summarize_error(coverage_warning)
    save_update_status(status)
    _refresh_daily_check_safely()
    return get_data_status()
