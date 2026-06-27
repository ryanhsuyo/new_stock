"""
排程相關測試

覆蓋：
  acquire_lock / release_lock
    - 正常取得與釋放
    - PID 檔不存在 → 取得成功
    - PID 檔含已結束 PID → 覆寫並取得成功
    - PID 檔含執行中 PID（當前 process） → 偵測並拒絕
    - 釋放後 PID 檔消失

  setup_logging
    - 指定 log_file 後，log 檔案被建立
    - 傳 None 時不建立 log 檔

  run_update_job（核心邏輯，不走真實網路）
    - 成功路徑：回傳 0，狀態檔寫入 success
    - 失敗路徑：回傳 1，狀態檔寫入 failed
    - skip_lock=True：不建立 PID 檔
    - 執行後 PID 檔被清理（release_lock）

  CLI --help 可正常執行（驗證 argparse 設定正確）
"""

import logging
import os
import subprocess
import sys
import json
from datetime import date
from pathlib import Path

import pytest

# ── scripts/ 目錄加入 sys.path，讓測試可 import update_all_data ──────────
_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import update_all_data as uda  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_pid(tmp_path, monkeypatch):
    """把 _PID_FILE 導向 tmp 目錄。"""
    pid_path = tmp_path / "update.pid"
    monkeypatch.setattr(uda, "_PID_FILE", pid_path)
    return pid_path


@pytest.fixture()
def tmp_log(tmp_path):
    return tmp_path / "update.log"


@pytest.fixture()
def tmp_sched(tmp_out, tmp_pid, monkeypatch):
    """
    組合 fixture：
      - tmp_out: signals_service._OUT / update_store 指向 tmp
      - tmp_pid: _PID_FILE 指向 tmp
      - _run_backfill stub（無網路）
      - notify stubs（不送真實通知）
    """
    import app.storage.update_store as store
    import app.services.update_service as svc
    import app.services.notify_service as notify

    status_path = tmp_out / "update_status.json"
    monkeypatch.setattr(store, "_OUT", tmp_out)
    monkeypatch.setattr(store, "UPDATE_STATUS_PATH", status_path)
    monkeypatch.setattr(svc, "_run_backfill", lambda months: (True, "stub OK"))

    def fake_run_daily_signals():
        as_of = date.today().isoformat()
        (tmp_out / "summary.json").write_text(
            json.dumps({"as_of": as_of, "signals": [], "files_written": ["summary.json", "universe_report.csv", "daily_brief.json"]}),
            encoding="utf-8",
        )
        (tmp_out / "universe_report.csv").write_text("code,name,data_ok,no_buy_reason\n", encoding="utf-8")
        (tmp_out / "daily_brief.json").write_text(
            json.dumps({"as_of": as_of, "data_status": {"last_data_as_of": as_of}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"as_of": as_of}

    monkeypatch.setattr(svc, "run_daily_signals", fake_run_daily_signals)

    # 停用通知，避免測試時彈出 macOS 通知
    monkeypatch.setattr(notify, "send_macos_notification", lambda *a, **kw: None)
    monkeypatch.setattr(notify, "send_slack_notification", lambda *a, **kw: None)
    monkeypatch.setattr(uda, "notify_update_failure", lambda *a, **kw: None)
    monkeypatch.setattr(uda, "notify_update_success", lambda *a, **kw: None)

    # 同步修正 uda.run_full_update 指向（from ... import 已綁定）
    monkeypatch.setattr(uda, "run_full_update", svc.run_full_update)

    return tmp_out


# ---------------------------------------------------------------------------
# acquire_lock / release_lock
# ---------------------------------------------------------------------------

class TestLock:

    def test_acquire_when_no_pid_file(self, tmp_pid):
        assert not tmp_pid.exists()
        result = uda.acquire_lock()
        assert result is True
        assert tmp_pid.exists()
        uda.release_lock()

    def test_pid_file_contains_current_pid(self, tmp_pid):
        uda.acquire_lock()
        assert int(tmp_pid.read_text().strip()) == os.getpid()
        uda.release_lock()

    def test_release_removes_pid_file(self, tmp_pid):
        uda.acquire_lock()
        uda.release_lock()
        assert not tmp_pid.exists()

    def test_acquire_with_stale_pid(self, tmp_pid):
        """PID 檔含已結束的 PID（1 號不可能是 update 進程），應允許覆寫。"""
        # PID 9999999 幾乎不可能存在
        tmp_pid.write_text("9999999")
        result = uda.acquire_lock()
        assert result is True
        uda.release_lock()

    def test_acquire_with_corrupted_pid_file(self, tmp_pid):
        """PID 檔損毀（非數字）應視同無鎖，允許取得。"""
        tmp_pid.write_text("not-a-pid")
        result = uda.acquire_lock()
        assert result is True
        uda.release_lock()

    def test_acquire_rejects_live_pid(self, tmp_pid):
        """PID 檔含當前 PID（模擬 self），若 pid != self 才拒絕。
        此測試直接寫一個已知存在的 PID（os.getppid 父進程通常活著）。"""
        ppid = os.getppid()
        tmp_pid.write_text(str(ppid))
        # 父進程存在且 PID != os.getpid() → 應拒絕
        # （若父進程碰巧結束則 fallthrough，可接受）
        if uda._pid_is_running(ppid):
            result = uda.acquire_lock()
            assert result is False
        # else: 父進程已死，跳過此斷言

    def test_release_when_no_file_is_safe(self, tmp_pid):
        """release_lock 在 PID 檔不存在時不應拋例外。"""
        assert not tmp_pid.exists()
        uda.release_lock()   # should not raise


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:

    def test_log_file_created(self, tmp_log):
        uda.setup_logging(tmp_log)
        logging.getLogger("test_create").info("hello")
        assert tmp_log.exists()

    def test_log_file_none_does_not_create_file(self, tmp_path):
        uda.setup_logging(None)
        # no file should appear in tmp_path from this call
        assert list(tmp_path.iterdir()) == []

    def test_log_appends(self, tmp_log):
        tmp_log.write_text("existing line\n", encoding="utf-8")
        uda.setup_logging(tmp_log)
        logging.getLogger("test_append").warning("appended")
        content = tmp_log.read_text(encoding="utf-8")
        assert "existing line" in content
        assert "appended" in content


# ---------------------------------------------------------------------------
# run_update_job（核心邏輯，monkeypatched）
# ---------------------------------------------------------------------------

class TestRunUpdateJob:

    def test_success_returns_0(self, tmp_sched, tmp_log):
        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        assert code == 0

    def test_success_writes_status(self, tmp_sched, tmp_log):
        import app.storage.update_store as store
        uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        import json
        saved = json.loads(store.UPDATE_STATUS_PATH.read_text())
        assert saved["last_run_status"] == "success"

    def test_success_writes_daily_check_report(self, tmp_sched, tmp_log, monkeypatch):
        calls = []

        def fake_write_daily_check_report(backend):
            calls.append(backend)
            path = backend / "out" / "daily_check.json"
            path.write_text('{"overall_status":"ok"}', encoding="utf-8")
            return path

        monkeypatch.setattr(uda, "write_daily_check_report", fake_write_daily_check_report)

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)

        assert code == 0
        assert calls == [uda._BACKEND]
        assert (uda._BACKEND / "out" / "daily_check.json").exists()

    def test_cli_update_requests_streaming_output_when_supported(self, tmp_sched, tmp_log, monkeypatch):
        calls = []

        def fake_run_full_update(months, *, stream_subprocess_output=False):
            calls.append(stream_subprocess_output)
            return {
                "last_run_status": "success",
                "last_run_started_at": "2026-06-25T00:00:00",
                "last_data_as_of": "2026-06-24",
                "is_stale": False,
                "stale_days": 0,
                "last_error": None,
            }

        monkeypatch.setattr(uda, "run_full_update", fake_run_full_update)

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)

        assert code == 0
        assert calls == [True]

    def test_cli_update_keeps_legacy_run_full_update_compatible(self, tmp_sched, tmp_log, monkeypatch):
        calls = []

        def legacy_run_full_update(months):
            calls.append(months)
            return {
                "last_run_status": "success",
                "last_run_started_at": "2026-06-25T00:00:00",
                "last_data_as_of": "2026-06-24",
                "is_stale": False,
                "stale_days": 0,
                "last_error": None,
            }

        monkeypatch.setattr(uda, "run_full_update", legacy_run_full_update)

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)

        assert code == 0
        assert calls == [1]

    def test_daily_check_write_failure_does_not_fail_update(self, tmp_sched, tmp_log, monkeypatch):
        monkeypatch.setattr(uda, "write_daily_check_report", lambda backend: (_ for _ in ()).throw(RuntimeError("daily check broken")))

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)

        assert code == 0
        assert "Daily Check 寫入失敗" in tmp_log.read_text(encoding="utf-8")

    def test_keyboard_interrupt_returns_130_without_traceback(self, tmp_sched, tmp_pid, tmp_log, monkeypatch):
        def interrupted(months, *, stream_subprocess_output=False):
            raise KeyboardInterrupt()

        monkeypatch.setattr(uda, "run_full_update", interrupted)

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=False)

        assert code == 130
        assert not tmp_pid.exists()
        assert "使用者中斷" in tmp_log.read_text(encoding="utf-8")

    def test_failure_returns_1(self, tmp_sched, tmp_log, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "simulated error"))
        monkeypatch.setattr(uda, "run_full_update", svc.run_full_update)
        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        assert code == 1

    def test_failure_writes_failed_status(self, tmp_sched, tmp_log, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store
        import json
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "net error"))
        monkeypatch.setattr(uda, "run_full_update", svc.run_full_update)
        uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        saved = json.loads(store.UPDATE_STATUS_PATH.read_text())
        assert saved["last_run_status"] == "failed"

    def test_stale_update_returns_1_and_logs_warning(self, tmp_sched, tmp_log, monkeypatch):
        monkeypatch.setattr(uda, "run_full_update", lambda months: {
            "last_run_status": "stale",
            "last_run_started_at": "2026-05-19T15:00:00",
            "last_data_as_of": "2026-05-14",
            "is_stale": True,
            "stale_days": 5,
            "last_error": None,
            "last_warning": "更新完成但資料仍過期",
        })

        code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)

        assert code == 1
        assert "資料仍過期" in tmp_log.read_text(encoding="utf-8")

    def test_skip_lock_leaves_no_pid_file(self, tmp_sched, tmp_pid, tmp_log):
        uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        assert not tmp_pid.exists()

    def test_log_file_written_on_success(self, tmp_sched, tmp_log):
        uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        assert tmp_log.exists()
        assert "update_all_data" in tmp_log.read_text(encoding="utf-8")

    def test_log_file_written_on_failure(self, tmp_sched, tmp_log, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "fail"))
        monkeypatch.setattr(uda, "run_full_update", svc.run_full_update)
        uda.run_update_job(months=1, log_file=tmp_log, skip_lock=True)
        assert tmp_log.exists()

    def test_double_lock_returns_2(self, tmp_sched, tmp_pid, tmp_log):
        """模擬另一個 instance 佔著 PID（寫入父進程 PID）。"""
        ppid = os.getppid()
        tmp_pid.write_text(str(ppid))
        if uda._pid_is_running(ppid):
            code = uda.run_update_job(months=1, log_file=tmp_log, skip_lock=False)
            assert code == 2
        # 若父進程已死，跳過（環境限制）


# ---------------------------------------------------------------------------
# CLI --help 驗證
# ---------------------------------------------------------------------------

class TestCLI:

    def test_help_exits_0(self):
        script = str(_SCRIPTS / "update_all_data.py")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--months" in result.stdout

    def test_help_shows_log_file_option(self):
        script = str(_SCRIPTS / "update_all_data.py")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True,
        )
        assert "--log-file" in result.stdout

    def test_help_shows_no_lock_option(self):
        script = str(_SCRIPTS / "update_all_data.py")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True,
        )
        assert "--no-lock" in result.stdout

    def test_daily_update_help_exits_0(self):
        script = str(_SCRIPTS / "daily_update.py")
        result = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--months" in result.stdout

    def test_schedule_templates_use_daily_update_entrypoint(self):
        setup_script = (_SCRIPTS / "setup_schedule.sh").read_text(encoding="utf-8")
        cron_example = (_SCRIPTS / "cron_example.txt").read_text(encoding="utf-8")

        assert 'UPDATE_SCRIPT="${SCRIPT_DIR}/daily_update.py"' in setup_script
        assert "/scripts/daily_update.py --months 1" in cron_example
        assert "/scripts/update_all_data.py --months 1" not in cron_example
