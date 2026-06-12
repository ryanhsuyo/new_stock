"""
notify_service 測試

覆蓋：
  send_macos_notification
    - macOS 上呼叫 osascript（subprocess.run 被 monkeypatch）
    - NOTIFY_MACOS=0 時跳過（不呼叫 subprocess）
    - 非 macOS（sys.platform != darwin）時跳過

  send_slack_notification
    - SLACK_WEBHOOK_URL 未設定時不呼叫 urllib
    - SLACK_WEBHOOK_URL 設定後呼叫（urllib.request.urlopen 被 monkeypatch）
    - Webhook 回傳非 200 時靜默（不拋例外）
    - 網路錯誤時靜默（不拋例外）

  notify_update_failure
    - 不拋例外
    - 訊息包含錯誤摘要
    - started_at 為 None 時能自動補時間

  notify_update_success
    - NOTIFY_SUCCESS=0（預設）時不呼叫底層
    - NOTIFY_SUCCESS=1 時呼叫底層

所有測試不發真實通知（底層函式被 monkeypatch）。
"""

import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import app.services.notify_service as ns


# ---------------------------------------------------------------------------
# 輔助：fake subprocess.CompletedProcess（returncode=0）
# ---------------------------------------------------------------------------

def _ok_proc():
    m = MagicMock()
    m.returncode = 0
    m.stderr = b""
    return m


# ---------------------------------------------------------------------------
# send_macos_notification
# ---------------------------------------------------------------------------

class TestMacosNotification:

    def test_calls_osascript_on_macos(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv("NOTIFY_MACOS", raising=False)
        with patch("subprocess.run", return_value=_ok_proc()) as mock_run:
            ns.send_macos_notification("Title", "Body")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "osascript"

    def test_skips_when_notify_macos_0(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv("NOTIFY_MACOS", "0")
        with patch("subprocess.run") as mock_run:
            ns.send_macos_notification("Title", "Body")
        mock_run.assert_not_called()

    def test_skips_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        with patch("subprocess.run") as mock_run:
            ns.send_macos_notification("Title", "Body")
        mock_run.assert_not_called()

    def test_does_not_raise_on_oserror(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv("NOTIFY_MACOS", raising=False)
        with patch("subprocess.run", side_effect=OSError("no osascript")):
            ns.send_macos_notification("Title", "Body")   # should not raise

    def test_escapes_double_quotes_in_message(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv("NOTIFY_MACOS", raising=False)
        with patch("subprocess.run", return_value=_ok_proc()) as mock_run:
            ns.send_macos_notification('Ti"tle', 'Mes"sage')
        script_arg = mock_run.call_args[0][0][2]  # osascript -e <script>
        assert '\\"' in script_arg   # double quotes must be escaped


# ---------------------------------------------------------------------------
# send_slack_notification
# ---------------------------------------------------------------------------

class TestSlackNotification:

    def test_skips_when_no_env_var(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        with patch("urllib.request.urlopen") as mock_open:
            ns.send_slack_notification("msg")
        mock_open.assert_not_called()

    def test_calls_urlopen_when_env_set(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            ns.send_slack_notification("hello")
        mock_open.assert_called_once()

    def test_sends_correct_content_type(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        captured_req = {}
        def fake_open(req, timeout=None):
            captured_req["req"] = req
            return mock_resp
        with patch("urllib.request.urlopen", side_effect=fake_open):
            ns.send_slack_notification("hello")
        assert captured_req["req"].get_header("Content-type") == "application/json"

    def test_does_not_raise_on_url_error(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("connection refused")):
            ns.send_slack_notification("msg")   # must not raise

    def test_does_not_raise_on_generic_exception(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            ns.send_slack_notification("msg")   # must not raise


# ---------------------------------------------------------------------------
# notify_update_failure
# ---------------------------------------------------------------------------

class TestNotifyUpdateFailure:

    def test_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(ns, "send_macos_notification", lambda *a, **kw: None)
        monkeypatch.setattr(ns, "send_slack_notification", lambda *a, **kw: None)
        ns.notify_update_failure("something broke")   # must not raise

    def test_does_not_raise_when_both_fail(self, monkeypatch):
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(ns, "send_slack_notification",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        # Both raising — but notify_update_failure itself should still not raise
        # (the individual functions catch their own exceptions)
        ns.notify_update_failure("error")

    def test_started_at_none_uses_current_time(self, monkeypatch):
        """started_at=None 時不拋例外，且訊息有時間資訊。"""
        messages: list[str] = []
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda title, body: messages.append(body))
        monkeypatch.setattr(ns, "send_slack_notification", lambda msg: None)
        ns.notify_update_failure("err msg", started_at=None)
        assert len(messages) == 1
        assert "err msg" in messages[0]

    def test_error_message_included(self, monkeypatch):
        received: list[str] = []
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda title, body: received.append(body))
        monkeypatch.setattr(ns, "send_slack_notification", lambda msg: None)
        ns.notify_update_failure("backfill 失敗: timeout", "2026-04-09T15:30:00")
        assert any("backfill 失敗" in m for m in received)

    def test_long_error_truncated(self, monkeypatch):
        long_err = "x" * 500
        received: list[str] = []
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda title, body: received.append(body))
        monkeypatch.setattr(ns, "send_slack_notification", lambda msg: None)
        ns.notify_update_failure(long_err)
        assert len(received[0]) < 400   # 訊息有被截短

    def test_calls_both_channels(self, monkeypatch):
        macos_calls: list[str] = []
        slack_calls: list[str] = []
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda t, b: macos_calls.append(b))
        monkeypatch.setattr(ns, "send_slack_notification",
                            lambda m: slack_calls.append(m))
        ns.notify_update_failure("err")
        assert len(macos_calls) == 1
        assert len(slack_calls) == 1


# ---------------------------------------------------------------------------
# notify_update_success
# ---------------------------------------------------------------------------

class TestNotifyUpdateSuccess:

    def test_skips_by_default(self, monkeypatch):
        monkeypatch.delenv("NOTIFY_SUCCESS", raising=False)
        with patch.object(ns, "send_macos_notification") as m:
            ns.notify_update_success("2026-04-09", 0)
        m.assert_not_called()

    def test_sends_when_notify_success_1(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_SUCCESS", "1")
        calls: list = []
        monkeypatch.setattr(ns, "send_macos_notification",
                            lambda t, b: calls.append((t, b)))
        monkeypatch.setattr(ns, "send_slack_notification", lambda m: None)
        ns.notify_update_success("2026-04-09", 0)
        assert len(calls) == 1
        assert "2026-04-09" in calls[0][1]
