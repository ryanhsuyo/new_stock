#!/usr/bin/env bash
# remove_schedule.sh — 卸載 macOS launchd 排程（台股 + 美股）

set -euo pipefail

echo "=== 卸載 launchd 排程 ==="

for label in \
    com.stockapp.daily-update \
    com.stockapp.us-update \
    com.stockapp.us-strategy-report \
    com.stockapp.tw-strategy-report; do
    plist_path="${HOME}/Library/LaunchAgents/${label}.plist"
    if [[ ! -f "${plist_path}" ]]; then
        echo "（${label} 未安裝，略過）"
        continue
    fi
    launchctl unload "${plist_path}" 2>/dev/null || true
    rm -f "${plist_path}"
    echo "✓ 已卸載：${label}"
done
