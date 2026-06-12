# 系統架構說明

本文件說明後端的分層設計、各層職責、模組依賴關係與關鍵檔案。

---

## 分層原則

```
HTTP 請求
    ↓
routers/        ← 只做路由、參數解析、response_model、錯誤碼
    ↓
services/       ← 商業邏輯（訊號、技術分析、推薦、統計、持倉計算）
    ↓
storage/        ← 資料存取（讀寫 CSV / JSON）
    ↓
data/ & out/    ← 實際資料檔案
```

**Router 輕、Service 厚、Storage 專職 I/O。**

- Router **不做**計算、不讀寫檔案、不打外部 API
- Service **不直接**讀寫 CSV/JSON，透過 storage 或直接操作 pandas DataFrame（由 backfill 讀入後傳入）
- Storage **只做** I/O，不含任何商業判斷

---

## 目錄結構

```
backend/app/
├── main.py              # FastAPI 進入點，掛載所有 router
├── routers/
│   ├── stocks.py        # /api/stocks/* 路由
│   ├── trades.py        # /api/trades/* 路由
│   ├── portfolio.py     # /api/portfolio/* 路由
│   ├── stats.py         # /api/stats 路由
│   └── system.py        # /api/system/* 路由
├── services/
│   ├── signals_service.py    # 核心：每日訊號計算
│   ├── analysis_service.py   # 單股深度技術分析
│   ├── holdings_service.py   # 持倉分析（持倉 + 技術訊號合併）
│   ├── pattern_service.py    # 型態辨識（W底、M頂）
│   ├── stock_service.py      # 推薦清單組裝
│   ├── trade_service.py      # 交易紀錄商業邏輯
│   ├── update_service.py     # 統一更新流程（backfill + signals）
│   └── notify_service.py     # 更新完成 / 失敗通知（stub）
├── storage/
│   ├── json_store.py         # trades.json、positions.json 讀寫
│   └── update_store.py       # update_status.json 讀寫
└── models/
    ├── analysis.py           # StockAnalysis、HoldingAnalysis、PatternResult 等
    ├── trade.py              # TradeRecord、Position、BuyRequest、SellRequest、Stats
    ├── stock.py              # StockRecommendation
    └── system.py             # DataStatus
```

---

## 各層職責說明

### `routers/`

| 檔案 | 前綴 | 主要端點 |
|------|------|----------|
| `stocks.py` | `/api/stocks` | 推薦清單、個股分析、訊號狀態、觸發訊號計算 |
| `trades.py` | `/api/trades` | 列出交易、記錄買入、記錄賣出 |
| `portfolio.py` | `/api/portfolio` | 持倉列表、持倉 + 分析合併、投組摘要 |
| `stats.py` | `/api/stats` | 月結 / 全期統計 |
| `system.py` | `/api/system` | 資料更新狀態查詢 |

每個 router 只負責：
1. 定義路由與 HTTP 方法
2. 解析路徑 / 查詢參數
3. 呼叫對應 service
4. 回傳 `response_model`，設定錯誤碼

### `services/`

#### `signals_service.py` — 核心訊號引擎

- 讀取 `backend/data/ohlcv.csv` 與 `backend/data/leaders.json`
- 對每檔股票計算：MA5 / MA20 / MA60、RSI14、成交量比、長短線趨勢
- 依支撐壓力位、趨勢、型態產生 7 狀態訊號
- 輸出 `backend/out/summary.json` 與 `backend/out/universe_report.csv`
- 最少需要 60 根 K 棒才計算（`DATA_MISSING` 若資料不足）

**訊號狀態（7 狀態）：**

| 狀態 | 說明 | 前端顯示 |
|------|------|----------|
| `entry_confirmed` | 突破確認，進場 | 進場確認 |
| `ready_to_enter` | 條件接近，準備 | 準備進場 |
| `watchlist` | 觀察中，條件未成熟 | 觀察中 |
| `hold` | 持股續抱 | 持股續抱 |
| `take_profit_warning` | 偏離均線過遠，停利注意 | 注意停利 |
| `exit_warning` | 跌破支撐或趨勢轉弱 | 出場警示 |
| `invalidated` | 多頭條件失效 | 多頭失效 |
| `DATA_MISSING` | 資料不足（< 60 根） | 資料不足 |

#### `analysis_service.py` — 單股深度分析

- 輸入：股票代碼 + 基準日（`as_of_date`）
- 輸出：`StockAnalysis`，包含：
  - OHLCV 最近 120 根（供前端 K 線圖）
  - 支撐壓力線：近 20/60 日靜態高低點 + MA20/MA60 動態線
  - 趨勢線：連接擺動高低點（5 Bar 窗口）
  - 完整 `reasons`、`risk_notes`、`no_buy_reason`
  - `PatternResult`（W 底 / M 頂）

#### `holdings_service.py` — 持倉分析

- 從 `trades.json` 計算各股持倉（加權平均成本）
- 對每檔持倉呼叫 `analysis_service`，合併損益資料
- 依訊號緊急度排序：`exit_warning` 排最前，`DATA_MISSING` 排最後

#### `pattern_service.py` — 型態辨識

- W 底：找兩個相近（差異 ≤ 5%）的擺動低點，頸線需比低點高 ≥ 3%
- M 頂：找兩個相近（差異 ≤ 5%）的擺動高點，頸線需比高點低 ≥ 3%
- 每個型態有三種狀態：`forming`（形成中）/ `confirmed`（確認）/ `failed`（失效）

#### `update_service.py` — 統一更新流程

1. 呼叫 `backfill_ohlcv_twse` 補資料
2. 呼叫 `run_daily_signals` 重算訊號
3. 將執行結果（started_at、finished_at、status、error）寫入 `update_status.json`

### `storage/`

| 檔案 | 負責 |
|------|------|
| `json_store.py` | 讀寫 `trades.json`（交易紀錄） |
| `update_store.py` | 讀寫 `update_status.json`（更新狀態） |

> `ohlcv.csv` 由 `backfill_ohlcv_twse.py` 直接以 pandas 管理，透過 `signals_service` 載入。

### `models/`

| 檔案 | 主要 Model |
|------|------------|
| `analysis.py` | `StockAnalysis`、`HoldingAnalysis`、`PortfolioSummary`、`PatternResult`、`OhlcvBar`、`SupportResistanceLine`、`TrendLine` |
| `trade.py` | `TradeRecord`、`Position`、`BuyRequest`、`SellRequest`、`Stats` |
| `stock.py` | `StockRecommendation` |
| `system.py` | `DataStatus` |

---

## 資料流

### 訊號計算流

```
leaders.json ─┐
ohlcv.csv  ───┴─→ signals_service → summary.json
                                   → universe_report.csv
                                   → buy_list.json / sell_list.json / hold_list.json
```

### 前端讀取流

```
GET /api/stocks/recommendations
  → stock_service → 讀 summary.json → StockRecommendation[]

GET /api/stocks/{code}/analysis
  → analysis_service → 讀 ohlcv.csv → StockAnalysis

GET /api/portfolio/analysis
  → holdings_service → trades.json + analysis_service → HoldingAnalysis[]

GET /api/system/data-status
  → update_store → update_status.json → DataStatus
```

### 交易記錄流

```
POST /api/trades/buy
  → trade_service → json_store → trades.json（append）

POST /api/trades/sell
  → trade_service → 驗證持股 → json_store → trades.json（append）
```

---

## 前端架構（概覽）

前端為 React 18 + TypeScript SPA，使用 Tab 導航（非 React Router）。

```
App.tsx
  ├─ state: tab (當前頁面) + analysisCode (跨頁跳轉)
  ├─ navigateToAnalysis(code) → 設定 tab='analysis' + analysisCode=code
  └─ 7 個 Page 元件（條件渲染）

components/
  ├─ StockChart.tsx      K線圖（lightweight-charts，含 MA/支撐壓力/趨勢線）
  ├─ AnalysisPanel.tsx   訊號分析面板（訊號 Badge、指標、reasons、risk_notes）
  ├─ PortfolioTable.tsx  持倉表格（含賣出按鈕）
  ├─ BuyModal.tsx        買入交易彈窗
  ├─ SellModal.tsx       賣出交易彈窗
  ├─ StatsPanel.tsx      統計面板
  └─ TradeTable.tsx      交易記錄表格
```

---

## 設計原則與限制

- **不使用資料庫**：交易紀錄與更新狀態均以 JSON 檔案儲存
- **不引入 Celery / Redis**：更新流程為同步執行，透過 PID 檔防止重複執行
- **不依賴外部推播**：`notify_service` 為 stub，可日後接入 LINE Notify 等
- **CORS 固定開放 `localhost:5173`**：生產環境需修改 `main.py`
