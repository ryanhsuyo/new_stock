# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-10

## Current Phase

US market（加美股）**骨架已落地**（commit `6ed907a`）：region 維度、price-source adapter seam、前端 market toggle 預留都在，台股主流程零改動。**下一步接真實美股資料流，明確依賴一把 Finnhub（或其他來源）API key。**

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

## In Progress

- 無進行中實作。US 骨架已 commit；下一步等 Finnhub key 才能接真實美股資料流。
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
- US scaffold：`TwsePriceSource.fetch_ohlcv()` **刻意丟 `PriceSourceError`**（seam，本輪不接管台股抓取），`test_markets_scaffold.py` 對此有斷言。要讓 TW adapter 真的接管抓取是**有意識的下一步**，屆時需同步更新該測試——不是 bug，別「順手修掉」。

## Latest Verified State

- **Verified at: 2026-07-10**，commit `6ed907a`（US market 骨架）。
- What was verified: `cd backend && python3.11 -m pytest -q` → **809 passed**（794 + 15 scaffold）；`cd frontend && npm run build` → 成功（tsc + vite）；`/api/stocks/universe` 76 筆全部 `region: "TW"`；瀏覽器實測 market toggle（US disabled、台股主流程正常、無 console error）。
- 更早基準：commits `b97807c` / `96694ba`（2026-07-09，794 passed + build）。

## Next Recommended Task

> 明確依賴：**需要一把 Finnhub（或其他來源）API key** 才能接真實美股資料流。拿到後依序接：
1. `backend/app/config.py`（或 `.env`）放 `FINNHUB_API_KEY`（**不進 git**）。
2. `price_source.py`：`UsPriceSourceStub` → `FinnhubPriceSource.fetch_ohlcv()`（真 API + 節流 + 錯誤處理）。
3. 新增 `backend/scripts/backfill_ohlcv_us.py`（對稱於 TWSE 版），寫入 OHLCV 並更新 region/universe。
4. `markets.py`：把 US `enabled` 打開 + region 持久化（新 store 或擴充 `stock_markets.json`）。
5. `leaders.json`（或新 US universe 檔）放美股 ticker。
6. 前端啟用 market toggle，依 `region` 過濾清單（**仍只做行情+呈現，先不套策略**）。
7. 交易日曆 / 時區分 region（美股 ≠ 台股）。

- 與美股無關的待辦：把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
