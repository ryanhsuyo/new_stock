#!/usr/bin/env bash
# setup_schedule.sh — 在 macOS 安裝 launchd 每日排程
#
# 用法：
#   bash backend/scripts/setup_schedule.sh
#
# 可用環境變數覆蓋預設值：
#   SCHEDULE_HOUR=15      排程小時（24h，預設 15）
#   SCHEDULE_MINUTE=30    排程分鐘（預設 30）
#   MONTHS=1              回補月數（預設 1）
#   PYTHON_BIN=...        Python 執行路徑（預設 which python3）
#
# 台灣股市收盤 13:30，TWSE API 通常 15:00 前更新完成。
# 預設排程 15:30 是讓資料有足夠時間上架後再抓。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "${SCRIPT_DIR}")"
OUT_DIR="${BACKEND_DIR}/out"

# 可覆蓋的設定
PYTHON_BIN="${PYTHON_BIN:-$(which python3)}"
SCHEDULE_HOUR="${SCHEDULE_HOUR:-15}"
SCHEDULE_MINUTE="${SCHEDULE_MINUTE:-30}"
MONTHS="${MONTHS:-1}"

PLIST_LABEL="com.stockapp.daily-update"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
UPDATE_SCRIPT="${SCRIPT_DIR}/daily_update.py"
LOG_FILE="${OUT_DIR}/update.log"

# ── 前置檢查 ──────────────────────────────────────────────────────────────

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[ERROR] 此腳本僅支援 macOS（偵測到 $(uname)）。"
    echo "        Linux 用戶請改用 cron（詳見 cron_example.txt）。"
    exit 1
fi

if [[ ! -f "${UPDATE_SCRIPT}" ]]; then
    echo "[ERROR] 找不到更新腳本：${UPDATE_SCRIPT}"
    exit 1
fi

if ! command -v "${PYTHON_BIN}" &>/dev/null; then
    echo "[ERROR] 找不到 Python：${PYTHON_BIN}"
    echo "        請設定 PYTHON_BIN 環境變數，例如："
    echo "        PYTHON_BIN=/usr/local/bin/python3 bash setup_schedule.sh"
    exit 1
fi

# ── 顯示設定摘要 ──────────────────────────────────────────────────────────

echo "=== 安裝 macOS launchd 排程 ==="
echo ""
echo "  Python       : ${PYTHON_BIN}"
echo "  更新腳本     : ${UPDATE_SCRIPT}"
echo "  Log 檔       : ${LOG_FILE}"
echo "  狀態檔       : ${OUT_DIR}/update_status.json"
echo "  排程時間     : 每日 ${SCHEDULE_HOUR}:$(printf '%02d' "${SCHEDULE_MINUTE}")"
echo "  回補月數     : ${MONTHS}"
echo "  plist 路徑   : ${PLIST_PATH}"
echo ""
read -r -p "確認安裝？ [y/N] " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "已取消。"
    exit 0
fi

# ── 建立輸出目錄 ─────────────────────────────────────────────────────────

mkdir -p "${OUT_DIR}"
mkdir -p "${HOME}/Library/LaunchAgents"

# ── 生成 plist ───────────────────────────────────────────────────────────

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${UPDATE_SCRIPT}</string>
        <string>--months</string>
        <string>${MONTHS}</string>
        <string>--log-file</string>
        <string>${LOG_FILE}</string>
    </array>

    <!-- 每日固定時間執行 -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${SCHEDULE_HOUR}</integer>
        <key>Minute</key>
        <integer>${SCHEDULE_MINUTE}</integer>
    </dict>

    <!-- launchd stdout/stderr 同步導向 log 檔 -->
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>

    <!-- 載入時不立即執行 -->
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

echo ""
echo "✓ plist 已生成：${PLIST_PATH}"

# ── 載入排程 ─────────────────────────────────────────────────────────────

# 若已存在，先卸載
if launchctl list 2>/dev/null | grep -q "${PLIST_LABEL}"; then
    launchctl unload "${PLIST_PATH}" 2>/dev/null || true
    echo "  (已卸載舊排程)"
fi

launchctl load "${PLIST_PATH}"
echo "✓ launchd 排程已載入"

# ── 完成提示 ─────────────────────────────────────────────────────────────

echo ""
echo "排程設定完成！"
echo ""
echo "管理指令："
echo "  查看狀態  : launchctl list | grep stockapp"
echo "  立即執行  : launchctl start ${PLIST_LABEL}"
echo "  查看 log  : tail -f ${LOG_FILE}"
echo "  查看狀態  : cat ${OUT_DIR}/update_status.json"
echo "  卸載排程  : bash ${SCRIPT_DIR}/remove_schedule.sh"
echo ""
