# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-09

## Current Phase

研究頁（AnalysisPage）UX 與前端可觀測性收尾（多輪 heartbeat 小改，目前**尚未 commit**），以及本次導入 AI Project Handoff Standard（docs-only）。

對應 roadmap 的「前端 dashboard usability」方向；後端資料流與兩策略推薦桶已穩定（見 `backend/docs/status_overview.md`）。

## Completed

> 已完成的事（後端多數已隨既有 commit 驗證；本 session 的前端改動為逐項驗證、尚未整批 commit）。

- 後端（已 commit，最新 commit `e6438b2`）：資料回補、兩策略推薦桶、universe_report、daily_check / today_scan、決策日誌、signal alerts、launchd 每日更新。
- 文件漂移修正（本 session，未 commit）：`backend/docs/api.md` 全端點索引 + `test_api_docs.py` guard；`test_docs_consistency.py`（擋已下線輸出檔名）；README / architecture / signal_rules 移除 buy_list/sell_list/hold_list。
- 前端研究頁（本 session，未 commit）：導覽分 4 組（今日/研究/投組/系統）、Dashboard 維運區摺疊、hash 路由（含 deep link）、研究頁左 rail（觀察/推薦/候選 + 策略切換 + 檢視過濾 + priority 排序 + ⟳）、加入觀察清單後 rail 自動刷新。
- 前端可觀測性（本 session，未 commit）：修 vite proxy 的 localhost→IPv6 問題（改 127.0.0.1）；初始載入失敗 `loadError` 橫幅；背景連線中斷偵測（去抖 + 自動恢復）。

## In Progress

- 本 session 的前端 / 文件改動**尚未整批 commit**，散落為未提交的 modified / untracked 檔案，需要一次整合驗證後再提交。
- 背景 polling 可觀測化剛完成，尚未在長時間 session 中觀察誤報率。

## Blocked / Risks

- 基本面避雷覆蓋率不足（真實外部資料尚未匯入）；`overall_status` 可能為 warn。不可用假數字補齊。
- 本 session 的未提交改動未經一次完整回歸（見下方 Latest Verified State）；下一步應整批驗證再 commit，避免遺漏。
- 後端依賴僅在本機 `python3.11` 安裝；用其他 interpreter 跑 pytest 會失敗（缺 fastapi 等）。

## Do Not Redo

> **已經做過、驗證過、不要重做**的事。

- 兩策略限制（`old_wang` / `steady_momentum`）已定案；不要在前端重算策略 / 分數 / 推薦桶。
- vite proxy 已改用 `127.0.0.1:19000`；**不要改回 `localhost`**（Node 會走 IPv6 連不到只綁 IPv4 的 uvicorn，整個 Dashboard 會變空白）。
- App 路由已改為「由 hash lazy-init state」以修 StrictMode 下 deep link 重整掉回首頁的問題；**不要改回 skip-first ref 的寫法**。
- rail 為研究頁 AnalysisPage 的 sibling（在 `{tab === 'analysis'}` 內），跨分頁會 remount 重抓；已知且刻意。

## Latest Verified State

> 誠實回報：本次為 docs-only 任務，未跑測試。

- **Latest Verified State: Pending verification in this session.**
- 說明：本次（AI handoff docs 導入）為 docs-only，未跑 pytest / build。本 session 先前的前端改動是**逐項**用瀏覽器 + `npm run build` 驗證過，但這些改動**尚未整批 commit、也未做一次完整 `pytest` 回歸**。最後一次已知的完整後端測試綠燈是在更早的 session（約 792 tests，對應當時狀態），不代表目前未提交的工作樹已整批驗證。
- Last commit: `e6438b2 Mark user-input-only workflow actions`（2026-07-06）。

## Next Recommended Task

- 對本 session 未提交的前端 / 文件改動做**一次整合驗證**：`cd backend && python3.11 -m pytest -q` 與 `cd frontend && npm run build`，通過後再 commit（與本次 docs commit 分開）。
- 之後可考慮把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
