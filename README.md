# 台灣股票分析與投資紀錄系統

React 18 (TypeScript) + FastAPI 的台灣股票分析與投資紀錄系統。  
提供技術訊號分析、持倉損益追蹤、每日資料更新與可解釋的買賣依據。

---

## 目錄

- [系統功能](#系統功能)
- [快速啟動](#快速啟動)
- [資料準備（初次）](#資料準備初次)
- [每日更新流程](#每日更新流程)
- [資料夾結構](#資料夾結構)
- [文件索引](#文件索引)

---

## 系統功能

### 前端（9 個頁面）

| 頁面 | 功能 |
|------|------|
| 訊號 Dashboard | 訊號執行狀態、資料檔案健康度、推薦股票概覽 |
| 推薦清單 | BUY 訊號股票列表，支援一鍵記錄買入 |
| 候選股篩選報告 | universe_report 的可行動候選、進出場區間、停損與復盤狀態 |
| 技術分析 | 個股 K 線圖（含 MA5/20/60、支撐壓力線、趨勢線）+ 訊號說明 |
| 觀察清單 | 群組管理與手動追蹤股票 |
| 投組總覽 | 持股摘要、訊號分佈、資料新鮮度、持倉表格（可排序 + 點擊跳轉分析） |
| 持倉損益 | 持倉列表 + 每檔持股技術訊號分析卡 |
| 交易紀錄 | 歷史買賣明細 |
| 統計 | 月結 / 全期報酬率、勝率、已實現損益 |

### 後端

- 7 狀態訊號系統：`entry_confirmed` / `ready_to_enter` / `watchlist` / `hold` / `take_profit_warning` / `exit_warning` / `invalidated`
- 技術分析：MA5/20/60、RSI14、支撐壓力線（靜態區間高低 + 動態均線）、趨勢線
- 型態辨識：W 底、M 頂（`forming` / `confirmed` / `failed`）
- 每股附帶 `reasons`（訊號依據）與 `risk_notes`（風險提示）
- 持股分析：均價 / 未實現損益 / 報酬率 / 訊號緊急度排序
- 資料更新狀態追蹤（running / success / failed）與 stale 警示

---

## 快速啟動

### 需求

- Python 3.10+
- Node.js 18+

### 後端

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 19000 --reload
# API：http://localhost:19000
# Swagger：http://localhost:19000/docs
```

#### 一鍵啟動（含資料更新）

```bash
# 在專案根目錄執行（首次需賦予執行權限）
chmod +x start_dev_backend.sh

# 更新資料後啟動後端（正常開發流程）
bash start_dev_backend.sh

# 略過資料更新，直接啟動（僅除錯 / 無網路時使用）
bash start_dev_backend.sh --skip-update
```

### 前端

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### 同時啟動前後端

```bash
pnpm dev:all
```

預設會啟動：

- 後端：`http://127.0.0.1:19000`
- 前端：`http://127.0.0.1:5173`

---

## 資料準備（初次）

### 1. 設定股票清單

確認 `backend/data/leaders.json` 已有要追蹤的股票代碼：

```json
["2330", "2317", "2454", "2308", "2881"]
```

### 2. 建立 12 個月資料與報表

```bash
cd backend
python3 scripts/daily_update.py --months 12
```

> `daily_update.py` 會回補 OHLCV、同步輔助資料、匯入基本面、重算訊號並刷新 Daily Check。`backfill_ohlcv_twse.py` 僅保留給 OHLCV 單獨除錯。

輸出至 `backend/out/`：

| 檔案 | 說明 |
|------|------|
| `summary.json` | 統計：通過股數、訊號分佈、不買原因計數、兩策略推薦桶（`recommendation_buckets`） |
| `universe_report.csv` | 全股票明細：訊號、分數、不買原因 |
| `daily_brief.json` | 每日晨報摘要 |
| `today_scan.json` | 今日規則掃描分桶（可小試 / 老王觀察 / 穩健動能 / 風險處理） |
| `daily_check.json` | 每日健康檢查（overall_status / blockers） |
| `signal_alerts.json` | 跨日訊號變化警示 |

---

## 每日更新流程

使用統一更新入口一次完成「回補 + 重算訊號 + 寫入狀態 + 更新 Daily Check」：

```bash
cd backend
python3 scripts/daily_update.py --months 1      # 每日用
python3 scripts/daily_update.py --months 12     # 初次建資料 / 大範圍修復
```

更完整的日常操作步驟請看 `backend/docs/daily_runbook.md`。

### 健康檢查

每天開盤後或盤後使用前，可先看 Dashboard 的 PM Daily Check；若要在終端單獨刷新或排錯，可跑：

```bash
cd backend
python3 scripts/daily_check.py
python3 scripts/daily_check.py --write-report
python3 scripts/doctor.py
python3 scripts/doctor.py --json   # 給自動化或 AI agent 讀取
```

`daily_update.py`、`run_signals.py` 與前端「立即更新資料」完成後會自動刷新 `backend/out/daily_check.json`。`daily_check.py` 可手動顯示資料日、交易輸出是否可用與 Top N 待辦；加 `--write-report` 可單獨重寫 Dashboard 讀取的快照。exit code：`0` 代表 OK、`1` 代表有警告但可回顧、`2` 代表有阻塞需先處理。
基本面避雷補資料會同時檢查 priority CSV 狀態；若 CSV 已可合併會提示合併與重算訊號，若有格式錯誤會列出第一筆問題並回傳阻塞。推薦策略固定只有老王 `old_wang` 與穩健動能 `steady_momentum`；基本面只作為穩健動能的避雷資料輔助。

基本面避雷補資料的終端流程：

```bash
cd backend
python3 scripts/prepare_fundamentals_priority_import.py --write-template
# 依 backend/out/fundamentals_priority_import_template.csv 整理真實外部資料後先 dry-run
python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv
# dry-run 確認後才寫入 backend/out/fundamentals_priority_fill.csv
python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply
# 先預覽合併
python3 scripts/merge_priority_fundamentals.py
# 預覽確認可合併後再正式寫回
python3 scripts/merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS
python3 scripts/run_signals.py
```

候選股可行動清單若需要盤後完整復盤草稿：

```bash
cd backend
python3 scripts/export_universe_review_todo.py
```

會輸出 `backend/out/universe_report_review_todo.md`，不會自動建立日誌或改交易紀錄。

### 自動排程（macOS launchd）

```bash
cd backend/scripts
./setup_schedule.sh    # 設定每日 15:30 自動執行
./remove_schedule.sh   # 移除排程
```

詳細排程說明見 `backend/scripts/cron_example.txt`。

---

## 資料夾結構

```
new_stock/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 應用進入點
│   │   ├── routers/             # HTTP 路由（不做計算）
│   │   ├── services/            # 商業邏輯（訊號、分析、持倉）
│   │   ├── storage/             # 資料存取（CSV / JSON）
│   │   └── models/              # Pydantic 資料模型
│   ├── data/
│   │   ├── leaders.json         # 追蹤股票代碼清單
│   │   ├── ohlcv.csv            # 歷史日線（backfill 產生）
│   │   ├── trades.json          # 交易紀錄
│   │   └── positions.json       # 持倉快照（可選）
│   ├── out/                     # 訊號輸出（daily_update / run_signals 產生）
│   ├── scripts/
│   │   ├── daily_update.py      # 日常統一更新入口
│   │   ├── backfill_ohlcv_twse.py # 僅除錯 OHLCV 回補
│   │   ├── run_signals.py       # 僅重算訊號
│   │   └── update_all_data.py   # 底層相容入口
│   ├── tests/                   # pytest 測試
│   ├── docs/
│   │   ├── signal_rules.md      # 技術分析規則規範
│   │   ├── architecture.md      # 系統分層架構說明
│   │   ├── api.md               # API 端點總覽
│   │   ├── operations.md        # 運維操作手冊
│   │   └── phases.md            # 開發階段記錄
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/               # 9 個頁面元件
│       ├── components/          # 可重用元件（StockChart、AnalysisPanel 等）
│       ├── api/client.ts        # API 客戶端
│       └── types/index.ts       # TypeScript 型別定義
├── README.md
└── CLAUDE.md                    # AI 協作規範
```

---

## 文件索引

| 文件 | 說明 |
|------|------|
| `backend/docs/signal_rules.md` | 技術分析核心規則、訊號定義、輸出欄位規格 |
| `backend/docs/architecture.md` | 分層架構（router / service / storage / model）說明 |
| `backend/docs/api.md` | 所有 API 端點、請求 / 回應格式 |
| `backend/docs/daily_runbook.md` | 每日實際操作流程：啟動、更新、阻塞處理、健康檢查 |
| `backend/docs/operations.md` | 資料更新、stale 檢查、狀態查看、錯誤排查 |
| `backend/docs/phases.md` | Phase 1–10 完成項目與已知限制 |
| `AGENTS.md` | AI 代理協作規範（修改範圍、分層規則、禁止事項） |
