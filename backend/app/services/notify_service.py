"""
notify_service.py — 最小通知機制

支援：
  1. macOS 系統通知（osascript，不需額外依賴）
  2. Slack Incoming Webhook（設定 SLACK_WEBHOOK_URL 環境變數啟用）

設計原則：
  - 通知失敗不影響主流程（所有例外都靜默 log）
  - 完全 opt-in：未設定 env var 就不發通知
  - 僅使用 stdlib：subprocess, urllib, json, os

啟用方式：
  # macOS 通知（預設啟用，設 NOTIFY_MACOS=0 可停用）
  export NOTIFY_MACOS=1

  # Slack Webhook（需要 Incoming Webhook URL）
  export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ

  # 成功時也通知（預設只通知失敗）
  export NOTIFY_SUCCESS=1
"""

import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

log = logging.getLogger(__name__)

_SLACK_WEBHOOK_ENV = "SLACK_WEBHOOK_URL"
_NOTIFY_MACOS_ENV  = "NOTIFY_MACOS"    # 預設 "1"（啟用），設 "0" 停用
_NOTIFY_SUCCESS_ENV = "NOTIFY_SUCCESS"  # 預設 "0"（不通知成功）


# ---------------------------------------------------------------------------
# 底層發送函式（可個別 monkeypatch）
# ---------------------------------------------------------------------------

def send_macos_notification(title: str, message: str) -> None:
    """
    透過 osascript 發送 macOS 系統通知。
    非 macOS、NOTIFY_MACOS=0 或 osascript 失敗時靜默略過。
    """
    if sys.platform != "darwin":
        return
    if os.environ.get(_NOTIFY_MACOS_ENV, "1") == "0":
        log.debug("macOS 通知已停用（NOTIFY_MACOS=0）")
        return
    try:
        # 逸出雙引號，避免 AppleScript 注入
        safe_title   = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            log.debug("macOS 通知已發送：%s", title)
        else:
            log.warning("osascript 回傳非零：%s", result.stderr.decode(errors="replace"))
    except Exception as exc:
        log.warning("macOS 通知失敗（不影響主流程）: %s", exc)


def send_slack_notification(message: str) -> None:
    """
    透過 Slack Incoming Webhook 發送訊息。
    SLACK_WEBHOOK_URL 未設定時靜默略過。
    """
    webhook_url = os.environ.get(_SLACK_WEBHOOK_ENV, "").strip()
    if not webhook_url:
        return
    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log.debug("Slack 通知已發送")
            else:
                log.warning("Slack 回應非 200：%d", resp.status)
    except urllib.error.URLError as exc:
        log.warning("Slack 通知失敗（網路錯誤）: %s", exc)
    except Exception as exc:
        log.warning("Slack 通知失敗（不影響主流程）: %s", exc)


# ---------------------------------------------------------------------------
# 業務層通知（組裝訊息再呼叫底層）
# ---------------------------------------------------------------------------

def notify_update_failure(
    error_msg: str,
    started_at: str | None = None,
) -> None:
    """
    資料更新失敗時送出通知。
    macOS 通知與 Slack 互不影響，任一失敗不中斷另一個。
    """
    ts = (started_at or datetime.now().isoformat(timespec="seconds"))[:16]
    short_err = (error_msg or "未知錯誤")[:200]

    title      = "⚠ 股票資料更新失敗"
    macos_body = f"{ts}\n{short_err}"
    slack_body = f"*[⚠ 股票資料更新失敗]* `{ts}`\n```{short_err}```"

    for fn, arg in [
        (send_macos_notification, (title, macos_body)),
        (send_slack_notification, (slack_body,)),
    ]:
        try:
            fn(*arg)
        except Exception as exc:
            log.warning("通知發送例外（不影響主流程）: %s", exc)

    log.info("已嘗試發送失敗通知（macOS + Slack）")


def notify_update_success(
    data_as_of: str | None,
    stale_days: int | None,
) -> None:
    """
    更新成功時送出通知（需設定 NOTIFY_SUCCESS=1，預設不發）。
    """
    if os.environ.get(_NOTIFY_SUCCESS_ENV, "0") != "1":
        return

    msg = (
        f"股票資料更新成功  "
        f"資料最新日：{data_as_of or '—'}  "
        f"距今 {stale_days if stale_days is not None else '?'} 天"
    )
    for fn, arg in [
        (send_macos_notification, ("✓ 股票資料更新成功", msg)),
        (send_slack_notification, (f"*[✓ 股票資料更新成功]* {msg}",)),
    ]:
        try:
            fn(*arg)
        except Exception as exc:
            log.warning("通知發送例外（不影響主流程）: %s", exc)
