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
import subprocess
import threading
from datetime import date, datetime
from pathlib import Path

from app.services.fundamental_service import _load_leader_codes
from app.services.signals_service import OHLCV_PATH, get_summary, run_daily_signals
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


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _run_backfill(months: int) -> tuple[bool, str]:
    """
    以 subprocess 執行 backfill_ohlcv_twse.py。
    回傳 (成功, 輸出文字)。

    此函式為模組層級，測試時可直接 monkeypatch。
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_BACKFILL_SCRIPT),
            "--months",
            str(months),
            "--include-current-month",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    return result.returncode == 0, output.strip()


def _run_chips_update() -> tuple[bool, str]:
    """以 subprocess 執行 update_chips.py。"""
    result = subprocess.run(
        [sys.executable, str(_CHIPS_SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr
    return result.returncode == 0, output.strip()


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


def _write_daily_check_report() -> None:
    """背景更新結束後刷新 daily_check.json；失敗時由呼叫端記錄但不影響更新結果。"""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    from daily_check import build_daily_summary, write_daily_summary
    from doctor import build_doctor_report

    report = build_doctor_report(_BACKEND)
    summary = build_daily_summary(report, limit=3)
    write_daily_summary(summary, _BACKEND)


def _refresh_daily_check_safely() -> None:
    try:
        _write_daily_check_report()
    except Exception:
        # Daily Check 是 Dashboard 快照，不能讓快照寫入失敗覆蓋原本資料更新結果。
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_data_status() -> dict:
    """
    讀取 update_status.json，補上 is_stale / stale_days。

    last_data_as_of 優先從狀態檔取，若無則嘗試讀 summary.json。
    """
    status = load_update_status()
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
    raw_data_warning = None
    if outputs_lag_raw_data:
        raw_data_warning = (
            f"ohlcv.csv 已更新到 {raw_ohlcv_as_of}，但交易輸出仍停在 {last_data_as_of}；"
            "請重新產生訊號與報表。"
        )
    return {
        **status,
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
    if current.get("last_run_status") == "running":
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


def run_full_update(months: int = 1) -> dict:
    """
    統一更新流程：backfill → run_signals → 寫狀態檔。

    回傳最新 data_status（含 is_stale / stale_days）。
    失敗時仍寫入狀態檔（last_run_status = "failed"，附 last_error）。
    """
    started_at = datetime.now().isoformat(timespec="seconds")
    status: dict = {
        "last_run_started_at": started_at,
        "last_run_finished_at": None,
        "last_run_status": "running",
        "last_error": None,
        "last_data_as_of": None,
    }
    save_update_status(status)

    # ── Step 1: backfill ──
    try:
        ok, output = _run_backfill(months)
        if not ok:
            raise RuntimeError(f"backfill 失敗:\n{output}")
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        err_str = str(exc)[:2000]
        status.update(
            last_run_finished_at=finished_at,
            last_run_status="failed",
            last_error=err_str,
            last_error_summary=_summarize_error(err_str),
        )
        save_update_status(status)
        _refresh_daily_check_safely()
        return get_data_status()

    # ── Step 2: update chips ──
    # 籌碼是輔助資料；若外部來源暫時失敗，保留舊 chips.json 並繼續跑日線訊號。
    chip_warning: str | None = None
    try:
        ok, output = _run_chips_update()
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
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        err_str = f"fundamentals 匯入失敗: {exc}"[:2000]
        status.update(
            last_run_finished_at=finished_at,
            last_run_status="failed",
            last_error=err_str,
            last_error_summary=_summarize_error(err_str),
        )
        save_update_status(status)
        _refresh_daily_check_safely()
        return get_data_status()

    # ── Step 4: run signals ──
    try:
        result = run_daily_signals()
        last_data_as_of: str | None = result.get("as_of")
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        err_str = f"signals 失敗: {exc}"[:2000]
        status.update(
            last_run_finished_at=finished_at,
            last_run_status="failed",
            last_error=err_str,
            last_error_summary=_summarize_error(err_str),
        )
        save_update_status(status)
        _refresh_daily_check_safely()
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
    )
    save_update_status(status)
    _refresh_daily_check_safely()
    return get_data_status()
