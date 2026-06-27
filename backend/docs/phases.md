# 開發階段記錄（Phase 1–10）

本文件整理各開發階段的完成項目、主要決策與已知限制，  
供後續維護者了解系統演進脈絡。

---

## Phase 1：專案骨架

**目標**：建立 FastAPI + React 骨架，跑通最基本的資料流。

**完成項目**：
- FastAPI 應用初始化（`app/main.py`）
- CORS 設定（開放 `localhost:5173`）
- React 18 + TypeScript 前端骨架（Vite）
- 基本 router / service / storage 分層建立
- `backend/data/` 資料夾結構規劃

**決策**：
- 資料儲存採 CSV / JSON，不上資料庫
- 分層原則：router 輕、service 厚、storage 專職 I/O

---

## Phase 2：OHLCV 資料回補

**目標**：從 TWSE 抓取歷史日線資料。

**完成項目**：
- `scripts/backfill_ohlcv_twse.py`
  - 從 TWSE OpenAPI 按月份拉取 OHLCV
  - 節流（每次請求間隔 ~1.2 秒）
  - 第一版僅支援 TWSE；後續已補上 TPEX fallback（見 Phase 10）
  - 以 `(code, date)` 去重，merge 後寫回 `ohlcv.csv`
- `backend/data/leaders.json`：股票代碼清單格式確立

**目前狀態**：
- TWSE / TPEX 日線皆已支援；特殊商品或資料來源格式變動仍需另行確認
- API 限速，大量回補耗時

---

## Phase 3：訊號計算核心

**目標**：實作技術訊號計算，產出 `summary.json` / `universe_report.csv`。

**完成項目**：
- `services/signals_service.py`：7 狀態訊號系統
- 技術指標：MA5 / MA20 / MA60、RSI14、成交量比（vol_ratio）
- 長短線趨勢判斷（基於 MA60 / MA20 關係）
- 支撐壓力線（20/60 日區間靜態高低點 + MA 動態線）
- `scripts/run_signals.py`
- 輸出：`summary.json`、`buy_list.json`、`sell_list.json`、`hold_list.json`、`universe_report.csv`
- 訊號最少需要 60 根 K 棒，否則標記 `DATA_MISSING`

**決策**：
- 訊號採 7 狀態而非簡單 BUY/SELL，保留持倉管理（hold / warning）
- `no_buy_reason` 欄位確保空清單時可解釋原因

---

## Phase 4：REST API

**目標**：建立前端所需的完整 API 端點。

**完成項目**：
- `routers/stocks.py`：推薦清單、個股分析、訊號狀態 / 觸發 / summary / universe_report
- `routers/trades.py`：列出 / 買入 / 賣出（含持股數驗證）
- `routers/portfolio.py`：持倉列表、持倉分析、投組摘要
- `routers/stats.py`：月結 / 全期統計
- `routers/system.py`：資料更新狀態
- Pydantic models 完整定義（`models/` 下 4 個模組）

---

## Phase 5：前端基礎

**目標**：建立可操作的前端介面。

**完成項目**：
- React 18 + TypeScript + Vite SPA
- Tab 導航（9 個頁面，無 React Router）
- API 客戶端（`api/client.ts`）
- TypeScript 型別定義（`types/index.ts`）
- 基礎 CSS（台股漲紅跌綠色系）
- 訊號 Dashboard、推薦清單、交易紀錄、統計頁面

---

## Phase 6：技術分析圖表

**目標**：實作個股 K 線圖與分析面板。

**完成項目**：
- `services/analysis_service.py`：單股深度分析（即時計算）
  - 支撐壓力線（靜態 + 動態）
  - 趨勢線（連接擺動高低點，5 Bar 窗口）
  - 回傳最近 120 根 OHLCV
- `components/StockChart.tsx`：K 線圖（lightweight-charts）
  - MA5 / MA20 / MA60 均線
  - 支撐（綠色虛線）/ 壓力（紅色虛線）
  - 上升 / 下降趨勢線
- `components/AnalysisPanel.tsx`：訊號面板
  - 訊號 Badge、分數、長短線趨勢
  - reasons / risk_notes / no_buy_reason / 型態結果
- `pages/AnalysisPage.tsx`：技術分析頁面（含 `initialCode` 跨頁跳轉）

---

## Phase 7：型態辨識

**目標**：實作 W 底、M 頂型態辨識。

**完成項目**：
- `services/pattern_service.py`
  - W 底：找兩個相近擺動低點（差異 ≤ 5%），頸線需比低點高 ≥ 3%
  - M 頂：找兩個相近擺動高點（差異 ≤ 5%），頸線需比高點低 ≥ 3%
  - 三種狀態：`forming` / `confirmed` / `failed`
- 型態結果整合至 `StockAnalysis.pattern`
- 前端 `AnalysisPanel` 顯示型態 Badge（含狀態與頸線價位）
- 測試：`tests/test_pattern_service.py`、`tests/test_signals_pattern.py`

**決策**：
- 採擺動點偵測（5 Bar 窗口）而非固定區間
- 不允許將 `forming` 誤判為 `confirmed`

---

## Phase 8：持倉分析與自動更新

**目標**：持倉技術分析、統一更新流程、排程機制。

**完成項目**：
- `services/holdings_service.py`：持倉 + 技術分析合併，依緊急度排序
- `services/update_service.py`：統一更新流程（backfill + signals + 寫狀態）
- `scripts/update_all_data.py`：CLI 入口，含 PID 鎖防重複執行
- `backend/out/update_status.json`：更新狀態持久化
- `routers/system.py` + `GET /api/system/data-status`
- `scripts/setup_schedule.sh` / `remove_schedule.sh`（macOS launchd）
- `scripts/cron_example.txt`（cron 範例）
- 測試：`test_update_status.py`、`test_schedule.py`

---

## Phase 9：資料新鮮度 UI 與通知

**目標**：前端顯示資料新鮮度，stale / running / failed 狀態可視化。

**完成項目**：
- `pages/PortfolioOverviewPage.tsx` 新增 `FreshnessSection`：
  - 資料最新日、距今天數、最後更新時間、更新狀態
  - `running` 時顯示藍色 Banner + spinner
  - `stale` 時顯示黃色警示 Banner（含操作指引）
  - `failed` 時顯示紅色 Banner + 可展開的完整錯誤訊息
- 自動輪詢：`last_run_status = "running"` 時每 3 秒 poll
- 更新完成後自動刷新持倉與摘要資料
- `services/notify_service.py`：通知 stub（成功 / 失敗）

---

## Phase 10：投組頁互動強化

**目標**：提升「投組總覽」頁的互動性與資訊密度。

**完成項目**：
- **股票名稱可點擊跳轉**：持股清單中的股票名稱改為 `link-btn`，點擊後跳轉至技術分析頁並自動載入
- **持股清單排序**：表頭「訊號」/ 「未實現損益」/「報酬率」可點擊排序（升冪 → 降冪 → 取消）
  - 訊號排序依緊急度：`exit_warning` 最緊急（0），`DATA_MISSING` 最後（7）
- **手動重新整理按鈕**：頁面右上角 `⟳ 重新整理`，刷新中顯示 spinner
- **Running 狀態整合**：刷新按鈕在 `running` 時自動 disabled
- **重用元件**：跳轉至 `AnalysisPage`，該頁已內建 `StockChart` + `AnalysisPanel`
- **CSS**：新增 `.link-btn`、`.th-sortable`、`.sort-ind`、`.sort-ind-active`、`.overview-toolbar`、`.overview-sort-hint`

---

## Phase 11：Core 單股可信回測第一版

**目標**：驗證既有 `core` 日線訊號的歷史交易結果，不以增加策略數量為目的。

**完成項目**：
- `services/backtest_service.py`：單股、單一多頭部位事件引擎
- D 日收盤產生訊號，D+1 實際下一根日 K 開盤成交
- 買賣不利滑價、正式手續費／折扣／最低費用與賣出證交稅
- 歷史個股／0050 prefix 隔離，回測模式不讀目前籌碼或基本面
- 交易明細、總報酬、最大回撤、勝率、平均損益與 buy-and-hold 基準
- `scripts/run_backtest.py` 產生 `backtest_summary.json` / `backtest_trades.csv`
- 固定測資覆蓋成交時序、成本、持股估值、強制平倉與 look-ahead guard

**限制**：
- 一次只回測一檔，不處理全市場同日訊號排序與資金配置
- 不含股利、拆併股、限價／部分成交、放空與券商整合
- 回測結果是規則驗證，不是獲利保證

---

## Phase 12：交易日、資料覆蓋率與 Lineage

**目標**：讓每日資料輸入可稽核，避免休市日誤報與追蹤清單缺資料時仍顯示可交易。

**完成項目**：
- `trading_calendar_service.py`：週末、休市日與補班交易日判斷
- `backend/data/trading_calendar.json` 可選本地覆寫；缺檔或壞檔退回週一至週五
- `data_coverage_service.py`：產生 `backend/out/data_coverage_report.json`
- 覆蓋率報告列出每檔 `ok` / `missing` / `insufficient` / `lagging` 與原因
- `update_status.json`、`summary.json`、coverage report 共享 `batch_id` / `lineage`
- `doctor.py`、Daily Check 與 Update Workflow 會讀 coverage report；coverage < 80% blocked
- `daily_update.py` expected outputs 納入 `data_coverage_report.json`

**限制**：
- 第一版不自動下載官方休市日，需用本地 JSON 覆寫
- coverage 門檻先固定 80%，尚未做成設定

---

## 已知限制（跨階段）

### 資料層
- 目前追蹤清單可回補 TWSE / TPEX 日線；若新增特殊商品仍需確認來源格式
- `ohlcv.csv` 無索引，大量持倉時 I/O 較慢
- 交易紀錄以 JSON 存放，不適合大量資料（> 數千筆）
- 未實現損益的 `current_price` 來自 ohlcv.csv，非即時報價

### 訊號層
- 需至少 60 根 K 棒才能計算 MA60；新股或資料不足時顯示 `DATA_MISSING`
- 型態辨識已支援 W 底 / M 頂 / 頭肩底 / 頭肩頂；型態新鮮度與距離權重仍可優化
- 趨勢線已支援三點以上觸碰驗證與破線失效，API 仍只回傳定義斜率的 `p1/p2`；尚未採回歸線或 `anchors[]`
- 訊號 API 為背景觸發並透過 status 輪詢；CLI `run_signals.py` 仍是同步批次

### API 層
- CORS 可用 `CORS_ALLOWED_ORIGINS` 設定明確來源；不接受 wildcard
- 無認證機制，不適合直接暴露至公網
- `POST /api/stocks/signals/run` 為背景觸發；進度請透過 `/api/stocks/signals/status` 查詢

### 前端層
- Dashboard 已有 Decision Console、Today Focus、PM Worklist action payload 呈現第一版；`Dashboard.tsx` 仍偏大，後續應漸進拆分
- Tab 導航不支援 URL 深連結（無法直接分享特定分析頁面）
- 無登入機制，所有人共用同一份交易紀錄

### 排程層
- macOS launchd 需要完整磁碟存取權限
- cron 環境 PATH 較短，需使用絕對路徑
- 更新中途崩潰需手動清除 PID 檔

---

## 未完成 / 後續可做

| 項目 | 優先度 | 說明 |
|------|--------|------|
| 候選股表格資訊密度 | 中 | 已固定股票身份欄並折疊長理由；後續可再優化欄位密度與手機閱讀 |
| 首頁截圖驗收 | 已結案 | DOM / 溢出與 build 已驗證；正式截圖依 2026-06-19 使用者核准的環境限制豁免關閉 |
| 頭肩頂型態 | 已完成 | 三擺盪高點、頸線、forming / confirmed / failed、分數與風險解釋皆有固定測試 |
| 即時報價 | 低 | 需外部 WebSocket 或輪詢 |
| 多點趨勢線 | 已完成 | 2% 容差、至少三觸點、風險方向破線失效，無多點候選時保留兩點 fallback |
| 使用者認證 | 低 | 目前無登入機制 |
| 行動版 RWD 優化 | 低 | 桌面版優先 |
| LINE Notify / Email 通知 | 低 | `notify_service` 已有 stub |
| 資料庫遷移 | 低 | 資料量大時考慮 SQLite 或 PostgreSQL |
