# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-10

## Current Phase

**US Market — Phase 2（美股基本技術狀態）完成**（本階段程式待 commit）。從 `ohlcv_us.csv` 算 MA20/MA60/RSI14/20日漲跌幅/距均線/新鮮度，產生描述性狀態（trend_up / pullback_watch / overheated / weak_or_no_data），`/api/markets/us/analysis` + 前端呈現。**非策略、非買賣建議、無下單；台股主流程零改動。** Phase 1（資料源 + 基本清單）已完成；**資料源主源改為 Yahoo Finance（免 key、非官方）**——Stooq 因改需瀏覽器 JS 驗證而停用，Finnhub 保留 optional。

後端資料流與兩策略推薦桶穩定（見 `backend/docs/status_overview.md`）；前端 dashboard usability 已收尾。

## Completed

> 已完成且已驗證的事。

- 後端核心（更早 commit）：資料回補、兩策略推薦桶、universe_report、daily_check / today_scan、決策日誌、signal alerts、launchd 每日更新。
- 文件漂移修正 + guard（commit `b97807c`）：`backend/docs/api.md` 全端點索引、`test_api_docs.py`、`test_docs_consistency.py`；README / architecture / signal_rules 移除 buy_list/sell_list/hold_list。
- 前端研究頁 UX + 可觀測性（commit `96694ba`）：導覽分 4 組、Dashboard 維運區摺疊、hash 路由（含 deep link）、研究頁左 rail（觀察/推薦/候選 + 策略切換 + 檢視過濾 + priority 排序 + ⟳）、加入觀察清單後 rail 自動刷新；vite proxy 改 127.0.0.1（修 IPv6）、`loadError` 載入失敗橫幅、背景連線中斷偵測（去抖 + 自動恢復）。
- US market 骨架（commit `6ed907a`）：
  - region 維度（TW/US）—— `markets.py`，在既有 exchange（TWSE/TPEX/ETF）之上；`get_universe()` 每筆帶 `region`，現有台股皆 TW。
  - price-source adapter seam —— `price_source.py`：`get_price_source(region)` + registry。
  - TW 既有流程維持不動 —— `TwsePriceSource.is_available()=True`（region 可用），但 `fetch_ohlcv()` 刻意丟錯（seam，尚未接管抓取）；台股資料仍走既有 `scripts/backfill_ohlcv_twse.py`。
  - US stub —— `UsPriceSourceStub.is_available()=False`、`fetch_ohlcv()` 丟 `PriceSourceUnavailable`（等來源）。
  - 前端 market toggle 預留 —— header 右上「台股 / 美股·即將推出」，US disabled、不接任何資料流。
  - 未把 old_wang / steady_momentum 套到美股。
- US Market Phase 1 資料流（本階段，程式待 commit）：
  - **主源 `YahooFinancePriceSource`（免 key、非官方）**：抓 `/v8/finance/chart/{ticker}` JSON → 轉 OHLCV；HTTP 走 stdlib `urllib`（**未加依賴**），SSL context 與 TWSE backfill 一致（certifi）。**Stooq 已停用**（需瀏覽器 JS 驗證，`is_available()=False`）。
  - **`FinnhubPriceSource` = optional**（讀 `FINNHUB_API_KEY`，不進 git，缺 key 明確錯誤），**不在 US registry**。
  - US universe：`backend/data/us_leaders.json`（AAPL/MSFT/NVDA/TSLA/SPY/QQQ，region=US）。
  - US backfill：`backend/scripts/backfill_ohlcv_us.py`（source-agnostic，走 `get_price_source("US")`）→ 寫**獨立** `ohlcv_us.csv`（**不動台股 ohlcv.csv**）。
  - US 唯讀 API：`GET /api/markets/us/universe`、`/api/markets/us/status`（`app/routers/markets.py`）。
  - 前端：market toggle 啟用；`UsMarketPage` 只列清單 + 基本行情，無資料時誠實顯示「尚未更新」；台股主流程完全不受影響。

- US Market Phase 2 基本技術狀態（本階段，程式待 commit）：
  - `us_analysis_service`（自帶 MA/RSI/漲跌幅/距均線/新鮮度指標，不耦合 signals_service）+ `classify_status`（四種描述性狀態）。
  - `GET /api/markets/us/analysis`；前端美股頁顯示指標 + 狀態 badge，附「非買賣建議」聲明。
  - **未套** old_wang / steady_momentum、無買賣建議、無下單。

## In Progress

- US Phase 1 + 2 程式待 commit（本 session）。
- 背景連線偵測剛上線，尚未在長時間 session 觀察誤報率。

## Blocked / Risks

- 基本面避雷覆蓋率不足（真實外部資料尚未匯入）；`overall_status` 可能為 warn。不可用假數字補齊。
- 後端依賴僅在本機 `python3.11` 安裝；用其他 interpreter 跑 pytest 會失敗（缺 fastapi 等）。

## Do Not Redo

> **已經做過、驗證過、不要重做**的事。

- 兩策略限制（`old_wang` / `steady_momentum`）已定案；不要在前端重算策略 / 分數 / 推薦桶。
- vite proxy 已改用 `127.0.0.1:19000`；**不要改回 `localhost`**（Node 會走 IPv6 連不到只綁 IPv4 的 uvicorn，整個 Dashboard 會變空白）。
- App 路由已改為「由 hash lazy-init state」以修 StrictMode 下 deep link 重整掉回首頁的問題；**不要改回 skip-first ref 的寫法**。
- rail 為研究頁 AnalysisPage 的 sibling（在 `{tab === 'analysis'}` 內），跨分頁會 remount 重抓；已知且刻意。
- US scaffold：`TwsePriceSource.fetch_ohlcv()` **刻意丟 `PriceSourceError`**（seam，不接管台股抓取），`test_markets_scaffold.py` 對此有斷言。要讓 TW adapter 真的接管抓取是**有意識的下一步**，屆時需同步更新該測試——不是 bug，別「順手修掉」。
- 美股 OHLCV 寫**獨立** `ohlcv_us.csv`、US universe 用**獨立** `us_leaders.json`；**不要把美股資料混進台股 `ohlcv.csv` / `leaders.json`**（會回歸台股流程）。
- 美股 Phase 1 **不做策略 / 訊號 / 推薦 / 下單**；別把 old_wang / steady_momentum 套到美股。
- US 主源 = **Yahoo Finance（免 key、非官方）**；registry `US` → `YahooFinancePriceSource`。**Stooq 已停用**（需瀏覽器 JS 驗證，**不要嘗試繞過**）；**Finnhub 保留 optional、不在 registry**。
- Yahoo 為**非官方 endpoint、無 SLA**：backfill 需節流、少量 ticker；被限流 / 錯誤要優雅降級（已有錯誤型別），別移除。
- 美股 Phase 2 的 `status`（trend_up / pullback_watch / overheated / weak_or_no_data）是**描述性技術狀態、非買賣建議**；`us_analysis_service` 自帶輕量指標、**不耦合 signals_service、不套兩策略**。別把它升級成推薦桶或加買賣訊號（除非明確要求）。

## Latest Verified State

- **Verified at: 2026-07-10**，Yahoo 資料源 + Phase 2 已 commit（`7c9fe4d` / `cd933ff`）。
- **真實 Yahoo 端到端已驗證通過**（AI 直接跑，非 mock）：`python3.11 scripts/backfill_ohlcv_us.py --months 12` 成功 → 六檔 AAPL/MSFT/NVDA/TSLA/SPY/QQQ **各 255 rows、total 1530**，`ohlcv_us.csv` 產生（本機資料、gitignored、未 commit），`last_data_as_of=2026-07-09`。`/api/markets/us/status` `tickers_with_data=6`；`/api/markets/us/analysis` 六檔皆有 MA20/MA60/RSI/status（3 檔 trend_up、3 檔 weak_or_no_data）；前端美股頁顯示真實收盤/資料日/指標/狀態 badge，「資料尚未更新」橫幅消失、無 console error。
- 測試 / build：`python3.11 -m pytest -q` → **838 passed**（含真實 `ohlcv_us.csv` 存在時亦綠）；`npm run build` → 成功。
- **執行注意**：US backfill 需以 **`python3.11`** 執行（本機 `python3`=3.9，無法 import 後端：缺依賴 + `X | None` 語法需 3.10+）。
- 更早基準：`bd5f4f0`/`52a0dfc`（Phase 2）、`6ed907a`（骨架）。

## Next Recommended Task

- 真實 Yahoo 驗收已過；US Phase 1+2 資料流可用。
- US 後續候選（未做）：交易日曆 / 時區分 region、US universe 擴充、Finnhub optional（quote / 即時 / 基本面）。**仍不做美股推薦策略 / 下單。**
- 與美股無關：把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
