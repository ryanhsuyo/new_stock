#!/usr/bin/env bash
# remove_schedule.sh — 卸載 macOS launchd 排程

set -euo pipefail

PLIST_LABEL="com.stockapp.daily-update"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

echo "=== 卸載 launchd 排程 ==="

if [[ ! -f "${PLIST_PATH}" ]]; then
    echo "plist 不存在：${PLIST_PATH}"
    echo "排程可能尚未安裝。"
    exit 0
fi

launchctl unload "${PLIST_PATH}" 2>/dev/null || true
rm -f "${PLIST_PATH}"

echo "✓ 排程已卸載：${PLIST_PATH}"
