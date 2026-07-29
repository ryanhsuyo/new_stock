#!/usr/bin/env bash
# setup_schedule.sh — 在 macOS 安裝 launchd 每日排程（台股 + 美股）
#
# 用法：
#   bash backend/scripts/setup_schedule.sh
#
# 可用環境變數覆蓋預設值：
#   PYTHON_BIN=...        Python 執行路徑（預設 which python3）
#   ASSUME_YES=1          跳過互動確認（非互動安裝用）
#
# 機制（2026-07-13 起）：不再用單一時間點的 StartCalendarInterval——
# launchd 行事曆觸發「跨重開機不補跑」，機器在排程時間關機當天就永遠不更新。
# 改為 RunAtLoad + StartInterval=3600（開機時 + 每小時醒來檢查一次），由
# scripts/scheduled_update.py 判斷：過了當日目標時間且尚未成功 → 執行；
# 否則秒退。成功一次即止、失敗下個整點重試。目標時間定義在 wrapper：
#   台股 15:30（TWSE 資料 ~15:00 上架）
#   美股 08:30（美股收盤 = 台灣清晨 4-5 點）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "${SCRIPT_DIR}")"
OUT_DIR="${BACKEND_DIR}/out"

# 依賴（pandas / requests 等）本機裝在 python3.11——優先使用，避免抓到系統 python
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3)}"
WRAPPER="${SCRIPT_DIR}/scheduled_update.py"
REPORT_WRAPPER="${SCRIPT_DIR}/scheduled_strategy_report.py"

# ── 前置檢查 ──────────────────────────────────────────────────────────────

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[ERROR] 此腳本僅支援 macOS（偵測到 $(uname)）。"
    echo "        Linux 用戶請改用 cron（詳見 cron_example.txt）。"
    exit 1
fi

if [[ ! -f "${WRAPPER}" ]]; then
    echo "[ERROR] 找不到 wrapper：${WRAPPER}"
    exit 1
fi

if ! command -v "${PYTHON_BIN}" &>/dev/null; then
    echo "[ERROR] 找不到 Python：${PYTHON_BIN}"
    echo "        請設定 PYTHON_BIN 環境變數。"
    exit 1
fi

# ── 顯示設定摘要 ──────────────────────────────────────────────────────────

echo "=== 安裝 macOS launchd 排程（台股 + 美股）==="
echo ""
echo "  Python     : ${PYTHON_BIN}"
echo "  Wrapper    : ${WRAPPER}"
echo "  觸發機制   : 開機時 + 每小時檢查（錯過自動補跑、日成功一次即止）"
echo "  台股目標   : 15:30 → daily_update.py --months 1"
echo "  美股目標   : 08:30 → backfill_ohlcv_us.py --months 1"
echo "  美股報告   : 10:00 → 刷新美股後產生獨立報告"
echo "  台股報告   : 15:40 → 等 15:30 日常更新後刷新並產生獨立報告"
echo "  執行紀錄   : ${OUT_DIR}/scheduled_update_{tw,us}.log"
echo ""
if [[ "${ASSUME_YES:-0}" != "1" ]]; then
    read -r -p "確認安裝？ [y/N] " confirm
    if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
        echo "已取消。"
        exit 0
    fi
fi

mkdir -p "${OUT_DIR}"
mkdir -p "${HOME}/Library/LaunchAgents"

# ── 生成並載入兩個 agent ─────────────────────────────────────────────────

install_agent() {
    local market="$1" label="$2" launchd_log="$3"
    local plist_path="${HOME}/Library/LaunchAgents/${label}.plist"

    cat > "${plist_path}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${WRAPPER}</string>
        <string>--market</string>
        <string>${market}</string>
    </array>

    <!-- 開機/登入時檢查一次（補跑錯過的更新） -->
    <key>RunAtLoad</key>
    <true/>

    <!-- 每小時醒來檢查；wrapper 未到條件會秒退 -->
    <key>StartInterval</key>
    <integer>3600</integer>

    <!-- launchd 預設 CWD 是 /，固定在 backend 下避免相對路徑失效 -->
    <key>WorkingDirectory</key>
    <string>${BACKEND_DIR}</string>

    <!-- 專案在 ~/Desktop（TCC 保護區）：launchd 只能開啟「自己建立」的檔案
         （com.apple.macl），此 log 不可與程式自寫的 log 共用，且安裝時要先
         刪掉讓 launchd 重新建立，否則 spawn 失敗 EX_CONFIG 78。 -->
    <key>StandardOutPath</key>
    <string>${launchd_log}</string>
    <key>StandardErrorPath</key>
    <string>${launchd_log}</string>
</dict>
</plist>
PLIST

    if launchctl list 2>/dev/null | grep -q "${label}"; then
        launchctl unload "${plist_path}" 2>/dev/null || true
    fi
    rm -f "${launchd_log}"
    launchctl load "${plist_path}"
    echo "✓ ${label} 已載入（--market ${market}）"
}

install_agent "tw" "com.stockapp.daily-update" "${OUT_DIR}/update.launchd.log"
install_agent "us" "com.stockapp.us-update"    "${OUT_DIR}/us_update.launchd.log"

install_report_agent() {
    local market="$1" hour="$2" minute="$3" label="$4" launchd_log="$5"
    local plist_path="${HOME}/Library/LaunchAgents/${label}.plist"

    cat > "${plist_path}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${REPORT_WRAPPER}</string>
        <string>--market</string><string>${market}</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>StartInterval</key><integer>3600</integer>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>${hour}</integer>
        <key>Minute</key><integer>${minute}</integer>
    </dict>
    <key>WorkingDirectory</key><string>${BACKEND_DIR}</string>
    <key>StandardOutPath</key><string>${launchd_log}</string>
    <key>StandardErrorPath</key><string>${launchd_log}</string>
</dict>
</plist>
PLIST

    if launchctl list 2>/dev/null | grep -q "${label}"; then
        launchctl unload "${plist_path}" 2>/dev/null || true
    fi
    rm -f "${launchd_log}"
    launchctl load "${plist_path}"
    echo "✓ ${label} 已載入（${hour}:$(printf '%02d' "${minute}")，--market ${market}）"
}

install_report_agent "us" 10 0 "com.stockapp.us-strategy-report" "${OUT_DIR}/strategy_report_us.launchd.log"
install_report_agent "tw" 15 40 "com.stockapp.tw-strategy-report" "${OUT_DIR}/strategy_report_tw.launchd.log"

# ── 完成提示 ─────────────────────────────────────────────────────────────

echo ""
echo "排程設定完成！"
echo ""
echo "管理指令："
echo "  查看狀態  : launchctl list | grep stockapp"
echo "  立即檢查  : launchctl start com.stockapp.daily-update   # 台股"
echo "              launchctl start com.stockapp.us-update      # 美股"
echo "  決策紀錄  : tail ${OUT_DIR}/update.launchd.log           # wrapper 每小時的判斷"
echo "  執行紀錄  : tail ${OUT_DIR}/scheduled_update_tw.log      # 實際更新輸出"
echo "  台股狀態  : cat ${OUT_DIR}/update_status.json"
echo "  卸載排程  : bash ${SCRIPT_DIR}/remove_schedule.sh"
echo ""
