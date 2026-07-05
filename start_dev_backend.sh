#!/usr/bin/env bash
# start_dev_backend.sh — 開發用後端啟動腳本
#
# 步驟：
#   1. 資料更新（python3 scripts/update_all_data.py --months 1）
#   2. 啟動後端（uvicorn app.main:app --reload）
#
# 用法：
#   bash start_dev_backend.sh               # 更新資料後啟動
#   bash start_dev_backend.sh --skip-update # 略過更新，直接啟動（除錯用）
#   bash start_dev_backend.sh --help

set -euo pipefail

# ── 路徑設定（以腳本所在目錄為基準，不依賴執行時的 cwd）────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

# ── ANSI 顏色輔助 ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${RESET}"; }

# ── 參數解析 ─────────────────────────────────────────────────────────────────
SKIP_UPDATE=false

for arg in "$@"; do
  case "$arg" in
    --skip-update)
      SKIP_UPDATE=true
      ;;
    -h|--help)
      echo "用法：bash start_dev_backend.sh [選項]"
      echo ""
      echo "選項："
      echo "  --skip-update   略過資料更新，直接啟動 uvicorn（開發除錯用）"
      echo "  -h, --help      顯示此說明"
      exit 0
      ;;
    *)
      error "未知參數：$arg"
      error "使用 --help 查看說明"
      exit 1
      ;;
  esac
done

# ── 前置環境檢查 ──────────────────────────────────────────────────────────────
header "=== 台灣股票分析系統 — 開發後端啟動 ==="

if [ ! -d "$BACKEND_DIR" ]; then
  error "找不到 backend/ 目錄"
  error "期望路徑：$BACKEND_DIR"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  error "找不到 python3，請確認已安裝 Python 3.10+"
  exit 1
fi

# uvicorn 可能安裝在 venv 或以 pip --user 安裝；先用直接指令，找不到改用 module 模式
if command -v uvicorn &>/dev/null; then
  UVICORN_CMD="uvicorn"
else
  # 確認 module 模式可用
  if python3 -m uvicorn --version &>/dev/null 2>&1; then
    UVICORN_CMD="python3 -m uvicorn"
  else
    error "找不到 uvicorn"
    error "請執行：pip install uvicorn  （或在 venv 內安裝）"
    exit 1
  fi
fi

# ── 進入 backend/ ─────────────────────────────────────────────────────────────
cd "$BACKEND_DIR"
info "工作目錄：$BACKEND_DIR"

# ── Step 1：資料更新 ──────────────────────────────────────────────────────────
header "── Step 1 / 2：資料更新"

if [ "$SKIP_UPDATE" = true ]; then
  warn "已略過資料更新（--skip-update）"
else
  info "執行 update_all_data.py --months 1 …"
  info "（TWSE 回補約需 1–2 分鐘，每支股票節流 ~1.2 秒）"
  echo ""

  if python3 scripts/update_all_data.py --months 1; then
    echo ""
    success "資料更新完成"
  else
    EXIT_CODE=$?
    echo ""
    error "資料更新失敗（exit code ${EXIT_CODE}），後端啟動中止"
    error "排查方向："
    error "  1. 確認網路可連線 TWSE（https://www.twse.com.tw）"
    error "  2. 確認 backend/data/leaders.json 存在且格式正確"
    error "  3. 查看 backend/out/update.log 取得詳細錯誤"
    error ""
    error "若要略過更新直接啟動，請加 --skip-update 參數"
    exit 1
  fi
fi

# ── Step 2：啟動後端 ──────────────────────────────────────────────────────────
header "── Step 2 / 2：啟動後端"
info "API：     http://localhost:19000"
info "Swagger： http://localhost:19000/docs"
info "（前端 proxy：localhost:5173/api → localhost:19000）"
info "按 Ctrl+C 停止"
echo ""

exec $UVICORN_CMD app.main:app --host 0.0.0.0 --port 19000 --reload
