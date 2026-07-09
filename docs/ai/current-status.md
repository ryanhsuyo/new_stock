# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-10

## Current Phase

**US Market — Phase 1（接真實美股資料流 + 基本呈現）實作完成**（骨架 `6ed907a`；本階段程式待 commit）：Finnhub 資料源、US universe、US backfill、US 唯讀 API、前端美股頁都在。**只做清單 + 基本行情，不做美股策略 / 訊號 / 下單；台股主流程零改動。** 抓真實美股資料需設定 `FINNHUB_API_KEY`（缺 key 時前端誠實顯示「尚未設定資料源」）。

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
  - `FINNHUB_API_KEY` 讀取（`config.resolve_finnhub_api_key`，不進 git；缺 key 明確錯誤）。
  - `FinnhubPriceSource`（取代 US stub）：`/stock/candle` + `/quote`，錯誤/限流/缺 key 處理；HTTP 走 stdlib `urllib`（**未加依賴**）。
  - US universe：`backend/data/us_leaders.json`（AAPL/MSFT/NVDA/TSLA/SPY/QQQ，region=US）。
  - US backfill：`backend/scripts/backfill_ohlcv_us.py` → 寫**獨立** `ohlcv_us.csv`（**不動台股 ohlcv.csv**）。
  - US 唯讀 API：`GET /api/markets/us/universe`、`/api/markets/us/status`（`app/routers/markets.py`）。
  - 前端：market toggle 啟用；`UsMarketPage` 只列清單 + 基本行情，缺 key / 無資料時誠實顯示；台股主流程完全不受影響。

## In Progress

- US Phase 1 程式待 commit（本 session）；抓真實美股資料需 `FINNHUB_API_KEY`（使用者尚未提供）。
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

## Latest Verified State

- **Verified at: 2026-07-10**，commit `f65867b` 之後的 US Phase 1 工作樹（**尚未 commit**）。
- What was verified: `cd backend && python3.11 -m pytest -q` → **820 passed**（809 + 11 US 測試，含缺 key 行為 + Finnhub 解析 mock）；`cd frontend && npm run build` → 成功；`/api/markets/us/status` 回 `source_configured=false`、universe 6 筆 region=US；`/api/stocks/universe` 台股仍 76 筆 region=TW；瀏覽器實測美股頁（缺 key 誠實顯示、切回台股完全復原、無 console error）。
- 更早基準：`6ed907a`（2026-07-10，809 passed）、`b97807c` / `96694ba`（2026-07-09）。

## Next Recommended Task

- **US Phase 1 尚未 commit** —— 驗收全綠後先 local commit（不 push）。
- **抓真實美股資料需 `FINNHUB_API_KEY`**（使用者提供）：`export FINNHUB_API_KEY=<key>` 後 `python3 scripts/backfill_ohlcv_us.py --quote-only`（免費層）或不加旗標（candle，需付費層），驗證 `ohlcv_us.csv` 有資料、前端美股頁顯示收盤價。
- US Phase 2 候選（本階段刻意不做）：美股技術指標 / 訊號、交易日曆 / 時區分 region、US universe 擴充。
- 與美股無關：把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
