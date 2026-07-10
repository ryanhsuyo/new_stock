# Handoff Log

> AI / 人在每次任務結束後的交接紀錄。這是給下一個接手者的摘要。

## 使用規則

- **最新紀錄放最上面**（append 在頂端，reverse-chronological）。
- 這是 **append-only 的歷史**：新增紀錄，不要改寫或刪除舊紀錄。
- 每筆只寫**可接手摘要**——不要貼完整聊天紀錄、完整 log、逐字對話。
- 每筆用下面的模板；沒有的欄位寫「N/A」，不要留白。
- 若狀態 / 規劃有變，除了在這裡記一筆，也要同步更新 `current-status.md` / `roadmap.md`。

---

## 2026-07-10 — US Phase 2 狀態語意修正（拆 `weak_or_no_data` 混合桶）

- **Date:** 2026-07-10
- **Task:** 27 檔真實回補後暴露的語意問題：`weak_or_no_data` 把「資料不足」與「弱勢」混在一桶，且 `close > MA20`、`close > MA60` 但 `MA20 < MA60` 的個股（META / TSLA）落入該桶，前端顯示「弱勢 / 資料不足」。
- **Goal:** 狀態語意誠實可讀；資料完整的股票不得被標成「資料不足」。
- **Completed:**
  - `classify_status` 拆桶（判斷順序：`no_data` → `overheated` → `weak` → `trend_up` / `recovering` → `pullback_watch`）：
    - `no_data`：筆數 < 20 或算不出 MA20 / 收盤 —— **僅代表無法計算**。
    - `weak`：收盤跌破 MA60 —— **真正弱勢**。
    - `recovering`：收盤同時站上 MA20 與 MA60，但 MA20 < MA60（均線尚未翻多）。
    - 保留 `trend_up` / `pullback_watch` / `overheated`。
  - `STATUS_LABELS` 六種標籤；`/api/markets/us/analysis` schema + api.md 條件表。
  - 前端：`UsTechStatus` 改新 enum、`.us-status-{recovering,weak,no_data}` badge（no_data 灰 / weak 紅，刻意不同色）、新增狀態圖例列。
  - 測試：新增 no_data（筆數不足 / MA20 或 close 缺）、weak（跌破 MA60、含「站上 MA20 但跌破 MA60」）、recovering（含 **META / TSLA 真實數值**）、無 MA60 的 trend_up / pullback_watch、label 對應、端點「no_data 必定真的算不出來」不變量。
- **Changed Files:** `backend/app/services/us_analysis_service.py`、`backend/tests/test_us_analysis.py`、`backend/docs/api.md`、`frontend/src/types/index.ts`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`；docs（roadmap / current-status / validation / handoff-log）。
- **Validation:** `python3.11 -m pytest -q` → **866 passed**（+8）；`npm run build` → 成功。真實 27 檔：analysis `no_data=0`、`weak=11`、`recovering=2`（META / TSLA）、`trend_up=8`、`pullback_watch=5`、`overheated=1`；`/signals` 訊號分佈與修正前**完全一致**（規則未動）。
- **Git Status:** 乾淨（feat commit 完成後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 候選：完整 NYSE 假日曆 + launchd 排程 US backfill、Finnhub optional、再擴 universe。**仍不做美股正式推薦 / 買賣 / 下單。**
- **Notes / Warnings:** **不要把 `no_data` 與 `weak` 合併回混合桶。** `us_watch_signal_service` 規則未改（`derive_watch_signal` 直接讀指標、不讀 status），只是 signal item 的 `status` 欄位跟著新 enum。

---

## 2026-07-10 — US universe 擴充 + 分類（非推薦、非買賣建議）

- **Date:** 2026-07-10
- **Task:** 把美股觀察清單擴到第一版 27 檔，每檔加觀察用 `category`，並讓 `/universe`、`/analysis`、`/signals` 帶 category、前端可依分類過濾。本輪**不同時做 launchd**（US backfill 續手動）。
- **Goal:** 逐步接近台股「可解釋觀察」廣度，但仍非推薦 / 非買賣 / 非下單。
- **Completed:**
  - `us_leaders.json`：6 → 27 檔（ETF/Benchmark: SPY,QQQ,DIA,IWM；Mega-cap Tech: AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA；Semiconductors/AI: AMD,AVGO,TSM,ASML,MU,ARM；Software/Cloud: CRM,ORCL,NOW,SNOW,PLTR；Defensive/Consumer: COST,WMT,MCD,KO,PG），每檔帶 `category`。此檔為 curated 輸入、在 `.gitignore` allowlist 內 → 會 commit。
  - `load_us_leaders()` 帶出 `category`（缺欄位 → ""）；`get_us_universe` / `get_us_analysis` / `get_us_watch_signals` 每筆帶 `category`。router 維持純 HTTP、回 dict（無 response_model 需改）。
  - 前端：`UsUniverseItem` / `UsAnalysisItem` / `UsWatchSignalItem` 加 `category`；`UsMarketPage` 兩張表加「分類」欄 + 分類過濾 chip（單一 `categoryFilter` 同時過濾技術狀態表與觀察訊號表）；`.us-cat-filter` / `.us-cat-chip` / `.us-cat-tag` CSS。
  - 測試：更新 `test_us_watch_signals.py`（訊號數 = leaders 數、含 category 欄位）、`test_us_market.py`（universe schema 含 category + 新增 `test_us_universe_expanded_with_categories`）。
- **Changed Files:** `backend/data/us_leaders.json`、`backend/app/storage/us_market_store.py`、`backend/app/services/us_market_service.py`、`backend/app/services/us_analysis_service.py`、`backend/app/services/us_watch_signal_service.py`、`backend/tests/test_us_market.py`、`backend/tests/test_us_watch_signals.py`、`backend/docs/api.md`、`frontend/src/types/index.ts`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`；docs（roadmap / current-status / handoff-log）。
- **Validation:** `python3.11 -m pytest -q` → **858 passed**（+1）；`npm run build` → 成功。新 ticker 的真實 OHLCV **尚未回補**（需本機 `python3.11 scripts/backfill_ohlcv_us.py --months 12`）；未補前 UI 誠實顯示新 ticker「資料不足」（weak_or_no_data / avoid_weak）。
- **Git Status:** feat + docs 待 commit。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 本機補齊 27 檔真實資料；之後候選：完整 NYSE 假日曆 + launchd 排程 US backfill、Finnhub optional、再擴 universe。**仍不做美股正式推薦 / 買賣 / 下單。**
- **Notes / Warnings:** `category` 僅為**觀察分組**（非產業標準分類、非推薦）。`ohlcv_us.csv` 仍為本機真實資料、gitignored、不 commit。**不改台股主流程；不套台股策略；本輪未做 launchd。**

---

## 2026-07-10 — US Phase 3：美股觀察訊號（非推薦、非買賣建議）

- **Date:** 2026-07-10
- **Task:** 在 Phase 2 指標上做美股觀察訊號（描述性）+ SPY/QQQ 大盤基準，逐步接近台股「可解釋觀察」程度；不做推薦 / 買賣 / 下單 / 不套台股策略。
- **Goal:** 美股頁能看「觀察訊號 + 理由 + 風險 + 優先度」，但明確非推薦。
- **Completed:**
  - `us_watch_signal_service`：`derive_watch_signal`（純函式，五種訊號：watch_breakout / watch_pullback / trend_up / overheated / avoid_weak）+ `_market_context`（SPY/QQQ 相對 MA60 → market_bias）。複用 Phase 2 指標、自帶 20 日高，**不耦合 signals_service、不套台股策略**。
  - `GET /api/markets/us/signals`：回 `market_bias` / `market_note` / `benchmarks` / `signals[]`（code/name/close/status/signal/reasons/risk_notes/priority/data_as_of，依 priority 排序）；無資料 → 全 avoid_weak / market_bias=unknown。
  - 前端 `UsMarketPage` 新增「觀察訊號」區塊（訊號 badge + priority + reasons + risk）。
  - 測試 `test_us_watch_signals.py`：五種訊號規則、大盤基準、fixture 端到端、no-data 誠實、endpoint schema。
- **Changed Files:** 新增 `backend/app/services/us_watch_signal_service.py`、`backend/tests/test_us_watch_signals.py`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`、`frontend/src/types/index.ts`、`frontend/src/api/client.ts`；docs（roadmap / current-status / handoff-log / validation）。
- **Validation:** `python3.11 -m pytest -q` → **857 passed**（+14）；`npm run build` → 成功；實測（真實資料）`/markets/us/signals`：market_bias=bullish、AAPL/SPY watch_breakout(prio 80)、QQQ/TSLA trend_up、MSFT/NVDA avoid_weak；前端「觀察訊號」區塊顯示正常、無 console error。
- **Git Status:** feat + docs 待 commit。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 逐步接近台股：完整 NYSE 假日曆 / 自動排程 US backfill、universe 擴充、Finnhub optional。**仍不做美股正式推薦 / 買賣 / 下單。**
- **Notes / Warnings:** `signal` / `priority` 為觀察用、**非推薦、非買賣、非下單**；別升級成推薦桶或加買賣訊號。`ohlcv_us.csv` 本機真實資料、gitignored、不 commit。

---

## 2026-07-10 — US 資料新鮮度（最小收尾切片）

- **Date:** 2026-07-10
- **Task:** US 資料更新流程小收尾——在 `/api/markets/us/status` 加資料新鮮度，前端美股頁顯示；weekend-aware、容忍 1 個交易日、不做完整 NYSE 假日曆。
- **Goal:** 讓「US 資料是否過期」誠實可見（US backfill 手動、無排程，需訊號提醒重跑）。
- **Completed:**
  - `us_market_service`：新增 `compute_us_freshness`——複用既有 `is_trading_day` / `previous_trading_day` / `count_missed_trading_days_since`，**傳空 calendar（weekend-only，不套台股假日）**；以 `America/New_York` 取「今天」。`/markets/us/status` 加 `expected_trading_day` / `days_since_last`（交易日數）/ `is_stale`。
  - stale 判斷：`last_data_as_of` 缺失 → stale；否則落後 > 1 個交易日 → stale（容忍 1 日避免收盤前誤判）。
  - 前端 `UsMarketPage`：非 stale 顯示「資料日 X（N 個交易日前 / 最新）」；stale 顯示琥珀 banner + 重跑 backfill 提示。
  - api.md 更新 status 範例與欄位說明。
  - 未碰台股；未做策略 / 推薦 / 下單；未做 check_us_ohlcv.py；未把 US status 塞進台股 Dashboard；未做 US launchd。
- **Changed Files:** `backend/app/services/us_market_service.py`、`backend/tests/test_us_market.py`、`backend/docs/api.md`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`、`frontend/src/types/index.ts`、docs（current-status / handoff-log）。
- **Validation:** `python3.11 -m pytest -q` → **843 passed**（+5 新鮮度測試，固定 today 求確定性）；`npm run build` → 成功；實測 `/markets/us/status`（真實資料）：`last_data_as_of=2026-07-09`、`expected_trading_day=2026-07-10`、`days_since_last=1`、`is_stale=false`；前端顯示「資料日 2026-07-09（1 個交易日前）」、無 console error。
- **Git Status:** feat + docs 待 commit。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** US 資料流小收尾完成。後續（未做）：完整 NYSE 假日曆 / 自動排程 US backfill（另評估）；仍不做策略。
- **Notes / Warnings:** 新鮮度**不含 NYSE 假日**（週末感知即可）；stale banner 的視覺在本輪未親眼驗證（真實資料僅落後 1 日，未達 stale），但 is_stale 邏輯有單元測試、banner 沿用既有 alert-stale 標記。

---

## 2026-07-10 — Yahoo 真實資料端到端驗收通過 + python3.11 指令修正

- **Date:** 2026-07-10
- **Task:** AI 自行做 US Yahoo Finance 真實資料驗收（不等使用者本機），並把美股 backfill 指令由 `python3` 修為 `python3.11`。
- **Goal:** 確認 YahooFinancePriceSource + backfill 能實際產生 `ohlcv_us.csv` 並讓 API / 前端顯示真實資料。
- **Completed（真實驗收，非 mock）:**
  - `python3.11 scripts/backfill_ohlcv_us.py --months 12` **成功**：六檔 AAPL/MSFT/NVDA/TSLA/SPY/QQQ **各 255 rows、total 1530**；`last_data_as_of=2026-07-09`。
  - `/api/markets/us/status` → `tickers_with_data=6`、`source_label=Yahoo Finance…`。
  - `/api/markets/us/analysis` → 六檔皆有 MA20/MA60/RSI/status（3 trend_up、3 weak_or_no_data）。
  - 前端美股頁顯示真實收盤/資料日/指標/狀態 badge，「資料尚未更新」消失、無 console error。
  - `python3.11 -m pytest -q` → **838 passed**（含真實 `ohlcv_us.csv` 存在時）；`npm run build` → 成功。
  - 修正：所有美股 backfill 指令 `python3` → `python3.11`（`us_market_service.status.backfill_command`、`api.md`、backfill 腳本 docstring、validation / current-status）。**本機 `python3`=3.9 無法 import 後端（缺依賴 + `X|None` 需 3.10+）。**
- **Changed Files:** `backend/app/services/us_market_service.py`（backfill_command → python3.11，API 輸出）、`backend/docs/api.md`、`backend/scripts/backfill_ohlcv_us.py`（docstring）、`docs/ai/validation.md`、`docs/ai/current-status.md`、`docs/ai/handoff-log.md`。
- **Validation:** 動到 `backfill_command`（API 輸出）→ 跑 `python3.11 -m pytest -q` = 838 passed。
- **Git Status:** 待 commit（docs/status + 一處 API 字串）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** US 資料流可用；後續候選（交易日曆/時區、universe 擴充、Finnhub optional）仍不做策略/下單。
- **Notes / Warnings:** `ohlcv_us.csv` 是本機真實資料、**gitignored、不 commit**。US backfill 一律用 `python3.11`。未改 Yahoo source 的 round 行為（close 仍為原始 float 精度）。

---

## 2026-07-10 — US 資料源改用 Yahoo Finance（Stooq 停用）

- **Date:** 2026-07-10
- **Task:** 使用者本機實測發現 Stooq 已改為需瀏覽器 JS 驗證（回 HTML「requires JavaScript to verify your browser」，非 CSV）。改資料源方向：Stooq 停用、改用 Yahoo Finance chart endpoint 為 US 主源。
- **Goal:** 免 key 就能抓真實美股歷史日 OHLCV；不繞過 Stooq 驗證；不改台股、不做策略。
- **Completed:**
  - `YahooFinancePriceSource`（新 US 主源，免 key）：`GET /v8/finance/chart/{ticker}?interval=1d&period1&period2` → 解析 timestamp + indicators.quote → 既有 OHLCV；缺值列跳過；429/HTTP/JSON/error 處理。registry `US` → Yahoo。
  - `StooqPriceSource` **停用**：`is_available()=False`、`fetch_ohlcv` 丟 `PriceSourceUnavailable`（不繞過 JS 驗證）；保留類別供參考。
  - `backfill_ohlcv_us.py` 仍 source-agnostic（`get_price_source("US")`），無邏輯改動、文案更新。
  - 測試：移除 Stooq 解析測試，改測「Stooq 已停用」；新增 Yahoo JSON 解析 / null 跳過 / 空結果 / error mock；status 測試改 Yahoo label。
  - docs（roadmap / current-status / handoff-log / validation / api.md）改標主源 = Yahoo、Stooq 停用、Finnhub optional。
- **Changed Files:** `backend/app/services/price_source.py`、`backend/scripts/backfill_ohlcv_us.py`、`backend/tests/test_markets_scaffold.py`、`backend/tests/test_us_market.py`、`backend/docs/api.md`；docs（roadmap / current-status / handoff-log / validation）。**前端未改**（source-agnostic，讀 `source_label`）。
- **Validation:** `python3.11 -m pytest -q` → **838 passed**；`npm run build` → 成功；`/api/markets/us/status` → `source_label=Yahoo Finance…`。**未實測真實 Yahoo 抓取**（sandbox 自簽憑證代理阻擋 HTTPS，Yahoo 解析全用 mock）。
- **Git Status:** feat + docs 待 commit（HEAD `52a0dfc`）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 使用者本機 `backfill_ohlcv_us.py --months 12`（免 key）實測真實 Yahoo 資料。
- **Notes / Warnings:** Yahoo 為**非官方 endpoint**、無 SLA、可能變動 / 被限流；**不要繞過 Stooq JS 驗證**；資料仍只寫 `ohlcv_us.csv`。

---

## 2026-07-10 — US Phase 2：美股基本技術狀態（非策略、非買賣建議）

- **Date:** 2026-07-10
- **Task:** 在美股資料流上做基本技術狀態呈現：MA20/MA60/RSI14/20日漲跌幅/距均線/新鮮度 + 描述性狀態；不套兩策略、不做買賣建議、不下單、不改台股。
- **Goal:** 讓美股頁能快速看基本技術狀態；AI 用 fixture 自行驗收，真實資料留給使用者本機。
- **Completed:**
  - `backend/app/services/us_analysis_service.py`：自帶輕量指標（`_sma`/`_rsi`/`_pct_change`/`_dist_pct`/`_days_since`）+ `classify_status`（trend_up / pullback_watch / overheated / weak_or_no_data）。**不耦合 signals_service。**
  - `GET /api/markets/us/analysis`（`app/routers/markets.py`）。
  - 前端 `UsMarketPage` 顯示指標 + 狀態 badge（顏色分四種），附「非買賣建議、非策略、無下單」聲明。
  - 測試 `test_us_analysis.py`：指標數學、四種狀態分類（受控輸入）、fixture 端到端、endpoint schema。
- **Changed Files:** 新增 `backend/app/services/us_analysis_service.py`、`backend/tests/test_us_analysis.py`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`、`frontend/src/types/index.ts`、`frontend/src/api/client.ts`；docs（roadmap / current-status / handoff-log / validation）。
- **Validation（兩層）:**
  - **AI 已驗收**：`python3.11 -m pytest -q` → **837 passed**；`npm run build` → 成功；用 fixture `ohlcv_us.csv`（AAPL 65 列）實測 analysis API 算出指標並歸類 overheated，前端顯示指標 + badge，無資料 ticker 顯示弱勢/資料不足；台股不受影響、無 console error；**fixture 已刪除（gitignored）**。
  - **需使用者本機（真實 Stooq）**：真正回補 → `ohlcv_us.csv` 產生 → `/api/markets/us/status` `tickers_with_data>0` → 前端顯示真實收盤 / 資料日 / 指標。
- **Git Status:** 本階段 feat + docs 待 commit（HEAD `3633ad0`）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 使用者本機真實回補驗收；之後 US 候選（交易日曆/時區、universe 擴充、Finnhub optional）仍不做策略 / 下單。
- **Notes / Warnings:** `status` 為描述性技術狀態、非買賣建議；勿升級成推薦桶或加買賣訊號。

---

## 2026-07-10 — US Phase 1 資料源改用 Stooq（免 API key）

- **Date:** 2026-07-10
- **Task:** 依使用者確認的方向，把 US Phase 1 主資料源從 Finnhub 改為 **Stooq（免 API key）**；Finnhub 降為 future optional。
- **Goal:** 免 key 就能抓真實美股歷史日 OHLCV；台股 baseline 不破、不加美股策略。
- **Completed:**
  - `StooqPriceSource`（新 US 主源，免 key）：抓歷史日 OHLCV CSV，`.us` 後綴、限流 / no-data / 非預期格式處理；SSL context 對齊 TWSE backfill（certifi）。registry `US` → Stooq。
  - `FinnhubPriceSource` 保留為 optional，移出 US registry。
  - `backfill_ohlcv_us.py` 改 source-agnostic（走 `get_price_source("US")`），移除 Finnhub 專屬的 candle→quote fallback / `--quote-only`。
  - `us_market_service.status`：Stooq 免 key → `source_configured` 恆 true、`source_label=Stooq（美股）`。
  - 前端 `UsMarketPage` 的「未就緒」文案改為 source-agnostic（不再寫死 FINNHUB_API_KEY）。
  - 測試：`test_markets_scaffold` / `test_us_market` 更新（US 免 key 可用、`available_regions()=["TW","US"]`）+ 新增 Stooq 解析 / 限流 / no-data mock。
- **Changed Files:** `backend/app/services/price_source.py`、`backend/scripts/backfill_ohlcv_us.py`、`backend/tests/test_markets_scaffold.py`、`backend/tests/test_us_market.py`、`backend/docs/api.md`、`frontend/src/pages/UsMarketPage.tsx`、docs（roadmap / current-status / handoff-log / validation）。
- **Validation:** `python3.11 -m pytest -q` → **825 passed**；`npm run build` → 成功；`/api/markets/us/status` → `source_configured=true` / Stooq；瀏覽器美股頁「資料尚未更新」、切回台股復原、無 console error。**未實測真實 Stooq 抓取**（sandbox 自簽憑證代理無法連外，錯誤有優雅降級）。
- **Git Status:** 開始前乾淨（HEAD `562fdb5`）；本階段 feat + docs 待 commit。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 在能對外的環境跑 `backfill_ohlcv_us.py --months 1`（免 key）確認 `ohlcv_us.csv` 有資料 + 前端顯示收盤價；US Phase 2 另議。
- **Notes / Warnings:** Stooq 非正式來源、無 SLA、重度抓取可能被限流/擋 → 節流、少量、EOD、個人用途；勿把美股資料混進台股 `ohlcv.csv` / `leaders.json`。

---

## 2026-07-10 — US Market Phase 1：接真實美股資料流 + 基本呈現

- **Date:** 2026-07-10
- **Task:** 美股 Phase 1——接 Finnhub 資料源、US universe、US backfill、US 唯讀 API、前端美股頁；只做清單/基本行情，不做策略/下單，不改台股主流程。
- **Goal:** 讓美股資料能真正抓進來並呈現；缺 key 誠實顯示；台股 baseline 不破。
- **Completed:**
  - key：`config.resolve_finnhub_api_key`（讀 `FINNHUB_API_KEY`，不進 git，缺 key 明確錯誤）。
  - 資料源：`FinnhubPriceSource`（取代 US stub）——`/stock/candle` + `/quote`、401/403/429/缺 key 錯誤處理，HTTP 走 stdlib `urllib`（**未加依賴**）。
  - US universe：`backend/data/us_leaders.json`（AAPL/MSFT/NVDA/TSLA/SPY/QQQ）；`.gitignore` 加 `!backend/data/us_leaders.json`。
  - backfill：`backend/scripts/backfill_ohlcv_us.py`（獨立可跑，候補 candle→quote fallback、節流、去重）→ 寫**獨立** `ohlcv_us.csv`（**不動台股 ohlcv.csv**）。
  - API：`GET /api/markets/us/universe`、`/api/markets/us/status`（`app/routers/markets.py`，於 `main.py` 註冊；api.md 同步 → drift guard 綠）。
  - 前端：market toggle 啟用；`UsMarketPage` 只列清單/基本行情，缺 key/無資料誠實顯示；US 視圖與台股 nav 完全隔離。
  - 規格：`roadmap.md` 新增「US Market — Phase 1」Purpose/Scope/Acceptance。
- **Changed Files:**
  - 新增：`backend/app/services/us_market_service.py`、`backend/app/storage/us_market_store.py`、`backend/app/routers/markets.py`、`backend/scripts/backfill_ohlcv_us.py`、`backend/data/us_leaders.json`、`backend/tests/test_us_market.py`、`frontend/src/pages/UsMarketPage.tsx`。
  - 修改：`backend/app/config.py`、`backend/app/services/price_source.py`、`backend/app/main.py`、`backend/tests/test_markets_scaffold.py`、`backend/docs/api.md`、`.gitignore`；`frontend/src/App.tsx`、`App.css`、`types/index.ts`、`api/client.ts`；docs（roadmap / current-status / handoff-log / validation）。
- **Validation:** `python3.11 -m pytest -q` → **820 passed**（809 + 11 US，含缺 key 行為 + Finnhub 解析 mock，不打真網路）；`npm run build` → 成功；API 實測（US status source_configured=false、6 檔 region=US；台股 76 檔 region=TW 不變）；瀏覽器實測美股頁誠實狀態 + 切回台股完全復原、無 console error。**無 key 環境下驗收全綠。**
- **Git Status:** 開始前工作樹乾淨（HEAD `f65867b`）；本階段程式待 commit（feat）+ docs（另一 commit 或同 commit，見回報）。
- **Commit:** 見完成回報（驗收全綠後 local commit）。**未 push。**
- **Next Steps:** 使用者提供 `FINNHUB_API_KEY` → 跑 `backfill_ohlcv_us.py` 抓 1–2 檔實測；US Phase 2（美股訊號 / 交易日曆時區 / universe 擴充）另議。
- **Notes / Warnings:** Finnhub 免費層 candle 端點需付費（403），backfill 會自動 fallback 到免費 `/quote`（單日快照）；歷史回補需付費 key。美股資料一律走 `ohlcv_us.csv` / `us_leaders.json`，勿混入台股檔。

---

## 2026-07-10 — US market 骨架落地（不接真資料）

- **Date:** 2026-07-10
- **Task:** 為「加美股」建立骨架：region 維度 + price-source adapter seam + 前端 market toggle 預留；不接真資料、不改台股行為、不套策略。
- **Goal:** 讓美股之後能掛進來，而台股主流程零改動；把「資料從哪來」的 seam 先立好。
- **Completed:**
  - region 維度（TW/US）：`backend/app/services/markets.py`（`SUPPORTED_MARKETS`、`classify_region`）；`get_universe()` 每筆帶 `region`，現有台股皆 TW。
  - price-source adapter seam：`backend/app/services/price_source.py`（`PriceSource` 介面 + `TwsePriceSource` + `UsPriceSourceStub` + registry）。
  - TW 既有流程維持不動：`TwsePriceSource.is_available()=True` 但 `fetch_ohlcv()` 刻意丟錯（seam，尚未接管）；台股仍走既有 backfill script。
  - US stub：`UsPriceSourceStub.is_available()=False`、`fetch_ohlcv()` 丟 `PriceSourceUnavailable`。
  - 前端 market toggle 預留：header 右上「台股 / 美股·即將推出」，US disabled、不接資料流。
  - 未把 old_wang / steady_momentum 套到美股。
- **Changed Files:**
  - 新增：`backend/app/services/markets.py`、`backend/app/services/price_source.py`、`backend/tests/test_markets_scaffold.py`。
  - 修改：`backend/app/services/signals_service.py`（get_universe 加 region）、`frontend/src/App.tsx`（region state + toggle）、`frontend/src/App.css`（header flex + toggle 樣式）、`frontend/src/types/index.ts`（`region?`）。
- **Validation:** `python3.11 -m pytest -q` → **809 passed**（794 + 15 scaffold）；`npm run build` → 成功；`/api/stocks/universe` 76 筆全 `region: TW`；瀏覽器實測 toggle（US disabled、台股正常、無 console error）。
- **Git Status:** scaffold 已 commit `6ed907a`（1 個 feat commit）；本紀錄與 current-status 為另一個 docs commit（hash 見完成回報）。工作樹乾淨。
- **Commit:** `6ed907a`（scaffold）；docs 更新 commit `docs: record US market scaffold in AI status`（hash 見回報）。**未 push。**
- **Next Steps:** **明確依賴 Finnhub（或其他來源）API key** 才能接真實美股資料流。拿到後依序接：config/.env 放 key → `price_source` 實作 Finnhub → 新增 `backfill_ohlcv_us.py` → `markets.py` 開 US enabled + region 持久化 → US universe → 前端啟用 toggle + 依 region 過濾 → 交易日曆/時區分 region。
- **Notes / Warnings:** `TwsePriceSource.fetch_ohlcv()` 刻意丟錯是 seam 設計、`test_markets_scaffold.py` 有斷言；若之後讓 TW adapter 真的接管抓取，需同步改該測試（非 bug）。

---

## 2026-07-09 — 驗證並 commit heartbeat / UX 批次

- **Date:** 2026-07-09
- **Task:** 對前幾輪 heartbeat / UX 未提交變更做整合驗證，通過後 commit 成乾淨 baseline，並更新 AI 狀態文件。
- **Goal:** 在開始「加美股」大功能前，讓現有工作有已驗證、可回溯的基準。
- **Completed:**
  - 整批驗收：`python3.11 -m pytest -q` → **794 passed**；`npm run build` → 成功。
  - 分 2 個邏輯 commit 落地：`b97807c`（後端 docs 同步 + drift guards）、`96694ba`（前端研究頁 UX + API 失敗可觀測性）。
  - 更新 `current-status.md`（Latest Verified State → verified）與本紀錄。
- **Changed Files:**
  - 後端：`README.md`、`backend/docs/{api,architecture,signal_rules,status_overview}.md`、`backend/tests/test_api_docs.py`、`backend/tests/test_docs_consistency.py`。
  - 前端：`frontend/vite.config.ts`、`frontend/src/App.{tsx,css}`、`frontend/src/components/AnalysisRail.tsx`、`frontend/src/pages/{AnalysisPage,Dashboard,WatchlistsPage}.tsx`。
  - 文件：`docs/ai/current-status.md`、`docs/ai/handoff-log.md`。
- **Validation:** 後端 `python3.11 -m pytest -q` → 794 passed（2m22s）；前端 `npm run build` → 成功（tsc + vite）。前端動線以瀏覽器實測。
- **Git Status:** 開始前僅有本批 heartbeat/UX 改動，無無關檔案；分 3 commit（含本 docs commit）落地後工作樹乾淨。
- **Commit:** `b97807c`、`96694ba`，以及本次 docs commit `docs: mark heartbeat/UX batch verified`（hash 見完成回報）。**未 push。**
- **Next Steps:** 規劃 US market 新 phase（資料源 Finnhub、universe 分池、交易日曆/時區、第一版是否套策略）；`connectionLost` 抽共用 hook。
- **Notes / Warnings:** 後端測試需以 `python3.11` 執行（依賴僅裝在該 interpreter）。

---

## 2026-07-09 — 導入 AI Project Handoff Standard

- **Date:** 2026-07-09
- **Task:** 把 `~/Desktop/code/ai-project-standards` 的 AI Project Handoff Standard 套用到 new_stock repo。
- **Goal:** 讓本專案遵守統一的 AI 開發規則、進度紀錄、roadmap 與 handoff 流程（docs-only）。
- **Completed:**
  - 以標準版 `AGENTS.md` 取代 repo root 既有 AGENTS.md（新版為 handoff 入口，並指向 `CLAUDE.md` 保留原有詳細協作規範，未動 `CLAUDE.md`）。
  - 依 repo 實際內容補齊 `docs/ai/`：`project-brief.md`、`current-status.md`、`roadmap.md`、`validation.md`、`handoff-log.md`。
  - 校正兩處與任務 brief 的落差，以 repo 為準：後端 port 是 **19000**（非 9000）；前端 build 是 **`npm run build`**（非 `pnpm build`，repo 用 `package-lock.json`）；腳本路徑在 `backend/scripts/`。
- **Changed Files:**
  - `AGENTS.md` — 覆蓋為標準 handoff 入口（指向 docs/ai 與 CLAUDE.md）。
  - `docs/ai/project-brief.md` — 專案定位、技術棧、port、重要檔案、non-goals、constraints。
  - `docs/ai/current-status.md` — 目前階段、完成 / 進行中 / 風險、Do Not Redo、最新驗證狀態。
  - `docs/ai/roadmap.md` — Vision/Now/Next/Later/Backlog/Open Questions + 6 個 phase。
  - `docs/ai/validation.md` — 驗收指令（以 repo 為準）與回報規範。
  - `docs/ai/handoff-log.md` — 本筆紀錄。
- **Validation:** **Docs-only，未跑測試（pytest / build 皆未執行）。** 依 `validation.md` 的 Docs-only Rules，不需跑完整套件；本 repo 無 markdown lint。
- **Git Status:** 開始前工作樹**不乾淨**：有前幾輪 heartbeat / UX 的未提交改動（`README.md`、`backend/docs/*`、`frontend/src/*`、`frontend/vite.config.ts`，以及未追蹤的 `backend/tests/test_api_docs.py`、`backend/tests/test_docs_consistency.py`、`frontend/src/components/AnalysisRail.tsx`）。本次**未觸碰**這些改動；commit 時只 stage `AGENTS.md` 與 `docs/ai/*`。
- **Commit:** 本次提交 `docs: add AI project handoff docs`（只含 AGENTS.md 與 docs/ai/*）；hash 見完成回報。**未 push。**
- **Next Steps:**
  - 對前幾輪未提交的前端 / 文件改動做一次整合驗證（`python3.11 -m pytest -q` + `npm run build`）後再另行 commit。
  - 之後可把 `connectionLost` 連線偵測抽成共用 hook（單例探測）。
- **Notes / Warnings:**
  - 未提交的前端改動尚未整批回歸，Latest Verified State 標為 Pending（見 `current-status.md`）。
  - `AGENTS.md` 原本是與 `CLAUDE.md` 近似的詳細規範；已被標準入口取代，但 `CLAUDE.md` 保留完整詳規、未更動，新 `AGENTS.md` 有指向它。

---

<!-- 更早的紀錄接在下面 -->
