# Handoff Log

> AI / 人在每次任務結束後的交接紀錄。這是給下一個接手者的摘要。

## 使用規則

- **最新紀錄放最上面**（append 在頂端，reverse-chronological）。
- 這是 **append-only 的歷史**：新增紀錄，不要改寫或刪除舊紀錄。
- 每筆只寫**可接手摘要**——不要貼完整聊天紀錄、完整 log、逐字對話。
- 每筆用下面的模板；沒有的欄位寫「N/A」，不要留白。
- 若狀態 / 規劃有變，除了在這裡記一筆，也要同步更新 `current-status.md` / `roadmap.md`。

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
