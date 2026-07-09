# Roadmap

> 專案的方向與規劃。用 Now / Next / Later 分層，細節放在各 Phase。
> 規劃改變時就更新這裡。
> Last updated: 2026-07-10

## Vision

打造一個**自用、可解釋、可信任**的股票決策工作台（台股為主，逐步納入美股）：資料流穩定跑通，訊號與候選股都能說明「為何買 / 為何不買 / 為何不是入場點」，前端只做呈現與決策動線；**不碰自動交易**。

## Now

> 現在正在做 / 即將做的（對應 `current-status.md` 的 Current Phase）。

- **US Market — Phase 2：美股基本技術狀態**（見下方 Phase 規格）。從 `ohlcv_us.csv` 算 MA/RSI/漲跌幅/距均線/新鮮度，產生描述性狀態（trend_up / pullback_watch / overheated / weak_or_no_data）並在前端呈現。**非策略、非買賣建議、無下單、不改台股主流程。** Phase 1（Stooq 資料源 + 基本清單）已完成。

## Next

> 接下來會做的（Now 完成後）。

- 把本 session 未提交的前端 / 文件改動整合驗證後 commit。
- 連線偵測 `connectionLost` 抽成共用 hook（單例探測）。
- 真實基本面資料匯入流程驗收（等外部 CSV）。

## Later

> 更遠、方向明確但尚未排程的。

- strategy / backtest / risk view 深化（單股回測已有基礎）。
- watchlist / alert 候選功能擴充（提醒、追蹤清單流程）。
- universe / signals 品質改善（型態新鮮度、趨勢線 anchors）。

## Backlog

> 想到但還沒排優先序的點子 / 待辦。

- CLAUDE.md / AGENTS.md 與 out 契約的長期一致性 guard。
- 前端頁面整併（投組總覽 + 持倉損益、推薦 + 候選）。
- 即時報價整合（目前用歷史收盤價）。
- K 線圖成交量子圖。

## Open Questions

> 尚未有答案、會影響規劃的問題。

- 何時能取得真實外部基本面資料以解除 `steady_momentum` 避雷覆蓋不足？
- rail 推薦策略是否要與 Dashboard 策略做跨頁同步（目前刻意低耦合）？

---

## Phases

> 每個 phase 都要有 Purpose / Scope / Acceptance Criteria。

### US Market — Phase 1：接真實美股資料流 + 基本呈現

**Purpose**
在**不破壞台股主流程、不做美股策略、不下單、不做即時交易決策**的前提下，把美股資料真正接進來並在前端做最基本的清單 / 行情呈現。延續 `6ed907a` 的 scaffold（region 維度、price-source adapter seam）。

**資料源方向（已確認）**：主源為 **Stooq（免 API key，直接抓歷史日 OHLCV CSV）**；**Finnhub 降為 future optional**（免費層歷史 candle 已改付費 403；保留供之後接 quote / 即時 / 基本面）。

**Scope**
- 包含：
  - `StooqPriceSource`（US Phase 1 主源，免 key）：抓歷史日 OHLCV，`.us` 後綴、解析、限流 / 非預期格式錯誤處理。走 stdlib `urllib`（無新依賴）。
  - `FinnhubPriceSource` 保留為 optional（讀 `FINNHUB_API_KEY`，缺 key 明確錯誤），**不在 US registry**。
  - 第一版小型 US universe（`backend/data/us_leaders.json`：AAPL / MSFT / NVDA / TSLA / SPY / QQQ），每筆標 `region: US`。
  - `backend/scripts/backfill_ohlcv_us.py`：source-agnostic（走 `get_price_source("US")`），寫入**獨立檔** `backend/data/ohlcv_us.csv`（**不寫台股 `ohlcv.csv`**，避免回歸）。
  - US universe / status 唯讀 API + 前端 US 清單（含「尚未就緒 / 尚未更新」誠實狀態）。
- **不包含（out of scope）**：
  - 美股策略（不套 old_wang / steady_momentum）。
  - 下單 / 自動交易 / 即時交易決策。
  - 改動台股 backfill 主流程、台股 `ohlcv.csv`、台股 `leaders.json`。
  - 美股技術分析 / 訊號 / 候選桶。

**Acceptance Criteria**
- [x] `cd backend && python3.11 -m pytest -q` 全綠（台股 baseline 不破，US 新測試涵蓋 Stooq 解析 / 限流 / no-data、Finnhub 缺 key）。
- [x] `cd frontend && npm run build` 成功。
- [x] US 主源 Stooq 免 key：`is_available()=True`、`source_configured=true`；`backfill_ohlcv_us.py` 免 key 可跑（實際抓取需正常對外網路；sandbox 因自簽憑證代理無法對外，錯誤有優雅降級）。
- [x] 前端 US toggle 可切換；US 視圖只做清單 / 基本行情，無資料時顯示「資料尚未更新」誠實訊息；台股主流程完全不受影響。
- [x] 台股 `ohlcv.csv` / `leaders.json` / 測試 baseline 不變（825 passed）。

### US Market — Phase 2：美股基本技術狀態

**Purpose**
在美股資料流之上，做**基本技術狀態呈現**（描述性），供快速看盤；**不做正式推薦策略、不做買賣建議、不下單**。

**Scope**
- 包含：
  - `us_analysis_service`：從 `ohlcv_us.csv` 算 MA20 / MA60 / RSI14 / 20 日漲跌幅 / 距 MA20、MA60 / 資料新鮮度（自帶輕量指標函式，不耦合 signals_service）。
  - 描述性狀態：`trend_up` / `pullback_watch` / `overheated` / `weak_or_no_data`。
  - `GET /api/markets/us/analysis` + 前端美股頁顯示指標與狀態 badge。
- **不包含（out of scope）**：
  - 套用 old_wang / steady_momentum 或任何台股推薦桶。
  - 買賣建議 / 進出場價 / 下單 / 交易決策。
  - 改動台股主流程。

**Acceptance Criteria（分兩層）**

AI 已驗收：
- [x] `python3.11 -m pytest -q` → 837 passed（含指標數學、四種狀態分類、fixture 端到端、endpoint schema）。
- [x] `npm run build` 成功。
- [x] API 在**無資料**時回 `weak_or_no_data` + 指標 null；用 **fixture `ohlcv_us.csv`** 時算出 MA/RSI/漲跌幅並歸類狀態。
- [x] 前端：缺資料誠實顯示、有資料顯示指標 + 狀態 badge（實測 fixture：AAPL 過熱 badge、其餘弱勢/資料不足）；台股主流程不受影響。

需使用者本機（真實 Stooq 資料）後續驗收：
- [ ] 真正連 Stooq 回補，`ohlcv_us.csv` 實際產生。
- [ ] `/api/markets/us/status` 顯示 `tickers_with_data > 0`。
- [ ] 前端美股頁顯示**真實**收盤價 / 資料日 / 指標 / 狀態。


### Phase 1: 資料更新穩定化

**Purpose**
確保 backfill → signals → out 檔案的每日資料流穩定、可重跑、可觀測，避免靜默失敗導致下游全錯。

**Scope**
- 包含：`daily_update.py` / `backfill_ohlcv_twse.py` / `update_all_data.py` 的節流、去重 merge、SKIP 說明、狀態檔（`update_status.json`）、排程健康度。
- 不包含：更換資料來源、即時報價。

**Acceptance Criteria**
- [ ] `python3 scripts/daily_update.py --months 1` 可完成並更新 `out/*` 與 `update_status.json`。
- [ ] 任何 SKIP / 錯誤都有 log 原因（代碼 / 月份 / 步驟）。
- [ ] `(code, date)` 去重、排序後寫回 CSV。

### Phase 2: universe / signals 改善

**Purpose**
提升訊號與候選股報表的正確性與可解釋性。

**Scope**
- 包含：7 狀態訊號、支撐壓力、趨勢線、型態、分數 + reasons/risk_notes、`universe_report.csv` 欄位（含 `data_ok` / `no_buy_reason`）。
- 不包含：新增第三個對外策略、複雜預測模型。

**Acceptance Criteria**
- [ ] 從固定測資可產生 signals 與 `summary.json` / `universe_report.csv`。
- [ ] 每檔可看出「為何進入某訊號分類」；不符合條件時能解釋原因。
- [ ] score 一定附 reasons / risk_notes。

### Phase 3: 前端 dashboard usability

**Purpose**
讓 dashboard / 研究頁的決策動線順、狀態可讀、失敗可觀測。

**Scope**
- 包含：導覽分組、Decision Console、研究頁 rail、hash 路由 / deep link、錯誤橫幅、連線偵測。
- 不包含：在前端重算策略 / 分數 / 推薦桶。

**Acceptance Criteria**
- [ ] `npm run build` 成功（含 `tsc`）。
- [ ] 主要動線（Today → 研究 → 切股 → back/forward、deep link 重整）行為一致。
- [ ] 後端不可用時有明確錯誤橫幅，與正常空狀態分開。

### Phase 4: strategy / backtest / risk view

**Purpose**
在不做自動交易的前提下，強化策略回測與風險視角。

**Scope**
- 包含：單股回測（已有 `backtest_service` / `run_backtest.py`）、風險欄位呈現。
- 不包含：自動下單、對外資金操作。

**Acceptance Criteria**
- [ ] 回測輸出含交易明細、回撤、與 buy-and-hold 比較。
- [ ] 風險資訊只呈現後端既有欄位，不在前端重算。

### Phase 5: watchlist / alert 候選功能

**Purpose**
擴充觀察清單與提醒候選，服務日常追蹤。

**Scope**
- 包含：watchlist CRUD、signal alert 檢視 / 確認、候選股復盤流程。
- 不包含：把 alert 變成自動交易觸發。

**Acceptance Criteria**
- [ ] watchlist CRUD 冪等、跨頁一致。
- [ ] alert 有人工檢視 / 確認的可觀測狀態。

### Phase 6（Non-goal 護欄）: 不直接做自動交易

**Purpose**
明確標記自動交易為**永久 non-goal**，避免任何 phase 順手做進去。

**Scope**
- 不包含：串接券商 API、自動下單、自動資金操作、把 AI 建議當成買賣指令。

**Acceptance Criteria**
- [ ] 全 repo 不含自動下單 / 券商交易觸發路徑。
- [ ] 文件與 UI 一律標示「僅供研究，非買賣指令」。
