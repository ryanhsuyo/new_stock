# Current Status

> 專案**現在**的狀態快照。改動狀態時就更新這裡。保持精簡、可接手。
> Last updated: 2026-07-19

## Current Phase

**策略驗證實驗室收斂（2026-07-17）**：補免責聲明與多重測試警語、TW 全窗口回放改背景執行（POST 觸發 + status 輪詢）、guardrail 交接（evaluation-only 邊界已被「可接 API 但須重用凍結規則 + 背景執行 + 警語」取代，詳 handoff-log 2026-07-17）。同輪：專案搬家至 `~/Developer/new_stock` 後 launchd 全斷已重灌修復（雙 agent 實測補跑成功）；盤前風險中心 WIP 以原樣落地（`8c65b20`）。

**修正輪：SPCX 納入 + launchd 排程失效診斷**（2026-07-13）。1) **更正事實錯誤**：SpaceX 已於 2026-06-12 IPO（NASDAQ: SPCX，史上最大 IPO）——先前文件寫「未上市」是 AI 知識截止造成的過時資訊，已 web 查證更正。SPCX 加入 `Defense / Aerospace`（universe 35 → 36），已回補（19 rows 起自 IPO 日；`insufficient_tickers=["SPCX"]` 是誠實顯示，約 2026-09 後才有 MA60，屆時自動進入分析）。2) **台股 07-10 確認臨時休市**（TWSE 全市場無該日資料；週五的 stale 警告是假警報）；07-13 資料已補、stale 解除。3) **launchd 排程已重建（使用者核准）**：根因是單一 15:30 觸發點 + `RunAtLoad=false`，機器在該時段關機就永久錯過（行事曆觸發跨重開機不補跑，07-06 後零自動執行）。新機制：`scripts/scheduled_update.py` wrapper + 兩個 agent（台股 `com.stockapp.daily-update` 目標 15:30；**美股新增** `com.stockapp.us-update` 目標 08:30）；plist 改 `RunAtLoad=true` + `StartInterval=3600`（開機時 + 每小時檢查），wrapper 規則「過了當日目標時間且尚未成功 → 跑；成功一次即止；失敗下個整點重試」——**錯過自動延後補跑**。已實測：launchd 端到端兩市場 exit 0、markers 寫入、重複觸發正確跳過。`setup_schedule.sh` / `remove_schedule.sh` 已改雙 agent 版（Python 預設優先 python3.11，避免系統 python 缺依賴）。**非推薦、非買賣建議、不下單。**

前一階段 **收尾輪：證據存檔 + 台股資料清理 + 文件除舊**（本階段待 commit）。1) 策略評估總帳 `docs/ai/strategy-evaluation-ledger.md`（7 個家族一張表 + 跨家族教訓 + 方法學標準）；台股 old_wang 回放正式化 `scripts/replay_tw_old_wang.py`（候選判定 = production 管線 as-of 截斷，兩套評估退出，排除企業行動污染 codes，可重現）。2) 台股 `ohlcv.csv` 清除 2009/2010/2017 髒列 284 筆（會讓均線把相隔多年的 bar 視為相鄰；已備份 `.bak-20260712`，本機檔不進 git）。3) 本檔陳舊段落除舊。**非推薦、非買賣建議、不下單。**

前一階段 **US universe 擴充：軍工航太 + AI 基礎設施（27 → 35 檔）**（`e5c582a`）。新增 `Defense / Aerospace`（LMT / RTX / NOC / GD / RKLB——當時寫「SpaceX 未上市」**是錯的**（實已於 2026-06-12 IPO），2026-07-13 已更正並納入 SPCX）與 `AI Infrastructure`（SMCI / VRT / CRWV）。已回補 5 年（新檔各 1,278 rows；CRWV 2025-03 IPO 為 322 rows，`min_row_count=322` 屬正常非缺資料）。既有 API / 兩套觀察策略 / 分類過濾全部動態承接，零程式改動（僅資料 + 文件）。實測：`tickers_with_data=35`、`missing/insufficient=[]`；RTX 進 trend-follow 候選 #1、GD 在 W 底突破觀察中。**非推薦、非買賣建議、不下單。**

前一階段 **美股第二套觀察策略 us_wbottom_target（W 底突破 + 量幅目標）上線**（`20eed0c`）。使用者以「所有測試中勝率最高（5 年 62.4%）」選定採用；`us_wbottom_service.py`（偵測 / 觀察輸出 / 回放**單一規則來源**，共用 `find_w_breakout`）、`GET /api/markets/us/strategy/w-bottom`（頸線 / 型態低=失效價 / 量幅目標 = **觀察用關鍵價位，非下單指令**；狀態機 forming → breakout_today/in_progress → target_reached/invalidated；無型態只計數，空清單是常態）、前端「策略觀察：W 底型態」區塊（位於 trend-follow 與觀察訊號之間）。**已知代價寫死在 UI/API**：高勝率≠高獲利（贏家封頂 +29%/最差 −27%）、2022 型空頭年平均 −5.87%、生存者折扣後 +0.48%/筆。參數凍結（2026-07-12），證據：`docs/ai/us-wbottom-replay-5y.md`。**非推薦、非買賣建議、不下單。**

前一階段 **us_wang_breakout 5 年回放驗證（evaluation-only）**（`34c4ade`）。突破+量能進場、MA10 波段、−8% 硬止損、SPY/QQQ 軟濾網；參數凍結後以 5 年資料（2021-06～2026-07，含 2022 空頭）樣本外重測。**機制層通過**（343 筆 +1.77%/筆、2022 空頭年濾網壓到 20 筆小虧、尾部不再單點依賴）；**edge 層被敏感度測試否定**——拿掉 NVDA/TSLA/AMD/MU/ARM 後 6 年有 5 年虧損（+607→+106 點，只剩 2024 為正），利潤主要是 2026 版 universe 的生存者偏差。**評級：不建議照此下單；可考慮做成第二套觀察策略。** 完整證據：`docs/ai/us-wang-breakout-replay-5y.md`。`ohlcv_us.csv` 已擴到 5 年（27 檔 33,961 rows，本機 gitignored）。**production 規則零改動、不下單、無參數最佳化。**

前一階段 **us_trend_follow 逐日回放驗證（evaluation-only）**（`136c865`）。`us_strategy_replay_service` + `scripts/replay_us_strategy.py`：walk-forward（as-of D 切片重算指標，測試證明無未來資料洩漏）、D+1 open 成交、兩套 evaluation-only 退出（candidate_exit / trend_protect_exit）比較，輸出 `backend/out/us_strategy_replay_*.{json,csv}`（gitignored）。結論見 `docs/ai/us-trend-follow-replay-2026-06.md`：**candidate_exit 證實太敏感**（平均持有 1.9 天、8/16 三日內再入選；主因 dist>8% 與 RSI<50 邊界被對稱當退出用）；trend_protect 結構較合理（9.3 天、再入選 1 次）；gate 本窗口全 bullish 未被壓力測試。**production 規則零改動、無參數最佳化、不下單。**

前一階段 **US 觀察策略第一套 us_trend_follow**（`bb5414c`）：大盤守門的趨勢延續觀察：`us_strategy_service`（純函式規則 + 聚合）、`GET /api/markets/us/strategy/trend-follow`（candidates/excluded 皆有 reasons、candidate 另有 risk_notes、rank 排序無分數）、前端「策略觀察：趨勢延續」區塊（gate 橫幅 / candidates 表 / excluded 摺疊「為何不在清單」）。守門：bullish 啟用、mixed 降 watch、bearish/unknown 誠實空清單（規則關門非故障）。**非推薦、非買賣建議、非下單、不套台股策略；第二套 us_pullback_watch 刻意未做。**

前一階段 **US 美股頁操作體驗完善**（資料狀態面板 + `#/us` deep link）已完成並 commit（`69bfc6a`）：
- **資料狀態面板**：美股頁頂部顯示資料源 / `tickers_with_data`/`universe_size` / 資料日（含 days_since_last、已過期 tag）/ `min_row_count` / `missing_tickers` / `insufficient_tickers`（非空時清楚列代碼）；資料完整時顯示「27/27 已更新，最少 256 筆」綠 pill。手動更新指令**只顯示**（`… --months 12`），無 run-backfill API、無自動回補。
- **hash deep link**：`#/us`（正準）與 `#/markets/us`（別名）直達美股頁；重整仍留在美股頁；header「台股/美股」切換同步 hash（美股→`#/us`、台股→原 tab path）；back/forward 正常。沿用既有 hash routing、未引 React Router；region 與 tab 一樣由 hash lazy-init（StrictMode-safe）。

前端純呈現（消費 `/status` 既有欄位，e323291 已提供），**未動後端**。**無策略 / 推薦 / 下單 / launchd；台股主流程零改動。**

前一階段 **US status 回補可觀測性**（missing/insufficient/min_row_count）已完成並 commit（`e323291`）。拆掉 `weak_or_no_data` 混合桶 → `no_data`（算不出指標）/ `weak`（跌破 MA60）/ `recovering`（站上 MA20 與 MA60 但 MA20 < MA60）；保留 trend_up / pullback_watch / overheated。`/api/markets/us/analysis` schema、前端 badge + 圖例同步更新；**watch signals 規則未動**（`/signals` 訊號分佈與修正前一致）。**不做 launchd / 策略 / 推薦 / 下單；台股主流程零改動。**

前一階段 **US universe 擴充 + 分類**（27 檔，真實 Yahoo 回補已驗收：每檔 256 筆、`tickers_with_data=27`、無資料不足）已完成並 commit（`2b2aaa7`）。`us_leaders.json` 擴到第一版 27 檔（ETF/Benchmark 4、Mega-cap Tech 7、Semiconductors/AI 6、Software/Cloud 5、Defensive/Consumer 5），每檔帶觀察用 `category`；`/universe`、`/analysis`、`/signals` 皆帶 `category`；前端美股頁加分類欄位 + 分類過濾 chip（同時過濾技術狀態表與觀察訊號表）。**仍非推薦、非買賣建議、無下單、不套台股策略；台股主流程零改動；本輪不做 launchd。** Phase 1（Yahoo 免 key 資料源）、Phase 2（基本技術狀態）、Phase 3（觀察訊號）、資料新鮮度皆已完成。

後端資料流與兩策略推薦桶穩定（見 `backend/docs/status_overview.md`）；前端 dashboard usability 已收尾。

## Completed

> 已完成且已驗證的事。

- 台股策略組合風控驗收（2026-07-19，evaluation-only）：定位到壓力窗口的主要問題是同日多筆新倉與總曝險集中，而非直接改策略分數；驗收回放加入歷史盤前風險 gate、策略別單檔／總曝險／每日新倉上限，且逐筆列出被略過候選。2026-07-08～07-15 合併模式由 −8.56%／MDD 11.52% 改善為 +0.64%／MDD 2.92%；較長區間合併為 +34.04%／7.55%（原 +34.30%／10.69%）。老王單策略採較寬 20%／80%／4 後，長區間 +31.98%／11.11%（原 +34.66%／14.81%，嚴格版僅 +24.91%／8.22%）；穩健動能放寬候選惡化至 +4.12%／18.51%，已拒絕並維持嚴格版 +12.97%／10.61%。目前仍不接 production，需更多樣本外驗證。完整回歸 **969 passed**，frontend build 成功。

- 盤前風險中心 MVP（2026-07-17）：新增 `GET /api/system/pre-market-risk`，以本機 SPY／QQQ／TSM 隔夜漲跌與最近人工市場筆記形成 `normal/watch/defensive/extreme/unknown` 可解釋分級；資料 stale 或不足兩個基準時固定 `unknown` 並暫停一般新倉提示，超過 3 天的舊事件筆記顯示但不計分。Dashboard 顯示觸發原因、建議最高曝險、官方 MOPS／台積電 IR／Fed／BLS 入口與「非崩盤預測」限制。未改兩策略、交易、持倉或 OHLCV。完整回歸 **958 passed**，frontend build 與桌面／375px 瀏覽器驗收通過。

- 台股「策略驗收」UI（2026-07-16）：`#/validation` 顯示 100 萬空手起始 walk-forward 投組回放，支援自選開始／結束日期後重新計算合併、老王、穩健動能三組獨立帳戶；個股損益貢獻、持有 / 平倉 / 盈虧篩選、逐筆訊號日→成交日時間線、費稅與原因，以及本機線圖 / TradingView 交叉核對。`GET /api/system/strategy-validation` 讀最近快照；`POST` 依區間完整重跑並快取，不是前端截斷既有交易。新增相關測試與真實 3 日 smoke test通過；frontend build 成功。2026-07-17 已移除四個測試對舊 repo 絕對路徑的依賴，全套回歸 **953 passed**。

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
- US Market Phase 1 資料流（已 commit `7c9fe4d`/`cd933ff`）：
  - **主源 `YahooFinancePriceSource`（免 key、非官方）**：抓 `/v8/finance/chart/{ticker}` JSON → 轉 OHLCV；HTTP 走 stdlib `urllib`（**未加依賴**），SSL context 與 TWSE backfill 一致（certifi）。**Stooq 已停用**（需瀏覽器 JS 驗證，`is_available()=False`）。
  - **`FinnhubPriceSource` = optional**（讀 `FINNHUB_API_KEY`，不進 git，缺 key 明確錯誤），**不在 US registry**。
  - US universe：`backend/data/us_leaders.json`（AAPL/MSFT/NVDA/TSLA/SPY/QQQ，region=US）。
  - US backfill：`backend/scripts/backfill_ohlcv_us.py`（source-agnostic，走 `get_price_source("US")`）→ 寫**獨立** `ohlcv_us.csv`（**不動台股 ohlcv.csv**）。
  - US 唯讀 API：`GET /api/markets/us/universe`、`/api/markets/us/status`（`app/routers/markets.py`）。
  - 前端：market toggle 啟用；`UsMarketPage` 只列清單 + 基本行情，無資料時誠實顯示「尚未更新」；台股主流程完全不受影響。

- US Market Phase 2 基本技術狀態（已 commit `bd5f4f0`/`52a0dfc`）：
  - `us_analysis_service`（自帶 MA/RSI/漲跌幅/距均線/新鮮度指標，不耦合 signals_service）+ `classify_status`（四種描述性狀態）。
  - `GET /api/markets/us/analysis`；前端美股頁顯示指標 + 狀態 badge，附「非買賣建議」聲明。
  - **未套** old_wang / steady_momentum、無買賣建議、無下單。

## In Progress

- US parity 主要研究與驗收動線已落地：美股具市場總覽、技術分析、region-aware 觀察清單、策略驗收與日期區間；可回放 `us_trend_follow` / `us_wbottom_target` 並顯示逐筆訊號、D+1 open 進出、持有日、報酬與 TradingView。US 口徑是逐筆等權評估，不冒充台股 100 萬投組。
- US parity Phase 1 核心已落地：新增 US 技術分析導覽與單股研究頁（120 根真實 OHLCV K 線、MA20/60、RSI、20 日漲跌、狀態、理由／風險、USD）；市場總覽 ticker 可直達研究頁。watchlist 股票身份改為 `(region, code)`，既有缺 region 資料相容視為 TW，美股可加入同一套群組且不覆寫／誤刪台股同代碼。
- US 研究動線續補：市場總覽、觀察訊號、trend-follow 入選／排除、W-bottom patterns 的 ticker 全部可直達 US 研究頁；US 導覽新增「觀察清單」，依 region 只顯示美股，帶 US badge，移除時用 `(region, code)` 精準刪除。
- US 一鍵更新已落地：獨立 `us_update_status.json`、background lock、`GET /markets/us/update-status`、`POST /markets/us/update-now?months=1`；前端立即更新、3 秒 polling、成功自動刷新 status / analysis / signals / strategies、失敗顯示錯誤。subprocess 明確只跑 `backfill_ohlcv_us.py`，不碰台股 update status / OHLCV。
- 觀察中：us_wbottom 型態狀態機在日常使用的直覺性；背景連線偵測長 session 誤報率。

## Blocked / Risks

- 基本面避雷覆蓋率不足（真實外部資料尚未匯入）；`overall_status` 可能為 warn。不可用假數字補齊。
- 後端依賴僅在本機 `python3.11` 安裝；用其他 interpreter 跑 pytest 會失敗（缺 fastapi 等）。
- **台股 TWSE 原始價不還原企業行動**：0050/0052 分割、2603/6269 大額除息會產生 >10% 假跳動（回放已排除）；一般除息缺口使報酬低估。任何台股報酬計算前先跑 |單日漲跌|>10.5% 掃描。詳見 `docs/ai/strategy-evaluation-ledger.md` 資料品質備忘。

## Do Not Redo

> **已經做過、驗證過、不要重做**的事。

- 兩策略限制（`old_wang` / `steady_momentum`）已定案；不要在前端重算策略 / 分數 / 推薦桶。
- vite proxy 已改用 `127.0.0.1:19000`；**不要改回 `localhost`**（Node 會走 IPv6 連不到只綁 IPv4 的 uvicorn，整個 Dashboard 會變空白）。
- App 路由已改為「由 hash lazy-init state」以修 StrictMode 下 deep link 重整掉回首頁的問題；**不要改回 skip-first ref 的寫法**。`region`（台股/美股）同樣由 hash lazy-init：`#/us` 正準、`#/markets/us` 別名（state→hash effect 對別名**刻意不改寫**，避免多餘歷史紀錄）——別「順手統一」成單一路徑。
- rail 為研究頁 AnalysisPage 的 sibling（在 `{tab === 'analysis'}` 內），跨分頁會 remount 重抓；已知且刻意。
- US scaffold：`TwsePriceSource.fetch_ohlcv()` **刻意丟 `PriceSourceError`**（seam，不接管台股抓取），`test_markets_scaffold.py` 對此有斷言。要讓 TW adapter 真的接管抓取是**有意識的下一步**，屆時需同步更新該測試——不是 bug，別「順手修掉」。
- 美股 OHLCV 寫**獨立** `ohlcv_us.csv`、US universe 用**獨立** `us_leaders.json`；**不要把美股資料混進台股 `ohlcv.csv` / `leaders.json`**（會回歸台股流程）。
- 美股 Phase 1 **不做策略 / 訊號 / 推薦 / 下單**；別把 old_wang / steady_momentum 套到美股。
- US 主源 = **Yahoo Finance（免 key、非官方）**；registry `US` → `YahooFinancePriceSource`。**Stooq 已停用**（需瀏覽器 JS 驗證，**不要嘗試繞過**）；**Finnhub 保留 optional、不在 registry**。
- Yahoo 為**非官方 endpoint、無 SLA**：backfill 需節流、少量 ticker；被限流 / 錯誤要優雅降級（已有錯誤型別），別移除。
- 美股 `us_watch_signal_service` 的 `signal`（watch_breakout 等）與 `priority` 是**觀察用描述性訊號 / 排序**，**非推薦、非買賣建議、非下單、非台股推薦桶**；`us_analysis`/`us_watch` 自帶輕量指標，**不耦合 signals_service、不套 old_wang / steady_momentum**。別把它升級成推薦或加買賣訊號（除非明確要求）。
- 美股 Phase 2 的 `status`（trend_up / recovering / pullback_watch / overheated / weak / no_data）是**描述性技術狀態、非買賣建議**；`us_analysis_service` 自帶輕量指標、**不耦合 signals_service、不套兩策略**。別把它升級成推薦桶或加買賣訊號（除非明確要求）。
- `no_data` 與 `weak` **已刻意拆開**（前者=算不出指標，後者=跌破 MA60）；`recovering`=站上 MA20/MA60 但 MA20<MA60。**不要再合併回 `weak_or_no_data` 混合桶**——那會讓 META/TSLA 這類「站上雙均線但均線未翻多」的個股被誤標成「資料不足」。
- `/status` 的 `insufficient_tickers` 門檻用 `us_market_service` 從 `us_watch_signal_service` import 的 `MIN_SIGNAL_ROWS`（=60）。**不要在 `us_market_service` 另寫死 60**——規則要單一來源（CLAUDE.md §10）。此 import 方向（market_service → watch_signal_service）無循環，watch_signal_service 不反向 import market_service。
- `us_trend_follow` 是**觀察策略**：state 只有 candidate/watch/avoid/overheated、rank 只是排序。**不要**加 0–100 分數、進出場價、買賣語言，或把它升級成台股式推薦桶。策略自有門檻（RSI 50–68、dist ≤ +8）只在 `us_strategy_service` 定義；過熱 / 資料量門檻引用既有常數（`OVERHEATED_*`、`MIN_SIGNAL_ROWS`），別複製數字。守門 bearish/unknown 回空 candidates 是**規則**——別「修」成永遠有輸出。
- `us_strategy_replay_service` 是 **evaluation-only 回放工具**：candidate_exit / trend_protect_exit 是評估用退出規則，**不是 production contract**——別接進 API / 前端 / 排程，別依回放結果直接改策略參數（樣本僅 11 天）。回放的候選判定直接呼叫 production `classify_trend_follow`，**不要**在 replay 裡複製或 fork 規則。out/ 回放結果檔 gitignored，不 commit。
- `us_breakout_replay_service`（us_wang_breakout）同為 **evaluation-only**，且**參數已凍結**（stop 0.92 / vol 1.5x / 20 日高 / MA10×2，2026-07-11 定案）——**不得調參重測**（那是過擬合）；改參數 = 新策略、需另案記錄。5 年結果的 edge 已被生存者敏感度測試否定（拿掉前 5 貢獻檔 → 5/6 年虧損），**別引用 +607 點當「策略會賺」的證據**；別據此上推薦 / 下單功能。
- `us_wbottom_target` 是**觀察策略**：頸線 / 型態低 / 量幅目標是**觀察用關鍵價位**，別改成買賣指令或加自動觸發。參數凍結（swing±3 / 低點距 10–40 / 價差 3% / 突破 ≤20 日 / 目標=量幅），**不得調參**。UI/API 的已知代價揭露（空頭年為負、贏家封頂、生存者折扣）**不得移除**——使用者採用的是高勝率紀律結構，不是 alpha。偵測規則單一來源在 `us_wbottom_service.find_w_breakout`（production 觀察與 replay 共用），**別複製到第三處**。空清單 / `no_pattern_count` 是常態不是 bug。

## Latest Verified State

- **Verified at: 2026-07-10**，Yahoo 資料源 + Phase 2 已 commit（`7c9fe4d` / `cd933ff`）。
- **真實 Yahoo 端到端已驗證通過**（AI 直接跑，非 mock）：`python3.11 scripts/backfill_ohlcv_us.py --months 12` 成功 → 六檔 AAPL/MSFT/NVDA/TSLA/SPY/QQQ **各 255 rows、total 1530**，`ohlcv_us.csv` 產生（本機資料、gitignored、未 commit），`last_data_as_of=2026-07-09`。`/api/markets/us/status` `tickers_with_data=6`；`/api/markets/us/analysis` 六檔皆有 MA20/MA60/RSI/status（3 檔 trend_up、3 檔 weak_or_no_data）；前端美股頁顯示真實收盤/資料日/指標/狀態 badge，「資料尚未更新」橫幅消失、無 console error。
- **US 資料新鮮度（最小收尾切片，本輪，待 commit）**：`/api/markets/us/status` 加 `expected_trading_day` / `days_since_last`（交易日）/ `is_stale`（weekend-aware、容忍 1 個交易日、**不含 NYSE 假日**，複用既有 trading_calendar 函式並傳空 calendar）；前端美股頁顯示「資料日 X（N 個交易日前）」，stale 時琥珀提示重跑 backfill。
- **US Phase 3 觀察訊號（本輪，待 commit）**：`us_watch_signal_service`（複用 Phase 2 指標）產生五種觀察訊號 + reasons/risk_notes/priority；SPY/QQQ 大盤基準（market_bias）調整 priority；`GET /api/markets/us/signals` + 前端「觀察訊號」區塊。**非推薦 / 非買賣 / 無下單 / 未套台股策略。**
- **US universe 擴充 + 分類（本輪，待 commit）**：`us_leaders.json` 6 → 27 檔，每檔加 `category`；`load_us_leaders` 帶出 category；`/universe`、`/analysis`、`/signals` 皆帶 `category`；前端加分類欄 + 分類過濾 chip（同時過濾兩張表）。`python3.11 -m pytest -q` → **858 passed**（+1 universe/category 測試）；`npm run build` 成功。新 ticker 的真實 OHLCV 尚未回補（需本機跑 backfill）；未補前 UI 誠實顯示資料不足。**仍非推薦 / 非買賣 / 無下單；本輪未做 launchd。**
- 測試 / build：`python3.11 -m pytest -q` → **857 passed**（+14 觀察訊號測試）；`npm run build` → 成功；實測 signals（真實資料）：market_bias=bullish、AAPL/SPY watch_breakout(prio 80)、QQQ/TSLA trend_up、MSFT/NVDA avoid_weak；前端「觀察訊號」區塊顯示 badge/priority/reasons/risk、無 console error。
- **執行注意**：US backfill 需以 **`python3.11`** 執行（本機 `python3`=3.9，無法 import 後端：缺依賴 + `X | None` 語法需 3.10+）。
- 更早基準：`8d20c12`（新鮮度）、`7c9fe4d`/`cd933ff`（Yahoo）、`bd5f4f0`/`52a0dfc`（Phase 2）。

## Next Recommended Task

- US Phase 1/2/3 + 新鮮度 + universe 擴充/分類完成；美股頁已有 27 檔清單 / 技術狀態 / 觀察訊號 / 分類過濾（皆描述性）。
- US 後續候選（未做，逐一小步）：完整 NYSE 假日曆 / 自動排程 US backfill（launchd，本輪刻意未做）、Finnhub optional、再擴 universe。**逐步接近台股「可解釋觀察」程度，但仍不做美股正式推薦 / 買賣建議 / 下單。**
- 提醒：擴充 universe 後需以 `python3.11 scripts/backfill_ohlcv_us.py --months 12` 補新 ticker 的真實資料；未補前前端會誠實顯示新 ticker「資料不足」。
- 與美股無關：把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
- 與美股無關：把 `connectionLost` 連線偵測抽成共用 hook（單例探測，避免多頁各起 interval）。
