# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-09

## Current Phase

heartbeat / UX 收尾已**驗證並 commit**（乾淨 baseline）。下一階段：規劃「US market（加美股）」新 phase（見 `roadmap.md`）。

對應 roadmap 的「前端 dashboard usability」方向已收尾；後端資料流與兩策略推薦桶穩定（見 `backend/docs/status_overview.md`）。

## Completed

> 已完成且已驗證的事。

- 後端核心（更早 commit）：資料回補、兩策略推薦桶、universe_report、daily_check / today_scan、決策日誌、signal alerts、launchd 每日更新。
- 文件漂移修正 + guard（commit `b97807c`）：`backend/docs/api.md` 全端點索引、`test_api_docs.py`、`test_docs_consistency.py`；README / architecture / signal_rules 移除 buy_list/sell_list/hold_list。
- 前端研究頁 UX + 可觀測性（commit `96694ba`）：導覽分 4 組、Dashboard 維運區摺疊、hash 路由（含 deep link）、研究頁左 rail（觀察/推薦/候選 + 策略切換 + 檢視過濾 + priority 排序 + ⟳）、加入觀察清單後 rail 自動刷新；vite proxy 改 127.0.0.1（修 IPv6）、`loadError` 載入失敗橫幅、背景連線中斷偵測（去抖 + 自動恢復）。

## In Progress

- 無進行中實作。下一步為 US market phase 的 scope 定義（尚未動手）。
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

## Latest Verified State

- **Verified at: 2026-07-09**，commits `b97807c`（後端 docs+guards）與 `96694ba`（前端 UX+可觀測性）。
- What was verified: 整批一起跑過 `cd backend && python3.11 -m pytest -q` → **794 passed**；`cd frontend && npm run build` → 成功（tsc + vite）。
- 前端互動流程於本 session 以瀏覽器逐項實測（Today→研究→切股→back/forward、deep link 重整、後端關閉時的錯誤/連線橫幅）。

## Next Recommended Task

- 規劃 **US market（加美股）新 phase** 的 scope（先定，再動手）：資料源（建議 Finnhub 優先、SEC EDGAR 補財報）、universe 分池（TW/US）、交易日曆/時區分離、第一版是否套策略（建議先只做行情+呈現）。
- 之後可考慮把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
