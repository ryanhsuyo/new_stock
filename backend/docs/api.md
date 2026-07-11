# API 端點總覽

FastAPI 後端，所有端點皆以 `/api` 為前綴。  
互動文件（Swagger UI）：`http://localhost:19000/docs`

---

## 端點索引

所有實際存在的端點一覽（與 `app/routers/*` 同步；`backend/tests/test_api_docs.py` 會驗證本文件不漏列端點）。
部分端點在下方有詳細章節；未列詳細章節者以本表描述與 Swagger UI 為準。

### 訊號與推薦（stocks）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/stocks/recommendations` | 推薦清單（`old_wang` / `steady_momentum` 兩策略） |
| GET | `/api/stocks/universe` | 追蹤股票資料狀態清單（leaders.json × ohlcv.csv 交叉比對） |
| GET | `/api/stocks/{code}/analysis` | 單檔深度分析：支撐壓力線、趨勢線、訊號、reasons、risk_notes |
| GET | `/api/stocks/{code}/intraday-monitor` | 盤中監控：只檢查日線計畫是否被盤中價格破壞 |
| POST | `/api/stocks/{code}/tracking` | 把單檔加入 leaders.json 的手動追蹤群組；不觸發長時間回補 |
| GET | `/api/stocks/signals/status` | out/ 檔案存在狀態、最後更新時間、summary 的 as_of / generated_at |
| POST | `/api/stocks/signals/run` | 背景執行訊號計算，透過 status 輪詢結果 |
| GET | `/api/stocks/signals/summary` | 讀取最近一次 run 的 summary.json |
| GET | `/api/stocks/signals/daily-brief` | 讀取最近一次 run 的 daily_brief.json |
| GET | `/api/stocks/signals/universe_report` | 下載 universe_report.csv（FileResponse） |
| GET | `/api/stocks/signals/universe-report` | 讀取 universe_report.csv，以 JSON array 回傳 |
| GET | `/api/stocks/signals/manual-watchlist-review` | 人工盤後觀察股逐檔校正表 |
| GET | `/api/stocks/market-notes` | 人工盤後筆記清單（日期新到舊） |
| POST | `/api/stocks/market-notes` | 新增或覆蓋指定日期的人工盤後筆記 |

### 交易紀錄（trades）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/trades` | 交易紀錄清單 |
| POST | `/api/trades/buy` | 記錄買入（含現金驗證） |
| POST | `/api/trades/sell` | 記錄賣出（含超賣驗證） |
| POST | `/api/trades/import` | 批次匯入交易紀錄（會先備份再覆蓋） |
| POST | `/api/trades/import/validate` | 匯入前完整驗證（一次回傳所有錯誤，不寫檔） |
| POST | `/api/trades/import/preview` | 匯入前預檢（含 positions_preview，不寫檔） |
| POST | `/api/trades/clear` | 清空交易紀錄（會先備份） |
| GET | `/api/trades/backups` | 交易紀錄備份清單 |
| POST | `/api/trades/backups/restore` | 還原指定交易備份 |

### 投資組合與統計

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/portfolio` | 持倉損益（均攤成本 + 未實現損益） |
| GET | `/api/portfolio/positions` | 從 trades.json 推算目前持股（不含技術分析） |
| GET | `/api/portfolio/analysis` | 持股 + 技術訊號（依緊急度排序） |
| GET | `/api/portfolio/summary` | 投組摘要（總成本 / 估值 / 損益 / 訊號分布） |
| GET | `/api/stats` | 月結 / 全期統計（勝率 / 已實現損益） |

### 系統狀態（system）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/system/data-status` | 資料更新狀態 + stale 計算 |
| POST | `/api/system/update-now` | 手動觸發資料更新（backfill + signals；已在執行中回 409） |
| GET | `/api/system/update-workflow` | 每日更新流程狀態：目前卡在哪一步、下一個可執行動作 |
| GET | `/api/system/workflow-status` | PM 視角每日工作流狀態：能不能操作、下一步優先做什麼 |
| GET | `/api/system/daily-check` | 每日 PM 摘要（由 `scripts/daily_check.py --write-report` 產生） |
| GET | `/api/system/today-scan` | Today Scan 衍生報告；不重算策略、不寫檔 |
| GET | `/api/system/pm-worklist` | PM 工作佇列：資料修復、基本面、候選復盤與 Daily Check 優先順序 |
| GET | `/api/system/settings/trading` | 交易費率設定（供前端估算交易成本） |
| GET | `/api/system/signal-alert-reviews` | 目前 signal_alerts.json 是否已被人工檢視 |
| POST | `/api/system/signal-alert-reviews/current` | 標記目前 signal_alerts.json fingerprint 已檢視（只寫 review ledger） |
| GET | `/api/system/fundamentals-status` | 基本面避雷資料對 leaders 清單的覆蓋率 |
| GET | `/api/system/fundamentals-priority-fill` | 下載基本面避雷優先補資料 CSV |
| POST | `/api/system/fundamentals-priority-fill/merge` | 預覽或正式合併基本面優先補資料 CSV |
| GET | `/api/system/fundamentals-official/status` | 官方基本面暫存報告檔狀態；不觸發外部抓取 |
| POST | `/api/system/fundamentals-official/reports` | 觸發官方基本面暫存報告產生；report-only，不寫入策略輸入 |
| GET | `/api/system/fundamentals-official/coverage-audit` | 官方 report-only 覆蓋率稽核 |
| GET | `/api/system/fundamentals-official/quality-momentum-lite-guard` | Quality Momentum Lite guard 覆蓋率（report-only） |
| GET | `/api/system/personal-backups` | 個人資料備份清單 |
| POST | `/api/system/personal-backups` | 建立個人資料備份（不含行情與 out 產物） |
| POST | `/api/system/personal-backups/restore-preview` | Dry-run 預覽還原；不寫檔 |
| POST | `/api/system/personal-backups/restore` | 正式還原（需 `confirm=RESTORE_PERSONAL_DATA`，先備份目前狀態） |

### 觀察清單（watchlists）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/watchlists` | 所有觀察清單群組（含股票列表） |
| POST | `/api/watchlists` | 建立新群組（名稱重複回 409） |
| DELETE | `/api/watchlists/{group}` | 刪除整個群組 |
| POST | `/api/watchlists/{group}/stocks` | 加入股票（冪等，已存在則跳過） |
| DELETE | `/api/watchlists/{group}/stocks/{code}` | 移除股票（群組不存在回 404） |

### 決策日誌（decision-journal）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/decision-journal` | 讀取決策日誌（只做復盤紀錄，不改持倉 / 交易） |
| POST | `/api/decision-journal` | 新增一筆買 / 賣 / 續抱 / 觀望 / 不動的決策紀錄 |
| PUT | `/api/decision-journal/{entry_id}` | 更新單筆決策日誌（保留建立時間與 workflow snapshot） |
| DELETE | `/api/decision-journal/{entry_id}` | 刪除單筆決策日誌 |
| GET | `/api/decision-journal/summary` | 指定日期的決策日誌統計 |
| GET | `/api/decision-journal/universe-report-workflow` | 候選股報表復盤 PM 工作流摘要（唯讀） |
| POST | `/api/decision-journal/from-universe-report` | 將尚未記錄的可行動候選批次轉成決策日誌 |
| POST | `/api/decision-journal/from-portfolio-tasks` | 將尚未記錄的持股待辦批次轉成決策日誌 |

---

## 訊號與推薦

### `GET /api/stocks/recommendations`

取得目前的推薦清單（由最近一次 `run_signals` 產生）。

**查詢參數**：

- `strategy=steady_momentum`：預設，回傳穩健動能候選。
- `strategy=old_wang`：回傳老王短波段候選。
- 舊版相容參數：後端導回 `steady_momentum`，不代表獨立推薦策略。

**回應**（`StockRecommendation[]`）：

```json
[
  {
    "stock_id": "2330",
    "name": "台積電",
    "price": 850.0,
    "change_pct": 1.5,
    "score": 75,
    "reason": "長線偏多，突破頸線，量能配合",
    "risk_warning": "接近前高壓力，注意量能是否持續"
  }
]
```

---

### `GET /api/stocks/{code}/analysis`

取得指定股票的深度技術分析（即時計算，包含 K 線資料供圖表使用）。

**路徑參數**：
- `code`：股票代碼（如 `2330`）

**查詢參數**：
- `as_of`（選填）：基準日 `YYYY-MM-DD`，預設為 `ohlcv.csv` 最新日期

**回應**（`StockAnalysis`）：

```json
{
  "code": "2330",
  "stock_id": "2330",
  "name": "台積電",
  "as_of": "2026-04-11",
  "data_ok": true,
  "data_missing_reason": null,
  "is_stale": false,
  "stale_days": 3,
  "close": 850.0,
  "ma5": 845.0,
  "ma20": 820.0,
  "ma60": 790.0,
  "rsi14": 62.5,
  "vol_ratio": 1.3,
  "long_trend": "up",
  "short_trend": "up",
  "signal": "entry_confirmed",
  "score": 75,
  "reasons": ["長線偏多", "突破頸線"],
  "risk_notes": ["接近前高壓力"],
  "no_buy_reason": null,
  "support_lines": [
    { "label": "近20日低", "price": 810.0, "type": "static" },
    { "label": "MA20", "price": 820.0, "type": "dynamic" }
  ],
  "resistance_lines": [
    { "label": "近20日高", "price": 860.0, "type": "static" }
  ],
  "uptrend_line": { "valid": true, "p1": {"date": "...", "price": 780.0}, "p2": {...}, "note": "" },
  "downtrend_line": { "valid": false, "p1": null, "p2": null, "note": "" },
  "pattern": {
    "pattern_type": "w_bottom",
    "pattern_status": "confirmed",
    "neckline": 840.0,
    "note": ""
  },
  "ohlcv": [
    { "date": "2026-04-11", "open": 845.0, "high": 855.0, "low": 843.0, "close": 850.0, "volume": 25000000 }
  ]
}
```

---

### `GET /api/stocks/signals/status`

取得訊號輸出檔案的狀態（是否存在、最後修改時間、輸出基準日與背景重算狀態）。

**回應**：

```json
{
  "run_status": "idle",
  "run_error": null,
  "out_dir": "/path/to/backend/out",
  "out_files": {
    "summary_json": {
      "exists": true,
      "path": "/path/to/backend/out/summary.json",
      "last_modified": "2026-05-22T15:35:00",
      "as_of": "2026-05-22",
      "generated_at": "2026-05-22T15:35:00"
    },
    "universe_report_csv": {
      "exists": true,
      "path": "/path/to/backend/out/universe_report.csv",
      "last_modified": "2026-05-22T15:35:00"
    },
    "daily_brief_json": {
      "exists": true,
      "path": "/path/to/backend/out/daily_brief.json",
      "last_modified": "2026-05-22T15:35:00",
      "as_of": "2026-05-22",
      "generated_at": "2026-05-22T15:35:00",
      "status_label": "資料最新",
      "update_required": false
    }
  },
  "data_files": {
    "leaders_json": { "exists": true, "path": "/path/to/backend/data/leaders.json" },
    "ohlcv_csv": { "exists": true, "path": "/path/to/backend/data/ohlcv.csv" },
    "market_notes_json": { "exists": true, "path": "/path/to/backend/data/market_notes.json", "optional": true },
    "fundamentals_json": { "exists": true, "path": "/path/to/backend/data/fundamentals.json", "optional": true },
    "positions_json": { "exists": true, "path": "/path/to/backend/data/positions.json", "optional": true }
  }
}
```

**`run_status` 可能值**：
- `idle`：尚未在目前後端程序觸發背景重算
- `running`：訊號正在背景重算，前端應輪詢本 endpoint
- `success`：最近一次背景重算完成
- `failed`：最近一次背景重算失敗，錯誤在 `run_error`

`daily_brief_json.update_required=true` 時，代表每日作戰表可回顧但不應直接作為當日盤後決策依據，需先執行更新 / 重算。

若 `summary_json` 或 `daily_brief_json` 檔案存在但 JSON 解析失敗，對應檔案資訊會包含 `parse_error`；前端應顯示解析失敗，而不是只把檔案存在視為正常。

---

### `POST /api/stocks/signals/run`

觸發訊號計算（非同步背景執行，立即回傳）。

**請求 Body**（選填）：

```json
{ "as_of_date": "2026-04-11" }
```

空 body `{}` 表示使用 `ohlcv.csv` 最新日期。

**回應**：

```json
{ "status": "started", "as_of_date": "2026-04-11" }
```

---

### `GET /api/stocks/signals/summary`

取得最新 `summary.json` 全文內容。

---

### `GET /api/stocks/signals/daily-brief`

取得最新 `daily_brief.json` 全文內容，包含每日作戰表資料狀態、建議水位、汰弱留強分類與隔日任務。

重點欄位：

- `data_status`：資料最新日、覆蓋率、是否 stale、是否需要更新
- `position_guidance`：建議持股水位與風險語氣
- `rotation_plan`：續抱、等回測、可進場、優先減碼、暫不碰五桶
- `tomorrow_tasks`：隔日可執行任務，包含觀察價、進場計畫、失效條件與停利 / 出場計畫

`run_signals.py` 也會產生 `backend/out/signal_snapshots/signal_snapshot_YYYY-MM-DD.json` 與 `backend/out/signal_snapshot_review.json`。snapshot 保存當日計畫；review 比較上一份 snapshot 與本次訊號，標示 `risk_triggered`、`risk_eased`、`action_changed`、`unchanged`、`missing_current`。此 review 是復盤稽核，不是績效證明或新交易訊號。

---

### `GET /api/stocks/signals/universe_report`

下載最新 `universe_report.csv`（`FileResponse`）。

---

### `GET /api/stocks/market-notes`

列出人工盤後筆記，依日期新到舊排序。

---

### `POST /api/stocks/market-notes`

新增或覆蓋指定日期的人工盤後筆記。相同 `date` 會覆蓋既有筆記，寫入 `backend/data/market_notes.json`。

驗證規則：

- `date` 必須是 `YYYY-MM-DD`
- `title` 不可空白
- `headline` 不可空白

**請求 Body**：

```json
{
  "date": "2026-05-20",
  "title": "5/20 盤後風控筆記",
  "risk_level": "caution",
  "headline": "大盤仍需觀察 MA10，強勢股汰弱留強。",
  "position_guidance": "短線水位依系統大盤濾網，不追價。",
  "market_actions": ["確認 TSE/OTC 是否守住 MA10", "弱勢股優先處理"],
  "index_notes": [],
  "stock_notes": [],
  "rules": []
}
```

**回應**：

```json
{
  "saved": { "date": "2026-05-20", "title": "5/20 盤後風控筆記" },
  "count": 3,
  "replaced": false,
  "signals_rerun_required": true,
  "next_step": "POST /api/stocks/signals/run"
}
```

寫入筆記只更新 `market_notes.json`；若要讓 Dashboard / `summary.json` 套用新筆記，需再呼叫 `POST /api/stocks/signals/run`。

---

## 交易紀錄

### `GET /api/trades`

列出所有交易紀錄，按時間升冪排列。

**回應**（`TradeRecord[]`）：

```json
[
  {
    "id": "uuid-...",
    "stock_id": "2330",
    "name": "台積電",
    "trade_type": "buy",
    "date": "2026-03-15",
    "price": 820.0,
    "shares": 1000,
    "gross_amount": 820000,
    "fee": 1168,
    "tax": 0,
    "net_amount": 821168,
    "note": "突破頸線買入",
    "created_at": "2026-03-15T10:30:00"
  }
]
```

> 交易金額預設以台股手續費 0.1425% 計算；賣出另扣證交稅 0.3%。可在 `backend/data/settings.json` 調整 `brokerage_discount` 與 `min_brokerage_fee`。`net_amount` 買進代表實付成本，賣出代表扣費稅後實收。舊交易若沒有這些欄位，持倉與統計會依同一規則即時計算。

---

### `POST /api/trades/buy`

新增買入紀錄。

**請求 Body**（`BuyRequest`）：

```json
{
  "stock_id": "2330",
  "name": "台積電",
  "date": "2026-03-15",
  "price": 820.0,
  "shares": 1000,
  "note": "突破頸線買入"
}
```

**驗證**：`shares > 0`、`price > 0`  
**回應**：`201 Created`，`TradeRecord`

---

### `POST /api/trades/sell`

新增賣出紀錄。

**請求 Body**（`SellRequest`）：

```json
{
  "stock_id": "2330",
  "date": "2026-04-11",
  "price": 850.0,
  "shares": 500,
  "note": "停利部分出場"
}
```

**驗證**：`shares > 0`、`price > 0`、持股數量足夠  
**回應**：`201 Created`，`TradeRecord`  
**錯誤**：`400 Bad Request`（持股不足）

---

### `POST /api/trades/import`

整批匯入真實交易紀錄並覆蓋 `backend/data/trades.json`。匯入前會先驗證整批資料，全部通過後才備份舊檔到 `backend/data/backups/trades_*.json`，再寫入新檔。

**請求 Body**（`TradeImportRequest`）：

```json
{
  "mode": "replace",
  "backup": true,
  "trades": [
    {
      "id": "real-001",
      "stock_id": "2330",
      "name": "台積電",
      "trade_type": "buy",
      "date": "2026-05-19",
      "price": 1000,
      "shares": 1000,
      "note": "真實成交",
      "created_at": "2026-05-19T09:00:00"
    }
  ]
}
```

`trades[]` 也可以使用簡化格式，只帶真實成交必要欄位：

```json
{
  "trades": [
    {
      "stock_id": "2330",
      "trade_type": "buy",
      "date": "2026-05-19",
      "price": 1000,
      "shares": 1000,
      "note": "真實成交"
    }
  ]
}
```

**驗證**：交易清單不可為空、`id` 不可重複、`price > 0`、`shares > 0`、賣出不可超過前面累計持股。若 `id` / `created_at` 未提供，系統會自動產生；若 `name` 未提供，優先用 `stock_names.json`，找不到則用代碼；若 `gross_amount` / `fee` / `tax` / `net_amount` 未提供，系統會依目前手續費設定補齊。

**回應**：

```json
{
  "imported_count": 1,
  "buy_count": 1,
  "sell_count": 0,
  "backup_path": "/Users/ryan/Desktop/code/new_stock/backend/data/backups/trades_20260519T230000000000.json",
  "warnings": [
    "自動補齊 id 1 筆",
    "自動補齊 created_at 1 筆",
    "自動補齊金額欄位 1 筆"
  ]
}
```

**錯誤**：`400 Bad Request`（資料為空、重複 id、價格/股數不合法、賣出超過持股）

---

### `POST /api/trades/import/validate`

正式匯入前的完整驗證報告。使用與 `POST /api/trades/import` 相同的請求 Body，但不會備份、不會覆蓋 `trades.json`；與 preview 不同的是，validate 會一次回傳所有可檢出的錯誤，不會遇到第一個錯誤就停止。

**錯誤回應範例**：

```json
{
  "valid": false,
  "error_count": 4,
  "errors": [
    "第 1 筆交易價格必須大於 0",
    "第 2 筆交易 id 重複：b1",
    "第 2 筆交易股數必須大於 0",
    "第 3 筆 2303 可賣出股數不足，目前累計持有 0 股"
  ],
  "imported_count": 3,
  "buy_count": 2,
  "sell_count": 1,
  "positions_preview": [],
  "warnings": [
    "自動補齊 created_at 3 筆",
    "自動補齊金額欄位 3 筆"
  ]
}
```

**成功回應**：`valid: true`、`error_count: 0`，並回傳 `positions_preview` 供確認。

---

### `POST /api/trades/import/preview`

正式匯入前的預檢。使用與 `POST /api/trades/import` 相同的請求 Body 與驗證規則，但不會備份、不會覆蓋 `trades.json`。回應會多帶 `positions_preview`，用來確認匯入後剩餘持股與均價。

**回應重點**：

```json
{
  "imported_count": 2,
  "buy_count": 1,
  "sell_count": 1,
  "backup_path": null,
  "warnings": [
    "自動補齊 id 2 筆",
    "自動補齊 created_at 2 筆",
    "自動補齊金額欄位 2 筆"
  ],
  "positions_preview": [
    {
      "stock_id": "2330",
      "name": "台積電",
      "total_shares": 1000,
      "avg_cost": 100.14,
      "total_cost": 100142,
      "current_price": 120,
      "current_value": 119529,
      "unrealized_pnl": 19387,
      "return_rate": 19.36
    }
  ]
}
```

**使用順序**：先呼叫 validate 看完整錯誤清單，再呼叫 preview 確認匯入後持倉摘要，最後呼叫 import 正式覆蓋。

---

### `POST /api/trades/clear`

明確清空交易紀錄。這是唯一允許把 `trades.json` 清成空陣列的流程；匯入空清單仍會被拒絕。預設會先備份舊檔到 `backend/data/backups/trades_*.json`。

**請求 Body**：

```json
{
  "confirm": "CLEAR_TRADES",
  "backup": true
}
```

**回應**：

```json
{
  "cleared_count": 12,
  "backup_path": "/Users/ryan/Desktop/code/new_stock/backend/data/backups/trades_20260519T230000000000.json",
  "warnings": []
}
```

**錯誤**：`400 Bad Request`（`confirm` 不是 `CLEAR_TRADES`）

---

### `GET /api/trades/backups`

列出交易紀錄備份檔。只會列出 `backend/data/backups/trades_*.json`。

**回應**：

```json
[
  {
    "filename": "trades_20260520T090000000000.json",
    "path": "/Users/ryan/Desktop/code/new_stock/backend/data/backups/trades_20260520T090000000000.json",
    "size_bytes": 2112,
    "trade_count": 12,
    "modified_at": "2026-05-20T09:00:00"
  }
]
```

---

### `POST /api/trades/backups/restore`

從指定備份檔還原交易紀錄。還原前會先備份目前的 `trades.json`，避免還原動作本身不可逆。

**請求 Body**：

```json
{
  "filename": "trades_20260520T090000000000.json",
  "confirm": "RESTORE_TRADES"
}
```

**回應**：

```json
{
  "restored_from": "trades_20260520T090000000000.json",
  "restored_count": 12,
  "backup_path": "/Users/ryan/Desktop/code/new_stock/backend/data/backups/trades_20260520T100000000000.json",
  "warnings": []
}
```

**錯誤**：`400 Bad Request`（檔名不合法或確認字串錯誤）、`404 Not Found`（找不到備份）

---

## 投資組合

### `GET /api/portfolio`

取得目前持倉列表，包含即時估算損益。

**回應**（`Position[]`）：

```json
[
  {
    "stock_id": "2330",
    "name": "台積電",
    "total_shares": 1000,
    "avg_cost": 820.0,
    "total_cost": 820000,
    "current_price": 850.0,
    "current_value": 846376,
    "unrealized_pnl": 30000,
    "return_rate": 3.66
  }
]
```

> `current_price` 來自 `ohlcv.csv` 最新收盤價；`current_value` 為估算賣出扣除手續費與證交稅後的淨值。

---

### `GET /api/portfolio/analysis`

取得持倉 + 技術分析合併結果，依訊號緊急度排序。

**回應**（`HoldingAnalysis[]`）：

```json
[
  {
    "avg_cost": 820.0,
    "shares": 1000,
    "unrealized_pnl": 30000,
    "return_rate": 3.66,
    "analysis": { "...": "StockAnalysis 完整內容" }
  }
]
```

**排序**：`exit_warning` → `invalidated` → `take_profit_warning` → `hold` → `watchlist` → `ready_to_enter` → `entry_confirmed` → `DATA_MISSING`

---

### `GET /api/portfolio/summary`

取得投組摘要統計。

**回應**（`PortfolioSummary`）：

```json
{
  "total_positions": 5,
  "total_cost": 1500000,
  "total_market_value": 1650000,
  "total_unrealized_pnl": 150000,
  "hold_count": 3,
  "take_profit_warning_count": 1,
  "exit_warning_count": 1,
  "invalidated_count": 0
}
```

---

## 統計

### `GET /api/stats?period={period}`

取得交易統計數據。

**查詢參數**：
- `period`：`monthly`（本月）或 `all`（全期）

**回應**（`Stats`）：

```json
{
  "period": "monthly",
  "buy_count": 3,
  "sell_count": 2,
  "realized_pnl": 15000,
  "unrealized_pnl": 30000,
  "win_rate": 0.67
}
```

---

## 系統狀態

### `GET /api/system/data-status`

取得最近一次資料更新的執行狀態與資料新鮮度。

**回應**（`DataStatus`）：

```json
{
  "last_run_started_at": "2026-04-11T15:30:00",
  "last_run_finished_at": "2026-04-11T15:35:00",
  "last_run_status": "success",
  "last_error": null,
  "last_error_summary": null,
  "last_warning": null,
  "last_warning_summary": null,
  "last_data_as_of": "2026-04-11",
  "schedule_health_status": "healthy",
  "schedule_is_overdue": false,
  "schedule_health_message": "最近一次排程更新已完成，未錯過已結束的平日。",
  "is_stale": false,
  "stale_days": 3
}
```

**`last_run_status` 可能值**：
- `success`：最近一次更新成功
- `failed`：最近一次更新失敗
- `running`：目前正在更新中
- `stale`：更新流程跑完，但資料最新日仍過期；需檢查資料源 / 網路 / backfill SKIP 原因
- `null`：從未執行過

> 當 `is_stale: true` 時，表示資料已錯過至少 1 個已結束交易日（週一至週五），前端會顯示警示 Banner。`stale_days` 仍是日曆天數，僅供畫面顯示。

**`schedule_health_status` 可能值**：

- `healthy`：最近一次完成後沒有錯過已結束的平日更新
- `running`：更新目前執行中
- `failed`：最近一次更新失敗
- `overdue`：已錯過至少一個已結束的平日更新
- `never_run`：沒有任何排程執行紀錄
- `invalid_timestamp`：完成時間缺少或格式無效

`schedule_health_status` 描述自動更新流程是否有執行；`is_stale` 描述市場資料是否過期。兩者彼此獨立，例如手動重算輸出可能讓資料恢復新鮮，但排程仍為 `overdue`。

若 `summary.json.as_of` 比 `update_status.json.last_data_as_of` 新，API 會以較新的 `summary.json.as_of` 作為 `last_data_as_of`，並重新計算 `is_stale` / `stale_days`。這是為了支援手動 backfill 後再單獨重算 signals 的流程。

---

### `GET /api/system/workflow-status`

PM 視角的每日工作流狀態。此 endpoint 彙整 data-status、signals/status 與 fundamentals-status，回傳「現在能不能用這份資料做交易判斷」與下一步優先行動。

**回應**（`WorkflowStatus`）：

```json
{
  "overall_status": "blocked",
  "can_trade_today": false,
  "headline": "今日交易前仍有必要前置工作",
  "data_as_of": "2026-05-19",
  "next_actions": [
    {
      "key": "update_data",
      "title": "先更新日線與訊號資料",
      "detail": "資料最新日 2026-05-19，已落後 3 天。",
      "priority": 95,
      "severity": "danger",
      "action_type": "update_data",
      "command": "python3 scripts/daily_update.py --months 1"
    }
  ],
  "close_checklist": [
    {
      "key": "update_data",
      "title": "更新日線 / 籌碼 / 基本面模板",
      "detail": "確保 ohlcv、籌碼與 fundamentals 匯入流程是今天可用版本。",
      "status": "todo",
      "action_type": "update_data",
      "priority": 100
    }
  ],
  "portfolio_tasks": [
    {
      "code": "2337",
      "name": "旺宏",
      "action": "exit",
      "label": "出場處理",
      "reason": "跌破 MA10",
      "key_price": "MA10 175",
      "invalidation": "重新站回 MA20",
      "priority": 100,
      "severity": "danger",
      "holding_shares": 1000,
      "holding_position_pct": 18.2,
      "journal_recorded": true
    }
  ],
  "workflow_metrics": {
    "blocker_count": 1,
    "warning_count": 0,
    "todo_step_count": 1,
    "blocked_step_count": 3,
    "done_step_count": 2,
    "portfolio_task_count": 2,
    "portfolio_danger_count": 1,
    "decision_journal_today_count": 1,
    "portfolio_tasks_without_journal_count": 1
  },
  "decision_guardrails": {
    "can_use_trade_outputs": false,
    "message": "資料最新日 2026-05-19，已落後 3 天；候選股報告、每日作戰表與技術訊號只能回顧，不可作為今天進出場依據。",
    "blocked_outputs": ["daily_brief", "universe_report", "technical_signals"],
    "required_action": "python3 scripts/daily_update.py --months 1"
  },
  "checks": {
    "data": { "status": "success", "is_stale": true, "last_data_as_of": "2026-05-19" },
    "signals": { "status": "idle", "reports_ready": true },
    "fundamentals": { "complete_count": 8, "total_codes": 20, "coverage_pct": 40.0 },
    "decision_journal": {
      "as_of": "2026-05-19",
      "today_count": 1,
      "portfolio_tasks_without_journal_count": 1,
      "missing_portfolio_codes": ["2408"],
      "parse_error": null
    }
  }
}
```

**`overall_status` 可能值**：
- `ready`：資料、訊號、每日作戰表都可用
- `warning`：短線可操作，但有低優先資料待補，例如基本面覆蓋不足
- `blocked`：交易判斷前必須先處理資料過期、報表缺失或 JSON 解析失敗
- `running`：資料更新或訊號計算正在執行中

`close_checklist` 固定回傳收盤流程六步：`update_data`、`market_note`、`run_signals`、`daily_brief`、`universe_report`、`portfolio_risk`。`status` 可為 `done`、`todo`、`blocked`、`running`。

`portfolio_tasks` 由 `universe_report.csv` 中目前持股列產生，排序以 `exit` / `reduce` 優先，再看 `daily_priority`。此欄位只整理既有持股任務，不另建新交易訊號。`journal_recorded` 只表示該持股待辦在 `data_as_of` 是否已有決策日誌，不代表交易已執行。

`workflow_metrics` 是 Dashboard KPI，用既有 `next_actions`、`close_checklist`、`portfolio_tasks` 與決策日誌覆蓋率推導，不應另建買賣判斷。`decision_journal_today_count` 以 `data_as_of` 對齊今天持股待辦已記錄的股票數，`portfolio_tasks_without_journal_count` 代表尚未復盤記錄的持股待辦數。

`decision_guardrails` 是交易輸出使用閘門。當 `can_use_trade_outputs=false` 時，前端應把 `blocked_outputs` 顯示為「只能回顧、不可作為今天交易依據」，並優先引導使用者執行 `required_action`。

---

### `GET /api/system/update-workflow`

每日更新流程狀態機。告訴 Dashboard 目前卡在哪一步、下一個可執行動作是什麼；與 `workflow-status`（PM 視角彙總）不同，本 endpoint 聚焦「更新流程本身」的步驟進度。

**回應**（`UpdateWorkflowStatus`）：

```json
{
  "generated_at": "2026-07-06T15:35:00",
  "overall_status": "warn",
  "headline": "資料已更新，仍有待處理警示",
  "can_use_trade_outputs": false,
  "current_step": "review_alerts",
  "next_action": {
    "key": "signal_alerts",
    "title": "檢視訊號變化警示",
    "detail": "…",
    "action_type": "copy_command",
    "command": "…",
    "copy_command": "…",
    "expected_outputs": [],
    "action_payload": {}
  },
  "steps": [
    { "key": "update_data", "label": "更新資料", "status": "done", "message": "…", "command": null }
  ],
  "checks": {}
}
```

- `steps[].status`：`done` / `warning` / `blocked` / `running`。
- `next_action.action_type`：`copy_command`（有可複製指令）或 `wait`（等待中，無指令可執行）。
- `action_payload.requires_user_input=true` 代表該動作需要使用者提供資料或人工判斷（例如真實基本面 CSV、人工檢視警示），系統與前端都不應代做。
- `can_use_trade_outputs=false` 時，交易輸出只能回顧，不可作為當日交易依據（與 `workflow-status.decision_guardrails` 同一閘門邏輯）。

---

### `GET /api/system/today-scan`

讀取 Today Scan 衍生報告（`out/today_scan.json`）。唯讀：不重算策略、不寫入任何檔案。檔案由 `python3 scripts/today_scan.py --write-report` 或每日更新流程產生；尚無檔案時回 `404`。

**回應**（主要欄位）：

| 欄位 | 說明 |
|------|------|
| `as_of` / `generated_at` | 資料日期與產生時間 |
| `rules_version` / `rules_metadata` | 掃描規則版本與參數（兩策略 profile、timeout 等） |
| `data_status` | `universe_size` / `data_ok_count` / `data_missing_count` |
| `market_context` | 大盤 regime 與 old_wang 市場濾網判斷及理由 |
| `signal_counts` | 7 狀態訊號 + `DATA_MISSING` 各自數量 |
| `formal_entries` | 可小試名單（正式進場條件成立） |
| `old_wang_candidates` / `steady_momentum_candidates` | 兩策略觀察候選（含各自 score / signal） |
| `risk_items` | 風險處理名單（持股或候選出現退出 / 減碼訊號） |
| `usage_status` | 使用閘門：`can_use_trade_outputs`、`status`、`reason`、`next_action`；被 Daily Check 或 signal alerts 阻擋時會標示 blocking action |
| `bucket_notes` / `data_freshness` / `notes` | 分桶說明、資料新鮮度與補充備註 |

候選項目一律附 `daily_action` / `daily_action_label` 與策略分數摘要；本 endpoint 不產生新訊號，只整理最近一次 run 的結果。

---

### `GET /api/system/pm-worklist`

PM 首頁工作佇列：把資料修復、基本面補資料、候選復盤與 Daily Check 整理成單一優先順序清單，供 Dashboard 的 PM Worklist / Primary Action / Today Focus 區塊使用。

**回應**（`PmWorklist`）：

```json
{
  "generated_at": "2026-07-06T15:35:00",
  "overall_status": "warn",
  "headline": "…",
  "primary_action": {
    "key": "signal_alerts",
    "title": "檢視訊號變化警示",
    "detail": "…",
    "priority": 1,
    "severity": "warn",
    "status": "todo",
    "action_type": "signal_alerts",
    "action_label": "前往檢視",
    "command": "",
    "source": "signal_alerts",
    "metric": "27 筆",
    "focus_codes": ["2330"],
    "action_payload": {}
  },
  "today_focus": [
    {
      "category": "entry",
      "code": "2330",
      "name": "台積電",
      "label": "可小試",
      "reason": "…",
      "next_action": "…",
      "severity": "info",
      "source": "today_scan",
      "price_basis": "2026-07-06 收盤",
      "as_of": "2026-07-06"
    }
  ],
  "items": []
}
```

- `items` 依 `priority` 升冪排列；`primary_action` 是其中最優先的一項（可能為 `null`）。
- `action_type` 是工作項分類（例如 `update_workflow` / `data_repair` / `fundamentals` / `decision_journal` / `data_freshness` / `market_note` / `signal_alerts` / `daily_check`），供前端決定跳轉位置。
- 需要使用者提供資料或人工判斷的項目，會在 `action_payload` 中帶 `requires_user_input=true` 與 `user_input_note`，前端不應提供一鍵代做。
- 本 endpoint 只彙整既有報告（daily_check / today_scan / fundamentals / coverage），不重算策略、不建立新交易訊號。

---

### `GET /api/system/fundamentals-priority-fill`

下載目前基本面優先補資料 CSV（`fundamentals_priority_fill.csv`）。內容由 `fundamental_service` 依 `fundamentals-status.next_fill_targets` 產生，供基本面避雷補資料流程使用。

外部資料建議先用 `python3 scripts/prepare_fundamentals_priority_import.py --write-template` 產生 `fundamentals_priority_import_template.csv`，整理真實 CSV 後 dry-run，再用 `--apply` 寫入 `fundamentals_priority_fill.csv`。不得直接偽造或手動改寫 `fundamentals.json`。

**回應**：`text/csv`

---

### `GET /api/system/fundamentals-status`

基本面覆蓋率與補資料操作狀態。Dashboard 應使用 `priority_fill_readiness` 決定是否允許預覽或正式合併。

`priority_fill_readiness.status`：
- `not_generated`：尚未產生補資料 CSV。
- `empty`：CSV 已產生但尚未填任何基本面欄位，可預覽，不可正式合併。
- `invalid`：CSV 有非數字、空白代號或重複代號等錯誤，不可預覽或合併。
- `ready_to_preview`：CSV 已有可合併欄位，可先預覽，再正式合併。

**片段回應**：

```json
{
  "coverage_pct": 0.0,
  "priority_fill_readiness": {
    "status": "empty",
    "can_preview": true,
    "can_merge": false,
    "message": "補資料 CSV 有 20 檔，但尚未填任何基本面欄位。",
    "suggested_action": "先填 ROE、現金流、負債、成長與估值欄位，再按預覽合併。",
    "filled_code_count": 0,
    "filled_field_count": 0,
    "row_count": 20
  }
}
```

---

### `POST /api/system/fundamentals-priority-fill/merge`

預覽或正式合併 `fundamentals_priority_fill.csv` 回 `backend/data/fundamentals.csv`。正式合併後會同步匯入 `backend/data/fundamentals.json`。

**請求 Body**：

```json
{ "dry_run": true, "confirm": null }
```

正式合併時需使用：

```json
{ "dry_run": false, "confirm": "MERGE_PRIORITY_FUNDAMENTALS" }
```

**回應**：

```json
{
  "dry_run": true,
  "updated_code_count": 1,
  "updated_codes": ["2408"],
  "updated_field_count": 2,
  "added_count": 0,
  "added_codes": [],
  "csv_path": "/path/to/backend/data/fundamentals.csv",
  "source": "/path/to/backend/out/fundamentals_priority_fill.csv",
  "json_path": null,
  "imported_count": null,
  "validation": { "valid": true }
}
```

---

## 決策日誌

### `GET /api/decision-journal`

讀取最近的決策日誌。這是復盤資料，不是交易紀錄，不會改動持倉、現金或 `trades.json`。

**查詢參數**：
- `limit`：回傳筆數，預設 100，最大 500
- `code`：選填，指定股票代號
- `date`：選填，指定決策日期（`YYYY-MM-DD`）
- `decision`：選填，指定決策分類；允許 `buy`、`sell`、`hold`、`skip`、`reduce`、`watch`

**回應**（`DecisionJournalEntry[]`）：

```json
[
  {
    "id": "f0a1...",
    "date": "2026-05-22",
    "code": "2330",
    "name": "台積電",
    "decision": "hold",
    "reason": "守住 MA10，尚未跌破關鍵支撐。",
    "price": 2310.0,
    "shares": 1000,
    "key_price": "MA10 2280",
    "invalidation": "跌破 MA10 且爆量長黑",
    "source": "manual",
    "created_at": "2026-05-22T15:30:00",
    "updated_at": null,
    "workflow_status": "ready",
    "workflow_headline": "資料與訊號已就緒"
  }
]
```

---

### `POST /api/decision-journal`

新增一筆決策日誌。允許的 `decision`：`buy`、`sell`、`hold`、`skip`、`reduce`、`watch`。

**請求 Body**：

```json
{
  "date": "2026-05-22",
  "code": "2330",
  "name": "台積電",
  "decision": "hold",
  "reason": "守住 MA10，尚未跌破關鍵支撐。",
  "price": 2310,
  "shares": 1000,
  "key_price": "MA10 2280",
  "invalidation": "跌破 MA10 且爆量長黑"
}
```

建立時會擷取當下 `workflow-status` 的 `overall_status` 與 `headline`，用來日後復盤。

---

### `GET /api/decision-journal/summary`

取得指定日期的決策日誌統計。這只做復盤摘要，不推論新的買賣訊號。

**查詢參數**：
- `date`：選填，`YYYY-MM-DD`；未提供時使用目前日誌中最新日期

**回應**：

```json
{
  "date": "2026-05-22",
  "total_count": 3,
  "by_decision": { "hold": 1, "reduce": 2 },
  "recent_codes": ["2303", "2408", "2337"]
}
```

---

### `PUT /api/decision-journal/{entry_id}`

更新單筆決策日誌內容。更新時會保留原本 `id`、`created_at`、`workflow_status` 與 `workflow_headline`，只修改日期、代號、名稱、決策、理由、價格、股數、關鍵價與失效條件等復盤內容，並寫入 `updated_at`。

**請求 Body** 同 `POST /api/decision-journal`。

找不到指定 id 時回傳 404。

---

### `DELETE /api/decision-journal/{entry_id}`

刪除單筆決策日誌。這只會移除復盤紀錄，不會改動交易紀錄、持倉、現金或訊號輸出。

**回應**：

```json
{ "deleted": "f0a1..." }
```

找不到指定 id 時回傳 404。

---

## Personal Backups

個人資料備份只包含 `trades.json`、`decision_journal.json`、`watchlists.json`、`market_notes.json` 與 `settings.json`。不包含行情、fundamentals、chips、stock names 或 `backend/out/*` 產物。

### `GET /api/system/personal-backups`

列出已建立的個人資料備份。

### `POST /api/system/personal-backups`

建立新的個人資料備份，回傳 `backup_id`、檔案數、缺檔數與每個檔案 checksum。

### `POST /api/system/personal-backups/restore-preview`

Dry-run 預覽還原，不寫入任何檔案。

```json
{ "backup_id": "personal_20260625T030000000000" }
```

回傳每個檔案會 `create`、`overwrite`、`skip_missing` 或因 checksum / 缺檔被阻擋。

### `POST /api/system/personal-backups/restore`

正式還原個人資料。必須提供確認字串，且還原前會自動建立 pre-restore backup。

```json
{
  "backup_id": "personal_20260625T030000000000",
  "confirm": "RESTORE_PERSONAL_DATA"
}
```

---

## 美股（US Market）

> 唯讀觀察層：清單 / 基本行情 / 技術狀態 / 觀察訊號 / 觀察策略；**全部非推薦、非買賣建議、不下單**。與台股端點分離，不套台股 old_wang / steady_momentum。

### `GET /api/markets/us/universe`

美股追蹤清單（`us_leaders.json` × `ohlcv_us.csv`，第一版約 27 檔）。每筆：`code` / `name` /
`category`（觀察用分類，如 `"ETF / Benchmark"` / `"Mega-cap Tech"` / `"Semiconductors / AI"` /
`"Software / Cloud"` / `"Defensive / Consumer"`；**非產業標準分類、非推薦**）/
`region`（固定 `"US"`）/ `has_data` / `row_count` / `last_data_as_of` / `last_close` /
`data_status`（`"ok"` | `"no_data"`）。尚未回補時 `has_data=false`、`last_close=null`。

### `GET /api/markets/us/status`

美股資料源 / 資料狀態，供前端誠實呈現：

```json
{
  "region": "US",
  "source_configured": true,
  "source_label": "Yahoo Finance（美股，非官方、免 key）",
  "universe_size": 27,
  "tickers_with_data": 27,
  "missing_tickers": [],
  "insufficient_tickers": [],
  "min_row_count": 256,
  "last_data_as_of": "2026-07-09",
  "expected_trading_day": "2026-07-10",
  "days_since_last": 1,
  "is_stale": false,
  "backfill_command": "cd backend && python3.11 scripts/backfill_ohlcv_us.py"
}
```

- US 主資料源為 **Yahoo Finance chart endpoint（免 API key、非官方、best-effort）**，故 `source_configured` 恆為 `true`。**Stooq 已停用**（改為需瀏覽器 JS 驗證）；**Finnhub** 保留為 future optional（官方、需 key）。
- `source_configured=false` → 前端顯示「美股資料源尚未就緒」；`true` 但 `tickers_with_data=0` → 顯示「美股資料尚未更新」（請先跑 `backfill_command`）。
- **回補可觀測性**（讓「回補是否補齊」一眼可判，供手動回補後驗收；皆由 universe × ohlcv 交叉比對）：
  - `missing_tickers`：**完全無資料**的 ticker（`has_data=false`）代碼清單，已排序。
  - `insufficient_tickers`：**有資料但筆數不足**（`row_count < 60`）的代碼清單，已排序。門檻沿用 watch signal 的 `MIN_SIGNAL_ROWS`（需 ≥ 60 筆才算得出 MA60 / 觀察訊號），不另寫死。
  - `min_row_count`：目前**所有有資料 ticker** 的最小 `row_count`（無任何資料時為 `null`）。
  - 27 檔全數回補後預期：`missing_tickers=[]`、`insufficient_tickers=[]`、`min_row_count` ≈ 256。
  - `missing_tickers` 與 `insufficient_tickers` **互斥**：前者沒資料、後者有資料但太短。每檔逐筆 `row_count` 仍可從 `GET /api/markets/us/universe` 取得。
- **資料新鮮度**（weekend-aware、**不含 NYSE 假日**、容忍 1 個交易日以避免收盤前誤判）：
  - `expected_trading_day`：以 America/New_York 為準的最近應有交易日。
  - `days_since_last`：`last_data_as_of` 之後到 `expected_trading_day` 的**交易日數**（缺資料時 `null`）。
  - `is_stale`：`last_data_as_of` 缺失、或落後超過 1 個交易日 → `true`；前端顯示「資料可能已過期，請重跑 backfill」。

### `GET /api/markets/us/analysis`

美股**基本技術狀態**（Phase 2，唯讀，**非買賣建議 / 非策略**）。每筆在 universe 欄位外（含 `category` 觀察分類），另含技術指標與描述性狀態：

| 欄位 | 說明 |
|------|------|
| `category` | 觀察用分類（同 universe，如 `"Mega-cap Tech"`；非推薦分組） |
| `ma20` / `ma60` | 20 / 60 日均線（資料不足時 `null`） |
| `rsi14` | 14 期 RSI（資料不足時 `null`） |
| `change_20d_pct` | 20 日漲跌幅（%） |
| `dist_ma20_pct` / `dist_ma60_pct` | 收盤距 MA20 / MA60（%） |
| `days_since_last` | 距最後資料日的天數（新鮮度） |
| `status` | `trend_up` / `recovering` / `pullback_watch` / `overheated` / `weak` / `no_data` |
| `status_label` | 狀態中文標籤（描述性，非推薦） |

`status` 判斷順序與語意（**`no_data` 與 `weak` 刻意分開**——前者是「算不出來」，後者是「真的弱」）：

| status | label | 條件 |
|--------|-------|------|
| `no_data` | 資料不足 | 筆數 < 20，或算不出 MA20 / 收盤。**僅代表無法計算，不代表弱勢。** |
| `overheated` | 過熱 | RSI ≥ 70 或 距 MA20 ≥ +15% |
| `weak` | 弱勢 | 收盤跌破 MA60（長線偏弱） |
| `trend_up` | 趨勢向上 | 收盤 ≥ MA20，且 MA20 ≥ MA60（或尚無 MA60） |
| `recovering` | 趨勢修復中 | 收盤同時站上 MA20 與 MA60，但 MA20 < MA60（均線尚未翻多） |
| `pullback_watch` | 回檔觀察 | 收盤 < MA20，但仍守住 MA60（或尚無 MA60） |

> `recovering` 於 2026-07-10 補上：先前 `weak_or_no_data` 混合桶會把「收盤站上 MA20/MA60 但 MA20 < MA60」（如當時的 META / TSLA）誤標為「弱勢 / 資料不足」。該混合桶**已移除**。

狀態純為描述性技術分類；**不套用台股 old_wang / steady_momentum，不產生買賣訊號。**

### `GET /api/markets/us/signals`

美股**觀察訊號**（Phase 3，唯讀，**非推薦 / 非買賣建議 / 非下單**）。以 Phase 2 指標 + SPY/QQQ 大盤基準產生描述性觀察訊號。

```json
{
  "as_of": "2026-07-09",
  "market_bias": "bullish",
  "market_note": "SPY / QQQ 皆在 MA60 上方，大盤偏多",
  "benchmarks": { "SPY": {"above_ma60": true, "close": 751.71, "ma60": 734.77}, "QQQ": {"above_ma60": true, "close": 723.28, "ma60": 702.85} },
  "signals": [
    {
      "code": "AAPL", "name": "Apple Inc.", "category": "Mega-cap Tech", "close": 316.22,
      "status": "trend_up", "signal": "watch_breakout", "signal_label": "觀察突破",
      "reasons": ["站上 MA20 / MA60，逼近 20 日高 318.00", "大盤（SPY/QQQ）在 MA60 上方"],
      "risk_notes": ["留意假突破 / 量能不足"],
      "priority": 80, "data_as_of": "2026-07-09"
    }
  ]
}
```

- **`category`**：觀察用分類（同 universe，如 `"Mega-cap Tech"`）；前端可據此過濾，**非推薦分組**。
- **`status`**：帶出 Phase 2 技術狀態（新 enum：`trend_up` / `recovering` / `pullback_watch` / `overheated` / `weak` / `no_data`）。觀察訊號（`signal`）規則本身**未改**，只是 `status` 欄位跟著新 enum。
- **`market_bias`**：`bullish`（SPY/QQQ 皆在 MA60 上方）/ `bearish`（皆下方，個股 priority 降級）/ `mixed` / `unknown`（基準資料不足）。
- **`signal`**：`watch_breakout` / `watch_pullback` / `trend_up` / `overheated` / `avoid_weak`（描述性觀察狀態）。
- **`priority`**：觀察優先度（排序用，數字越大越優先看）；**非推薦分數、非買賣訊號**。大盤偏弱時整體降級。
- **`reasons` / `risk_notes`**：字串陣列，解釋觀察狀態與風險（描述性）。
- `ohlcv_us.csv` 不存在 / 無資料 → 每檔 `avoid_weak`、`market_bias=unknown`（誠實回報資料不足，不假裝有訊號）。
- **明確不做**：買賣建議、下單、正式推薦；**不套用台股 old_wang / steady_momentum**。

### `GET /api/markets/us/strategy/trend-follow`

美股**觀察策略 `us_trend_follow`：大盤守門的趨勢延續**（唯讀，**非推薦 / 非買賣建議 / 非下單**）。在 Phase 2 指標上做跨檔收斂：回答「大盤允許的前提下，哪幾檔處於健康趨勢延續段且未追高、其他為何不在清單」。

```json
{
  "as_of": "2026-07-10",
  "strategy": "us_trend_follow",
  "strategy_label": "趨勢延續（大盤守門）",
  "market_gate": { "active": true, "bias": "bullish", "note": "SPY / QQQ 皆在 MA60 上方，策略啟用" },
  "candidates": [
    {
      "code": "AAPL", "name": "Apple Inc.", "category": "Mega-cap Tech", "close": 314.08,
      "state": "candidate", "rank": 1,
      "reasons": ["收盤 314.08 > MA20 298.04 > MA60 293.04（多頭排列）", "RSI 61 介於 50–68，有動能未過熱", "距 MA20 +5.4%（≤ +8%，未追高）", "20 日漲跌幅 +7.7%"],
      "risk_notes": ["趨勢延續觀察，非入場建議；跌破 MA20 即離開清單", "盤整市清單會反覆進出（whipsaw），清單變動不代表訊號翻轉"],
      "data_as_of": "2026-07-10"
    }
  ],
  "excluded": [
    { "code": "SPY", "name": "SPDR S&P 500 ETF", "category": "ETF / Benchmark", "close": 751.71, "state": "watch", "reasons": ["ETF 作為大盤量尺，不列入個股候選"], "data_as_of": "2026-07-10" }
  ]
}
```

**大盤守門（market_gate）**：
- `bullish`（SPY 且 QQQ 在 MA60 上方）→ `active=true`，正常輸出。
- `mixed` → `active=true`，但全體 candidate 的 `state` 降為 `watch` 並加 reason「大盤分歧」。
- `bearish` / `unknown` → `active=false`、`candidates=[]`，`note` = 「大盤在 MA60 下方或資料不足，本策略今日不產生觀察對象」；原本符合條件者移入 `excluded` 並註明守門關閉。**空清單是規則，不是故障。**

**入選條件**（全部滿足）：`close > MA20 > MA60`、`50 ≤ RSI14 ≤ 68`、`0 ≤ dist_ma20_pct ≤ +8`（防追高）、`20 日漲跌幅 > 0`、`category ≠ ETF / Benchmark`。

**排除規則**（依序，附 reasons）：ETF 量尺 → `watch`；資料不足（< 60 筆）→ `avoid`；RSI ≥ 70 或 dist ≥ +15%（沿用 Phase 2 過熱門檻）→ `overheated`；跌破 MA60 → `avoid`；`recovering`（均線未翻多）→ `watch`；入選條件任一不符 → `watch`（逐項列出未通過原因）。

**排序**：`dist_ma20_pct` 小→大（防追高排序化）→ `change_20d_pct` 大→小 → code 字母序；`rank` 為 1 起排序位置。**不產出 0–100 分數**；`state` 只有觀察語言（`candidate` / `watch` / `avoid` / `overheated`）。每筆（含 excluded）必有 `reasons`；candidate 另有 `risk_notes`。

---

## 錯誤格式

所有錯誤回應格式統一：

```json
{ "detail": "錯誤說明文字" }
```

或含結構化細節：

```json
{ "detail": { "message": "持股不足", "available": 500, "requested": 1000 } }
```
