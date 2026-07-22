# Handoff Log

> AI / 人在每次任務結束後的交接紀錄。這是給下一個接手者的摘要。

## 使用規則

- **最新紀錄放最上面**（append 在頂端，reverse-chronological）。
- 這是 **append-only 的歷史**：新增紀錄，不要改寫或刪除舊紀錄。
- 每筆只寫**可接手摘要**——不要貼完整聊天紀錄、完整 log、逐字對話。
- 每筆用下面的模板；沒有的欄位寫「N/A」，不要留白。
- 若狀態 / 規劃有變，除了在這裡記一筆，也要同步更新 `current-status.md` / `roadmap.md`。

---


## 2026-07-19 — 策略別 guardrail 二次驗證

- **Date:** 2026-07-19
- **Task:** 接續完善上一輪組合風控，處理所有策略共用同一曝險限制造成的報酬犧牲。
- **Completed:** 將 guardrails 改為每個回放 mode 各自凍結並隨 result 輸出；合併與穩健動能維持 15%／60%／3，老王一般日調整為 20%／80%／4（watch 仍 10%／40%／2），所有 mode 在 defensive/extreme/unknown 仍停止新倉。前端改讀 result 實際限制，不再硬編碼合併模式數字。曾驗證穩健動能 20%／80%／5 候選，但長窗口惡化，已拒絕且未保留。
- **Changed Files:** 延續同批 `strategy-portfolio-guardrails` 變更；主要追加 `backend/app/services/strategy_validation_service.py`、`backend/tests/test_strategy_validation_api.py`、`frontend/src/pages/StrategyValidationPage.tsx`、OpenSpec 與 `docs/ai/*`／API 文件。
- **Validation:** 相關測試 **18 passed**；完整 backend **969 passed**；frontend build 成功（僅既有 chunk warning）。短窗口老王 −2.38%／MDD 5.20%（無風控 −2.99%／6.48%）；長窗口老王 +31.98%／11.11%（無風控 +34.66%／14.81%，嚴格版 +24.91%／8.22%）。穩健動能放寬候選為 +4.12%／18.51%，已拒絕；最終仍為 +12.97%／10.61%。回放只寫 `/private/tmp`。
- **Git Status:** 未 commit、未 push；最終狀態見完成回報。
- **Next Steps:** 增加更長、跨多空市場的樣本外分段比較；正式 production 是否採用仍需另行決策。
- **Notes / Warnings:** 這次只改 evaluation 容量，沒有調整策略選股、排序或出場。不要把被拒絕的穩健動能放寬設定重新加回。


## 2026-07-19 — 台股策略組合風控驗收（evaluation-only）

- **Date:** 2026-07-19
- **Task:** 使用者發現策略在大跌窗口表現有問題，要求繼續完善。
- **Completed:** 從既有回放定位到同日多筆進場與總曝險集中；新增只讀成交日前美股 K 線的歷史盤前風險判斷，並在台股驗收回放加入凍結的單檔／總曝險／每日新倉限制。賣出規則與 production 兩策略均未修改。API 回傳每日風險與逐筆略過原因，前端可展開稽核。
- **Changed Files:** `backend/app/services/{pre_market_risk_service,strategy_validation_service}.py`、`backend/tests/{test_pre_market_risk,test_strategy_validation_api}.py`、`backend/docs/api.md`、`frontend/src/{App.css,types/index.ts}`、`frontend/src/pages/StrategyValidationPage.tsx`、`openspec/changes/strategy-portfolio-guardrails/*`、`docs/ai/{current-status,roadmap,validation,handoff-log}.md`。
- **Validation:** 相關測試 **18 passed**；完整 backend **969 passed**；frontend build 成功（僅既有 chunk size warning）；`git diff --check` 待最終回報。壓力窗口 2026-07-08～07-15：合併模式 −8.56%／MDD 11.52% → +0.64%／2.92%。長窗口 2026-05-04～07-15：合併 +34.30%／10.69% → +34.04%／7.55%。輸出僅寫 `/private/tmp`，未覆寫正式 `backend/out`。
- **Git Status:** 未 commit、未 push；最終狀態見本次完成回報。
- **Next Steps:** 用更多樣本外期間與不同市場狀態驗證；尤其穩健動能長窗口報酬由 +31.12% 降至 +12.97%、MDD 僅 11.01% → 10.61%，通過策略別門檻前不得連到 production。
- **Notes / Warnings:** 這是驗收層的風控假設，不是第三套策略，也不是崩盤預測。`unknown` 刻意禁止新倉；若未來考慮 production，需另開明確決策並先定義策略別接受門檻。



## 2026-07-17 — 補完輪：推定臨時休市 + UsResearchPage 聲明 + 記憶搬家（不 push）

- **Date:** 2026-07-17
- **Task:** 使用者指示補齊掃描清單的 2/3/4 項；**明確不 push**（44 commits 仍僅在本機——單點風險已告知，等使用者決定）。
- **Completed:**
  - **推定臨時休市（假 stale 警報修復）**：`trading_calendar_service.reconcile_presumed_closures()`——成功更新後，近 35 天窗口內「平日 + 全市場整天無資料」→ 寫入 `data/trading_calendar.json` 的 `presumed_closures`（loader 併入 holidays 參與新鮮度判定）；資料晚到自動撤銷；人工 `holidays` / `makeup_trading_days` 不受影響；無變更不寫檔。掛在 `run_full_update()` Step 5 之後、stale 判定之前（best-effort，失敗不擋更新），status 增 `calendar_note`。颱風假（如 2026-07-10）不再誤發「資料過期」告警。+4 測試。
  - **UsResearchPage 補免責聲明**（描述性技術觀察、非推薦非買賣非下單、Yahoo 非官方資料源）——最後一個漏聲明的策略/分析 UI。
  - **Claude 記憶搬家**：memory 檔複製到新路徑對應目錄 `~/.claude/projects/-Users-ryan-Developer-new-stock/memory/`（專案搬家後新 session 才讀得到 launchd TCC、vite proxy、時效性事實查證等 gotcha）。
- **Changed Files:** `backend/app/services/trading_calendar_service.py`、`backend/app/services/update_service.py`、`backend/tests/test_trading_calendar_service.py`、`frontend/src/pages/UsResearchPage.tsx`、`docs/ai/handoff-log.md`。（記憶檔在 repo 外。）
- **Validation:** `python3.11 -m pytest -q` → **966 passed**（+4）；`npm run build` ✓。
- **Git Status:** 乾淨（commit 後）。**未 push（使用者明示）。**
- **Next Steps:** 剩餘缺口：push 備份（等使用者）、美股觀察歷史/決策日誌（功能輪）、NYSE 假日曆、台股基本面（blocked）、候選復盤（人工）。
- **Notes / Warnings:** 推定休市是**推定**——TWSE 整天故障也會被記為休市，但資料晚到會自動撤銷、且有 `note_presumed_closures` 說明；別把它改成永久人工假日清單的自動維護器。

## 2026-07-17 — 策略驗證實驗室收斂：免責聲明 + 背景執行 + guardrail 交接

- **Date:** 2026-07-17
- **Task:** 策略掃描找出驗證實驗室（`4559398`，relay 產出）的四個問題，使用者核准全修。**同輪前置**：專案已從 `~/Desktop/code/new_stock` 搬到 `~/Developer/new_stock`（07-17 上午），launchd 排程因 plist 寫死舊路徑而全斷——已從新路徑重灌雙 agent 並實測補跑成功（TW 資料到 07-17 stale=False、US 36 檔；美股週五盤中補的那根 K 為快照，隔日 08:30 排程自動覆蓋為完整 K）。舊路徑殘骸可刪。另把樹上懸掛的盤前風險中心 WIP 以原樣落地（`8c65b20`，驗證後才 commit）。
- **Guardrail 交接（重要）：** 2026-07-11 條目寫「replay 是 evaluation-only——別接進 API / 前端 / 排程」。**此邊界已於 2026-07-17 被使用者決策取代**（策略驗證實驗室上線）。新的現行邊界是：
  1. 回放**可以**接進 API / 前端，但**只能重用** production / 凍結的規則實作（`classify_trend_follow` / `find_w_breakout` / `_run_signal_batch`），不得複製或變形規則；
  2. 全窗口台股回放**必須背景執行**（POST 觸發 + status 輪詢），不得同步佔住請求；
  3. 驗證 UI **必須**掛「非推薦、非買賣建議、非下單」與**多重測試偏誤**警語；
  4. 任意區間的結果是探索工具，**不得**寫進文件當策略有效性證據——正式結論仍以凍結參數的長期報告（strategy-evaluation-ledger）為準。
- **Completed:**
  - `StrategyValidationPage` 兩面板（台股/美股）補免責聲明 + 多重測試警語（原本全頁零聲明，是全站唯一漏掉的策略 UI）。
  - TW `POST /system/strategy-validation` 改**背景觸發**（`trigger_background_validation`，執行緒 + lock + `out/strategy_validation_status.json`，仿 us_update_service 模式）；新增 `GET /system/strategy-validation/status`；前端改輪詢（4 秒），離開頁面不中斷。US 版實測 5 年全窗口 20 秒，維持同步。
  - 測試改寫 + 新增（trigger 傳遞、422、409 busy、status、日期先驗證再開執行緒、lock 佔用）；api.md 同步。
- **Changed Files:** `backend/app/services/strategy_validation_service.py`、`backend/app/routers/system.py`、`backend/tests/test_strategy_validation_api.py`、`backend/docs/api.md`、`frontend/src/pages/StrategyValidationPage.tsx`、`frontend/src/api/client.ts`、`frontend/src/types/index.ts`、`frontend/src/App.css`、docs/ai。
- **Validation:** 見完成回報。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Notes / Warnings:** production 策略規則本體零改動（diff 驗證過）。背景執行同一時間只允許一個回放（lock）；status 檔在 out/（gitignored）。別把「請勿關閉頁面」的同步模式加回來。

## 2026-07-17 — 盤前風險中心 MVP（隔夜市場 + 事件提示）

- **Date:** 2026-07-17
- **Task:** 台股盤中重挫逾 2,000 點後，使用者希望系統能利用開盤前新聞／事件與隔夜訊號降低風險，並授權依適合方式調整。
- **Completed:** 依 OpenSpec 新增盤前風險中心；後端以 SPY／QQQ／TSM 連續兩日收盤漲跌與最近人工市場筆記計分，輸出 normal/watch/defensive/extreme/unknown、理由、是否暫停新倉與最高曝險提示。US 行情 stale 或不足時誠實回 unknown。Dashboard 加入「非崩盤預測」風險卡、隔夜指標、事件摘要與 MOPS／台積電 IR／Fed／BLS 官方入口。前端 API 失敗會降級為尚無資料，不阻塞既有 Dashboard。
- **Changed Files:** 新增 `backend/app/services/pre_market_risk_service.py`、`backend/tests/test_pre_market_risk.py`、`openspec/changes/pre-market-risk-center/{proposal.md,design.md,tasks.md,specs/pre-market-risk.md}`；修改 `backend/app/{models/system.py,routers/system.py}`、`backend/docs/api.md`、`frontend/src/{api/client.ts,types/index.ts,App.css}`、`frontend/src/pages/Dashboard.tsx`、`docs/ai/{current-status,roadmap,validation,handoff-log}.md`。
- **Validation:** 新測試 5 passed；API/docs 小套件 8 passed；完整 backend **958 passed**；frontend build 成功（僅既有 >500 kB warning）；桌面瀏覽器顯示 stale→待確認、QQQ/TSM 風險原因與 4 個官方來源，console 0 errors；375px 寬度 `scrollWidth=clientWidth=360`、console 0 errors。
- **Git Status:** 未 commit；工作樹僅包含本次盤前風險中心與文件變更，結束狀態見回報。未 push。
- **Next Steps:** 做獨立官方事件 collector（先 MOPS 與公開 ICS／IR 行事曆），採快取、來源時間與解析健康狀態；未完成前不得宣稱自動監測即時新聞。再評估將盤前 risk level 接成策略新倉 gate，需先補歷史事件／隔夜資料回放驗證，不能直接上 production。
- **Notes / Warnings:** 第一版不抓新聞全文，事件證據只用人工市場筆記；目前實際 US 資料日 2026-07-13 已 stale，因此畫面正確顯示待確認並暫停一般新倉，而不是用舊資料判定安全。

---

## 2026-07-17 — US parity 全套回歸與瀏覽器驗收收尾

- **Date:** 2026-07-17
- **Task:** 接續完善台股／美股畫面與策略日期區間落差，完成本批次收尾驗收。
- **Completed:** 移除 `test_daily_check.py`、`test_pm_worklist.py`、`test_update_status.py`、`test_update_workflow.py` 對舊 repo 絕對路徑的依賴，改驗證命令列最終參數；以 in-app browser 實測美股市場總覽、AAPL 技術分析、region-aware 觀察清單、策略驗收與兩個日期欄位。確認「立即更新美股」存在但未觸發真實 Yahoo 回補；瀏覽器 console 無 error。
- **Changed Files:** 上述四個 backend tests、`openspec/changes/us-market-parity/tasks.md`、`docs/ai/{current-status,handoff-log}.md`；其餘 production 變更屬同一未提交 US parity 批次。
- **Validation:** 完整 backend pytest **953 passed in 37.01s**；frontend build 成功（僅既有 >500 kB chunk warning）；桌面瀏覽器流程通過且 console 0 errors；`git diff --check` 於收尾再次執行。
- **Git Status:** 未 commit；結束狀態見回報。未 push。
- **Next Steps:** 補手機寬度 RWD 驗收；US 交易／投組／統計仍須先確認費率、稅費、零股與匯率口徑。
- **Notes / Warnings:** 美股資料日顯示 2026-07-13、頁面誠實標示已過期；本輪避免網路與資料污染，未執行更新按鈕。

---

## 2026-07-17 — 美股一鍵更新 + 獨立背景狀態

- **Date:** 2026-07-17
- **Task:** 接續 US parity，補上台股已有、美股缺少的一鍵更新與狀態輪詢。
- **Completed:** 新增獨立 `us_update_store.py` / `us_update_service.py`：持久化 idle/running/success/failed、背景 lock 防重複、subprocess 執行既有 `backfill_ohlcv_us.py`；新增 GET update-status 與 POST update-now（months 1–60、409/422）。US 頁新增立即更新按鈕、running disabled、3 秒 polling、成功後刷新 US status / freshness / analysis / signals / trend-follow / W-bottom，失敗顯示錯誤。TW update store、ohlcv 與 signals 流程完全不接觸。
- **Changed Files:** 新增 `backend/app/{storage/us_update_store.py,services/us_update_service.py}`、`backend/tests/test_us_update_service.py`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`、`frontend/src/{api/client.ts,types/index.ts,App.css}`、`frontend/src/pages/UsMarketPage.tsx`、OpenSpec tasks、`docs/ai/{current-status,validation,handoff-log}.md`。
- **Validation:** 相關 tests **34 passed**（補文件後）+ US-only command isolation test；frontend build 成功（既有 >500 kB warning）。未打真實 Yahoo、未寫 `ohlcv_us.csv`；避免驗收污染與網路依賴。完整 pytest **949 passed / 4 failed**；4 個失敗皆為既有測試寫死舊 repo 路徑 `/Users/ryan/Desktop/code/new_stock`，與本功能無關。
- **Git Status:** 未 commit；結束狀態見回報。未 push。
- **Next Steps:** US USD 交易／投組／統計前，先確認券商費率、稅費、零股與匯率呈現規則；另補瀏覽器實測一鍵更新長流程。
- **Notes / Warnings:** `us_update_status.json` 與台股 `update_status.json` 分開；US endpoint 不重算台股 signals。Yahoo 非官方、可能限流，失敗會留在 US status 供重試。

---

## 2026-07-16 — US 研究連結全覆蓋 + 美股觀察清單畫面

- **Date:** 2026-07-16
- **Task:** 使用者要求繼續完善美股與台股操作落差。
- **Completed:** UsMarketPage 的基本狀態、trend-follow candidates / excluded、W-bottom patterns、觀察訊號所有 ticker 均改為可點擊並直達 US 技術分析。US 導覽新增「觀察清單」，重用既有群組但只顯示 region=US，顯示 US badge；移除時傳 region，避免刪到同 code 的 TW item。WatchlistsPage 保持預設不過濾，台股既有入口行為不變。
- **Changed Files:** `frontend/src/pages/{UsMarketPage,WatchlistsPage}.tsx`、`frontend/src/{App.tsx,App.css}`、`openspec/changes/us-market-parity/tasks.md`、`docs/ai/{current-status,handoff-log}.md`。
- **Validation:** backend 相關 tests **34 passed**；frontend build 成功（既有 >500 kB chunk warning）。未跑完整 pytest；上一完整結果為 942 passed / 4 個既有舊路徑失敗。
- **Git Status:** 未 commit；結束狀態見回報。未 push。
- **Next Steps:** US 一鍵更新（獨立 status store / lock / background backfill / polling），完成後才進 USD 交易／投組／統計。
- **Notes / Warnings:** US 自選仍共用群組名稱，但 item identity 已按 region 分離；既有無 region item 視為 TW。

---

## 2026-07-16 — US 單股研究頁 + region-aware 自選清單

- **Date:** 2026-07-16
- **Task:** 使用者核准直接完成下一階段：美股單股研究頁與 region-aware 自選清單。
- **Completed:** 新增 `GET /api/markets/us/analysis/{code}`（選填 as_of）：120 根 OHLCV、MA20/60、RSI、20 日漲跌、距均線、描述性狀態、reasons / risk_notes、USD。前端 US 導覽新增「技術分析」，用 lightweight-charts 畫真實 K 線與 MA20/60；市場總覽 ticker 可直達，研究頁可搜尋 ticker 並加入既有自選群組。watchlist identity 改為 `(region, code)`，add/remove API 支援 region；legacy 無 region item 視為 TW，避免破壞個人資料。
- **Changed Files:** `backend/app/services/us_analysis_service.py`、`backend/app/routers/{markets,watchlists}.py`、`backend/app/storage/watchlist_store.py`、`backend/tests/test_watchlists.py`、`backend/docs/api.md`、`frontend/src/pages/{UsMarketPage,UsResearchPage}.tsx`、`frontend/src/{App.tsx,App.css,api/client.ts,types/index.ts}`、OpenSpec tasks 與 AI status/handoff。工作樹另含前輪未提交批次。
- **Validation:** 相關 tests **36 passed**；frontend build 成功（既有 >500 kB warning）；真實 AAPL smoke：資料日 2026-07-13、1,280 rows、chart payload 120 bars、status trend_up。未重跑完整 pytest；上一輪完整結果 942 passed / 4 個既有舊路徑失敗。
- **Git Status:** 未 commit；結束狀態見回報。未 push。
- **Next Steps:** 將 trend-follow candidates、W-bottom patterns 與觀察訊號 ticker 也接上研究頁；US 自選清單頁增加 region filter / badge；之後做 US 一鍵更新工作流。
- **Notes / Warnings:** US research 是描述性研究，不套台股策略、不下單；K 線使用 `ohlcv_us.csv`，不讀台股 OHLCV。

---

## 2026-07-16 — 美股共用導覽 + 策略驗收日期區間落地

- **Date:** 2026-07-16
- **Task:** 使用者指出台股／美股畫面落差仍大，且美股沒有策略驗收日期區間；要求實際補齊而非只寫規格。
- **Completed:** App 的 US 分支不再直接繞過所有導覽，新增「研究／市場總覽」與「系統／策略驗收」同層入口；共用策略驗收頁新增台股／美股切換，從 US 導覽進入時預設 US。新增 `POST /api/markets/us/strategy-validation?start=&end=`，直接重用既有無未來洩漏 replay 核心，依日期同時跑 `us_trend_follow`（trend_protect_exit）與 `us_wbottom_target`；前端可切策略並看訊號、D+1 open 進出、持有交易日、報酬、未解析與 TradingView。明確標示 US 是逐筆等權評估，不冒充 TW 100 萬投組淨值。
- **Changed Files:** 新增 `backend/app/services/us_strategy_validation_service.py`、`backend/tests/test_us_strategy_validation_api.py`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`、`frontend/src/{App.tsx,App.css,api/client.ts,types/index.ts}`、`frontend/src/pages/StrategyValidationPage.tsx`、`openspec/changes/us-market-parity/tasks.md`、`docs/ai/{current-status,handoff-log}.md`。工作樹另含前輪未提交策略驗收／規格批次，未覆寫 `.ai-*`。
- **Validation:** 相關 tests **40 passed**；frontend build 成功（既有 >500 kB warning）；真實資料 2026-06-01～06-30 smoke：trend-follow 24 signals / 20 completed，W-bottom 10 / 8。完整 pytest **942 passed / 4 failed**；4 個失敗仍是既有測試寫死舊 repo 路徑 `/Users/ryan/Desktop/code/new_stock`，與本功能無關。瀏覽器 RWD 本輪未跑。
- **Git Status:** 未 commit；結束狀態見回報。未 push。
- **Next Steps:** Phase 1：US 單股 K 線研究頁、region-aware 自選清單與候選直接跳研究；之後補 US 一鍵更新、交易／投組／統計。
- **Notes / Warnings:** 美股兩策略結果不可直接相加，也不可與台股淨值比較；仍是 evaluation-only、非推薦／非下單。US replay 未計滑價、手續費、稅費與股息，限制已隨 API 回傳。

---

## 2026-07-16 — 美股除策略外對齊台股：產品規格與分段計畫

- **Date:** 2026-07-16
- **Task:** 使用者指定美股除策略外，資料與操作體驗盡量比照台股。
- **Completed:** 建立 `us-market-parity` OpenSpec，盤點並定義四階段：1) US 單股研究 + region-aware 自選；2) 一鍵更新與狀態工作流；3) market-aware 交易 / 投組 / 統計；4) 共用驗收 UI + US 自有策略回放。明確保留 US 策略、USD、交易日／時區、資料源與費稅差異；禁止把 old_wang / steady_momentum 或台股費稅直接套到美股。採共用 market-aware 能力，避免複製兩套產品碼。
- **Changed Files:** 新增 `openspec/changes/us-market-parity/{proposal.md,design.md,tasks.md,specs/market-parity.md}`；更新 `docs/ai/{roadmap,current-status,handoff-log}.md`。本輪未修改 production code，也未覆寫前一輪未提交策略驗收檔案。
- **Validation:** docs/spec-only；已檢查既有 US page / API 與台股能力差距。未跑 pytest / frontend build，因本輪無程式碼變更。
- **Git Status:** 工作樹原已包含前一輪策略驗收未提交批次及 `.ai-*` 目錄；本輪只新增規格與三份狀態文件變更。結束狀態見回報。
- **Commit:** 無；未 push。
- **Next Steps:** 依 `tasks.md` 實作 Phase 1：US 單股 analysis endpoint、研究頁 region / USD、候選連結，以及 watchlist region 相容遷移與測試。
- **Notes / Warnings:** Phase 3 前必須由使用者確認美股費率、稅務與零股規則；沒有匯率時禁止把 TWD / USD 損益直接加總。

---

## 2026-07-16 — 策略驗收支援自選日期區間完整重跑

- **Date:** 2026-07-16
- **Task:** 接續策略驗收，新增可選開始／結束日期，讓使用者針對不同區間測試兩套策略與合併帳戶。
- **Completed:** 將一次性 walk-forward 回放正式化進 `strategy_validation_service.py`；`POST /api/system/strategy-validation?start=&end=` 以 100 萬元空手完整重跑指定區間（起日前一交易日收盤訊號、D+1 開盤成交、10 bps 滑價、費稅、持倉感知 exit/reduce），三模式各自獨立計算並快取 JSON。前端加入日期選擇器與明確執行按鈕、計算中狀態、區間錯誤保留上一份結果。不是在前端截斷既有交易，因此期初現金、持倉、MDD 與報酬口徑一致。
- **Changed Files:** `backend/app/services/strategy_validation_service.py`、`backend/app/routers/system.py`、`backend/tests/test_strategy_validation_api.py`、`backend/docs/api.md`、`frontend/src/pages/StrategyValidationPage.tsx`、`frontend/src/api/client.ts`、`frontend/src/App.css`、`docs/ai/current-status.md`、`docs/ai/handoff-log.md`；同一未提交批次另含前輪策略驗收與交易報告檔案。未觸碰 `.ai-coding-relay/`、`.ai-heartbeat/`。
- **Validation:** 相關後端/API/docs tests **12 passed**；`npm run build` 成功（既有 >500 kB chunk warning）；真實資料 smoke test 2026-07-13～07-15 成功（combined 6買/1賣、old_wang 2買/0賣、steady_momentum 6買/1賣），輸出置於 `/private/tmp`。全套 pytest：**938 passed / 4 failed**；4 失敗皆為既有測試寫死舊路徑 `/Users/ryan/Desktop/code/new_stock`，實際 repo 已移至 `/Users/ryan/Developer/new_stock`，與本次功能無關。
- **Git Status:** 本批仍未 commit；結束狀態見任務回報。未 push。
- **Next Steps:** 實際以瀏覽器跑一個較長區間觀察等待體感；若區間擴到多年，將同步 POST 改為背景 job + polling，避免 HTTP 長連線。另可在下一個獨立 scope 修正 4 個硬編碼舊 repo path 的測試。
- **Notes / Warnings:** 此為紙上回放，不是券商實績或下單；universe / fundamentals 使用現行 snapshot，仍有生存者與歷史快照偏誤；台股未完整還原企業行動，已排除已知污染代碼。

---

## 2026-07-16 — 策略驗收 UI + TradingView 逐筆核對

- **Date:** 2026-07-16
- **Task:** 使用者希望有比純文字損益更清楚的驗收方式，能逐檔了解策略如何進出並搭配 TradingView 核對，並要求實際操作測試一次。
- **Completed:**
  - 新增唯讀 `strategy_validation_service.py` 與 `GET /api/system/strategy-validation`：讀取最新台股投組回放 JSON，補股票名稱、市場、本機分析 hash 與正確的 TradingView `TWSE:` / `TPEX:` symbol；無報告時誠實回 404，不在 API request 內重算策略。
  - 新增前端 `#/validation`「策略驗收」頁與系統導覽入口：合併 / 老王 / 穩健動能 segmented tabs、期末淨值 / 淨損益 / MDD / 成本 / 交易數、集中度警告、持有 / 平倉 / 盈虧篩選、代號名稱搜尋與個股損益排序。
  - 每檔可展開完整事件時間線：訊號日、D+1 成交日、方向、成交價、股數、手續費、交易稅、決策原因與單筆已實現損益；另有「本機線圖」與 TradingView 外部核對。
  - 瀏覽器實測旺宏：搜尋、展開兩輪買賣、逐筆費稅與原因均正確；本機線圖成功跳 `#/research/2337`；TradingView URL 為 `TWSE:2337`，TPEX 範例台半正確為 `TPEX:5425`。老王 tab 顯示 1,346,597 元 / +34.66% / MDD 14.81%。
  - 手機 375×844 實測：頁面無整體橫向溢出，寬表格捲動限制在表格內；策略標籤中文化，「31 買 · 27 賣 · 17 持有」不截斷；console 0 errors。
- **Changed Files:** `backend/app/services/strategy_validation_service.py`、`backend/app/routers/system.py`、`backend/tests/test_strategy_validation_api.py`、`backend/docs/api.md`、`frontend/src/pages/StrategyValidationPage.tsx`、`frontend/src/App.tsx`、`frontend/src/api/client.ts`、`frontend/src/types/index.ts`、`frontend/src/App.css`、`docs/ai/current-status.md`、`docs/ai/handoff-log.md`。
- **Validation:** endpoint tests 3 passed；完整後端 **939 passed**；`npm run build` 成功（既有 >500 kB chunk warning）；瀏覽器實測策略切換 / 搜尋 / 展開 / 本機跳轉 / TWSE-TPEX TradingView URL / 手機響應式 / console 均通過。
- **Next Steps:** 將一次性 `/private/tmp/replay_tw_portfolio_may.py` 正式化成可重跑 CLI，再在頁面加「報告新鮮度」與每日淨值曲線；正式化前需先定義同日多訊號資金分配與重複 reduce 規則，避免 UI 漂亮但回放口徑仍不穩定。
- **Notes / Warnings:** 此頁是 generated paper replay 的驗收器，不是券商實績或下單介面；資料主要限制仍是現行 universe / fundamentals snapshot、生存者偏誤、未計股利與少數股票貢獻集中。

---

## 2026-07-16 — 台股 100 萬空手起始投組回放（05-01～07-15）

- **Date:** 2026-07-16
- **Task:** 使用者要求排除 5 月前持倉與錯誤手動成交紀錄，以 100 萬元重算 2026-05-01 至今的台股策略投組損益。
- **Completed:**
  - 先執行 `scripts/daily_update.py --months 1`，台股 OHLCV / 法人資料更新至最近完整交易日 2026-07-15；2026-07-16 尚未收盤，不納入。
  - 以一次性 walk-forward 回放重算：04-30 收盤訊號可於 05-04 開盤成交；其後皆為 D 日收盤產生持倉感知決策、D+1 開盤成交，禁止同日收盤訊號回填；初始現金 1,000,000、初始零持股、不融資、允許零股。
  - 成交套用 10 bps 滑價並限制於當日 low–high，買賣手續費 0.1425%、賣出交易稅 0.3%；期末以 07-15 收盤模擬全部清算後淨值計算。合併策略期末 1,343,044 元，淨利 343,044 元（+34.3044%），最大回撤 10.69%；31 次買進、27 次賣出、期末 17 檔。
  - 分策略對照：old_wang 1,346,597 元（+34.6597%，MDD 14.81%）；steady_momentum 1,311,169 元（+31.1169%，MDD 11.01%）。結果高度集中於禾伸堂、南亞科、景碩，不能外推為穩定報酬或真實帳戶績效。
  - 稽核所有合併策略成交，共 58 個交易事件，0 筆超出成交日 low–high；旺宏改為 05-11 模擬買進 161.161、日月光改為 06-15 模擬買進 619.619，不採用原手動紀錄的 174 / 336。
- **Changed Files:** `docs/ai/handoff-log.md`；generated output（gitignored）：`backend/out/tw_portfolio_replay_2026-05-01_2026-07-15.json`。一次性回放程式位於 `/private/tmp/replay_tw_portfolio_may.py`，未加入正式產品碼。
- **Validation:** `scripts/daily_update.py --months 1` 成功；一次性腳本 `py_compile` 成功並完整執行；資金恆等式通過（89,952 現金 + 1,253,092 預估淨清算值 = 1,343,044）；58/58 成交價均落在當日 low–high。未修改正式程式碼，因此未重跑全套 pytest；上一輪完整後端測試為 936 passed。
- **Next Steps:** 將此 walk-forward 投組回放正式化前，需決定整股 / 零股、同日多訊號的資金分配上限、重複 `reduce` 規則，並補齊歷史 fundamentals / chips snapshot，降低目前快照造成的前視與生存者偏誤。
- **Notes / Warnings:** 這是策略紙上回放，不是券商實績；未計股利，且目前 universe / fundamentals 為現行快照。報酬約 34% 主要由少數強勢股貢獻，集中度高。

---

## 2026-07-16 — 台股 / 美股交易報告拆分 + 旺宏時間基準修正

- **Date:** 2026-07-16
- **Task:** 使用者要求台股、美股分成兩份詳細報告，欄位含建議 / 實際進場、停損、止盈、出場、損益、報酬與策略；並追查旺宏為何實際均價高於舊報告止盈價。
- **Completed:**
  - `generate_strategy_trade_report.py` 改輸出兩份獨立報告：`strategy_trade_report_tw_2026-05-01.md`、`strategy_trade_report_us_2026-05-01.md`。
  - 修正時間穿越：進場建議與停損 / 止盈改用**交易日前一個資料日的收盤快照**，不再拿交易當日收盤後重算值冒充事前計畫；推論出場原因同樣以前一資料日為基準。
  - 旺宏釐清：舊報告 `171.5` 是 04-30 收盤後重算目標；04-30 交易前可知的是 04-29 計畫（建議 136.12–145.84、停損 136.12、目標 190.25、動作等回測）。實際 174 未高於真正事前目標，但高於建議區且非進場動作，仍判定不合規。
  - 新增逐筆進場合規檢核：實際價 ≥ 止盈、≤ 停損、超出建議區、或每日動作非 enter/probe 均標不合規。現有 8 筆進場為 0/8 合規，因此帳面 +91,361 元只能稱交易結果，不能稱策略照單績效。
  - 交易價資料品質改用「實際價是否落在同日 low–high 外（1% 容差）」檢查，不再只與收盤價比較；9 筆交易需回查。
  - 美股報告保留使用者指定的實際交易欄位，但目前 `trades.json` 無美股紀錄；觀察策略與回放另列，明確不冒充實績。
- **Changed Files:** `backend/scripts/generate_strategy_trade_report.py`、`backend/tests/test_strategy_trade_report.py`、`docs/ai/handoff-log.md`；generated outputs：`backend/out/strategy_trade_report_tw_2026-05-01.md`、`backend/out/strategy_trade_report_us_2026-05-01.md`。
- **Validation:** 報告腳本執行成功；`python3.11 -m py_compile` 成功；新增測試 4 passed；完整後端測試 **936 passed**。
- **Git Status:** 任務結束回報為準；工作樹進場時已有 `.ai-coding-relay/`、`.ai-heartbeat/` 與未提交 handoff / report script，本輪未覆寫兩個 AI 輔助目錄。
- **Next Steps:** 優先讓使用者校正報告列出的 9 筆區間外成交；若要追蹤真正策略績效，交易建立時需保存 `strategy_snapshot`（訊號基準日、建議區、停損、止盈、策略 tag），並為美股交易補 market / currency / fee / tax 契約。
- **Notes / Warnings:** 不可再以同日收盤訊號回填同日進場計畫；出場 note 未填時的原因仍只是系統推論，不等於使用者主觀原因。美股回放不屬實際交易。

---

## 2026-07-16 — 5 月以來策略實際交易與目前台美股觀察報告

- **Date:** 2026-07-16
- **Task:** 使用者要求檢查目前台股 / 美股策略推論是否正確，並整理自 5 月開始實施策略後的實際進出、預計停損 / 止盈、出場原因、正負損益與策略歸因。
- **Completed:**
  - 新增 `backend/scripts/generate_strategy_trade_report.py`：讀取 `trades.json`、以交易建立日或交易日 >= `2026-05-01` 篩選，依 FIFO/WAC 類方式彙整平倉交易；買進日用 `analysis_service.analyse_stock(code, as_of)` 回推當時預計停損 / 止盈 / 策略標籤；賣出日若交易 note 空白，標註「交易紀錄未填；依當日分析推論」。
  - 產出 `backend/out/strategy_trade_report_2026-05-01.md`（generated output，不手動編輯）：實際交易 7 組平倉、勝率 2/7、已實現損益 **+91,361 元**；目前無未平倉；最新台股 universe_report 顯示老王大盤濾網多數標的為 block，短波段做多需降權；美股僅列觀察策略與回放摘要，不混入實際交易績效。
  - 報告分清楚：台股實際 trades、最新台股可能買進/降風險、美股 `us_trend_follow` / `us_wbottom_target` 目前觀察狀態、美股回放（非實際交易）。
- **Changed Files:** 新增 `backend/scripts/generate_strategy_trade_report.py`；修改 `docs/ai/handoff-log.md`；產生 `backend/out/strategy_trade_report_2026-05-01.md`。
- **Validation:** `cd backend && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/generate_strategy_trade_report.py` 成功產出報告；`cd backend && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q` → **932 passed**。
- **Git Status:** 任務結束回報為準。當前 repo 已有未追蹤 `.ai-coding-relay/`、`.ai-heartbeat/`，本輪未觸碰。
- **Next Steps:** 若要進一步產品化，可把這份報告做成後端 API / 前端「策略績效」頁；但需先決定是否把出場原因變成必填欄位，避免未來仍需用系統推論補原因。
- **Notes / Warnings:** 美股目前沒有實際 trades，只有觀察策略 / 回放；不可把美股回放損益與使用者實際績效混算。台股早期交易 note 多數為空，出場原因是依當日訊號推論，不等於使用者當時主觀決策。

---

## 2026-07-13 — launchd 排程重建：錯過自動補跑（台股）+ 美股排程新增

- **Date:** 2026-07-13
- **Task:** 使用者核准並指定需求：台股維持 15:30、美股另找時間、**電腦沒開錯過排程就延後補跑、做到一次為止**。
- **Completed:**
  - `scripts/scheduled_update.py`：wrapper（`--market tw|us`、`--force`、`--dry-run`）。規則：`now >= 當日目標時間` 且 `目標時間後尚未成功` → 執行；子程序 exit 0 才寫 marker（`out/.sched_last_success_*`）；失敗下個整點自動重試。台股門檻 15:30、美股 08:30（美股收盤=台灣清晨 4-5 點）。輸出 append 到 `out/scheduled_update_{tw,us}.log`。
  - `setup_schedule.sh` 改雙 agent：`com.stockapp.daily-update`（tw）+ `com.stockapp.us-update`（us，新增）；plist 改 `RunAtLoad=true` + `StartInterval=3600`（取代單點 StartCalendarInterval）；`ASSUME_YES=1` 支援非互動；**Python 預設優先 `python3.11`**（第一次安裝抓到 `/usr/bin/python3` 導致子程序缺依賴，已修）。`remove_schedule.sh` 同步雙 label。
  - `test_scheduled_update.py` 6 測試（純函式 `should_run` 決策矩陣）。
  - **實測（launchd 真跑非模擬）**：載入即觸發，兩市場端到端 exit 0（TW 資料日 2026-07-13 stale=False；US 36/36）、markers 寫入、`launchctl start` 重複觸發回「今天已成功，跳過」。
- **Changed Files:** 新增 `backend/scripts/scheduled_update.py`、`backend/tests/test_scheduled_update.py`；修改 `backend/scripts/setup_schedule.sh`、`backend/scripts/remove_schedule.sh`、docs/ai（current-status / validation / handoff-log）。plist 在 `~/Library/LaunchAgents/`（不進 git，由 setup 腳本生成）。
- **Validation:** 見完成回報（pytest 全套 + launchd 實測）。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Next Steps:** 觀察幾天 wrapper 決策 log（`out/update.launchd.log` / `us_update.launchd.log`）；臨時休市的假 stale 警告仍是既知小缺陷（wrapper 不受影響——update exit 0 就算成功）。
- **Notes / Warnings:** **TCC gotcha 仍在**：plist 的 StandardOutPath 必須讓 launchd 自建（setup 腳本會先 rm），別手動 touch。重載 agent 前先 unload 並等舊實例結束，否則 `Load failed: 5`。wrapper 門檻時間在 `scheduled_update.py` 的 `MARKETS` 常數，改門檻不需動 plist。別把 wrapper 換回單點 StartCalendarInterval（會回到跨重開機丟失的老問題）。

---

## 2026-07-13 — SPCX 納入（更正「SpaceX 未上市」錯誤）+ launchd 失效診斷 + 資料補跑

- **Date:** 2026-07-13
- **Task:** 使用者指出 SpaceX 應已上市。Web 查證屬實：**2026-06-12 IPO，NASDAQ: SPCX**——前一輪文件寫「未上市」是 AI 知識截止（2025-02）造成的錯誤，本輪更正。同時例行掃描發現台股資料停更。
- **Completed:**
  - `us_leaders.json` +SPCX（`Defense / Aerospace`，35 → 36 檔）；note / api.md 的錯誤敘述已更正（current-status 舊段落以註記更正，handoff-log 依 append-only 不改寫舊條目、以本條目更正記錄）。
  - 美股回補：36/36 OK；SPCX 19 rows（2026-06-12 起），收盤 145.30 與公開報價一致。`insufficient_tickers=["SPCX"]`、`min_row_count=19` 是**誠實顯示非故障**；strategies 將 SPCX 列 excluded（reasons=資料不足 ≥60 筆）；約 2026-09 後樣本夠自動進入分析。
  - 台股：07-13（週一）資料補齊、stale 解除；**07-10 確認為臨時休市**（TWSE 全市場無該日資料，週五 stale 警告為假警報）。
  - **launchd 失效根因**：plist 僅 `StartCalendarInterval` 15:30 單點 + `RunAtLoad=false`；機器近日在 15:30 常關機/重開（reboot 紀錄 07-13 00:49 關機、08:59 / 19:50 重開），launchd 行事曆觸發**跨重開機不補跑** → 07-06 後零自動執行（07-09 / 07-12 / 07-13 皆手動）。`launchctl list` exit 0 = 程式本身沒壞。
- **Changed Files:** `backend/data/us_leaders.json`、`backend/docs/api.md`、`docs/ai/current-status.md`、`docs/ai/handoff-log.md`。資料檔（ohlcv*.csv）本機不進 git。
- **Validation:** pytest 見完成回報；SPCX 端到端驗證（status / trend-follow excluded 有理由 / w-bottom 正常）。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Next Steps:** 1) **launchd 修復待使用者同意**：plist 改多時段觸發（如 15:30 + 21:30；daily_update 冪等、重複跑無害），或使用者自行確保 15:30 開機。2) 假 stale 警告（臨時休市不在行事曆）仍是既知小缺陷。
- **Notes / Warnings:** SPCX 短史：**任何含 SPCX 的歷史回放都無意義**（<1 個月樣本）；別因清單有它就把它塞進回放結論。AI 知識截止教訓：**上市狀態這類時效性事實要先查證再寫進文件**。

---

## 2026-07-12 — 收尾輪：策略評估證據存檔 + 台股資料清理 + 文件除舊

- **Date:** 2026-07-12
- **Task:** 使用者問「還有什麼沒完善」→ 指示處理紅色三項：1) 評估證據只活在對話/scratchpad；2) 台股 ohlcv.csv 髒資料；3) current-status 陳舊段落。
- **Completed:**
  - **策略評估總帳** `docs/ai/strategy-evaluation-ledger.md`：7 個家族（trend_follow 兩退出 / pullback / 指數擇時 / wang_breakout / wbottom + 三出場對比 / 台股 old_wang）一張表：關鍵數字、判定、證據位置；跨家族五教訓（零 α 區、生存者偏誤是頭號殺手、濾網三次證明、多重測試折扣、對照組=指數）；資料品質備忘；方法學標準。**未來任何「要不要再測 X」先查此表。**
  - **台股 old_wang 回放正式化** `backend/scripts/replay_tw_old_wang.py`：候選判定=production 管線（`_run_signal_batch` as-of 截斷，零複製；`pool_factory=_SyncPool` 換速度）；兩套評估退出（bucket_exit / wang_protect −8%+MA10×2）；排除企業行動污染 codes（0050/0052/2603/6269）；含成本後數字（0.585%/趟）。清理後資料重跑：bucket_exit 1,792 筆 +1.55%（成本後 +0.97%）；wang_protect 781 筆 +5.64%（成本後 +5.06%）——**但同期 0050 修正後 +143.9%，投組等效 ≈ 指數（β 非 α）**。無獨立測試（重用已測 production 管線），validation.md 已註明。
  - **台股 ohlcv.csv 清理**：移除 2009/2010/2017 髒列 **284 筆**（會讓均線把相隔多年 bar 視為相鄰；來源不明殘留）；備份 `backend/data/ohlcv.csv.bak-20260712`（皆本機檔不進 git）。日常 backfill（近 12 個月）不會重引入。
  - **current-status 除舊**：In Progress 移除停在 Phase 1+2 的陳舊項；Completed 的「待 commit」改為實際 hash；Current Phase / Last updated 更新；Risks 補台股企業行動備忘。
- **Changed Files:** 新增 `backend/scripts/replay_tw_old_wang.py`、`docs/ai/strategy-evaluation-ledger.md`；修改 `docs/ai/current-status.md`、`docs/ai/validation.md`、`docs/ai/handoff-log.md`。本機資料檔（ohlcv.csv 清理）不進 git。
- **Validation:** 全套 pytest 見完成回報（台股資料清理後必須全綠）；TW 回放腳本在清理後資料重現成功。docs 部分為 docs-only。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Notes / Warnings:** ledger 是 append-only 結論檔——新評估往下加，別改寫歷史判定。台股任何報酬計算前先跑 |單日漲跌|>10.5% 掃描。`.bak-20260712` 確認無誤後可自行刪除。

---

## 2026-07-12 — US universe 擴充：軍工航太 + AI 基礎設施（27 → 35 檔）

- **Date:** 2026-07-12
- **Task:** 使用者要求 universe 納入軍工、AI、SpaceX 等。**SpaceX 未上市無法納入**（已明確告知），以 RKLB 為太空類公開上市代表。
- **Completed:**
  - `us_leaders.json` +8：`Defense / Aerospace`（LMT/RTX/NOC/GD/RKLB）、`AI Infrastructure`（SMCI/VRT/CRWV）；note 註明 SpaceX 未上市。
  - 回補 5 年：新檔各 1,278 rows；CRWV（2025-03 IPO）322 rows → `min_row_count=322` 屬正常。
  - **零程式改動**：universe/status/analysis/signals、兩套觀察策略、前端分類 chip 全部動態承接。
  - api.md 更新（35 檔、兩個新分類、min_row_count 語意）。
- **Validation:** `tickers_with_data=35`、`missing/insufficient=[]`；trend-follow 候選 RTX#1/AMD/AAPL/NOW，新檔在 excluded 各有 reasons；W 底 GD 突破觀察中、RTX 已達標、LMT 失效；pytest 見完成回報。前端未改（分類 chip 動態產生），不需 build。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Notes / Warnings:** 2026 年把「當紅族群」（軍工/AI）加進清單，正是 wang_breakout 報告記錄的 **universe 事後選擇風險**的現在進行式——策略在新檔上的歷史回放數字會被此偏誤美化，別引用。CRWV 短史（<60 筆門檻已過但 <2 年），長窗指標與回放樣本少屬正常。SpaceX：未上市；別用 DXYZ 之類高溢價封閉式基金當替代納入。

---

## 2026-07-12 — 美股第二套觀察策略上線：us_wbottom_target（W 底突破 + 量幅目標）

- **Date:** 2026-07-12
- **Task:** 使用者要「勝率最高」並指示採用（「那美股就採用這個 然後幫我做起來」）。W 底 + 量幅目標在多出場法對比中勝率 62.4% 為所有測試最高，做成第二套觀察策略。**非推薦、非買賣建議、非下單；關鍵價位為觀察用。**
- **Goal:** production 觀察輸出 + 回放證據 + 已知代價全部落檔，UI 誠實揭露。
- **Completed:**
  - `us_wbottom_service.py`：偵測（`find_w_breakout`，swing±3 需 3 日確認 / 低距 10–40 / 價差 ≤3% / 頸線 = 兩低間最高 high / 突破 ≤20 日 / 軟濾網 SPY 或 QQQ > MA60）+ production 觀察輸出 `get_us_wbottom()`（狀態機：forming / breakout_today / breakout_in_progress / target_reached / invalidated；無型態只計數 `no_pattern_count`）+ 回放 `run_wbottom_replay()`（V1：量幅目標 / 型態低停損，D+1 open）——**單一規則來源，三者共用偵測**。參數凍結 2026-07-12。
  - `GET /api/markets/us/strategy/w-bottom`（router 薄轉發）+ api.md 完整規格（含回放證據與已知代價）。
  - `scripts/replay_us_wbottom.py`：輸出 `out/us_wbottom_replay_*.{json,csv}`（gitignored）；**重現對話中 scratchpad 評估**（282 筆 / 62.4% / target 183 / stop 99）。
  - 前端：「策略觀察：W 底型態」區塊（trend-follow 與觀察訊號之間）：軟濾網橫幅、型態表（狀態 badge / 頸線 / 型態低=失效 / 量幅目標 / 距目標 / 說明）、空清單明講是常態、風險提醒列（高勝率≠高獲利、空頭年為負、非下單）。types / client / CSS。
  - `test_us_wbottom.py` 15 測試：偵測邊界（間距 9/10、價差 3.9% 拒絕、突破新鮮度、>20 日拒絕）、竄改未來 bar 不影響訊號、觀察五態分類、gate 關閉註記、無型態=常態、回放 D+1 open / 目標 / 停損 / 確定性、endpoint schema。
  - 報告 `docs/ai/us-wbottom-replay-5y.md`（5 年年度分解含 2022 −5.87%、已知代價、結論：合格觀察工具、非 alpha）。
- **Changed Files:** 新增 `backend/app/services/us_wbottom_service.py`、`backend/scripts/replay_us_wbottom.py`、`backend/tests/test_us_wbottom.py`、`docs/ai/us-wbottom-replay-5y.md`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`、`frontend/src/types/index.ts`、`frontend/src/api/client.ts`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`、docs/ai（roadmap / current-status / validation / handoff-log）。
- **Validation:** 見完成回報（pytest / build / 瀏覽器實測）。
- **Git Status:** 乾淨（commit 後）。**未 push。**
- **Next Steps:** 觀察實際使用中型態出現頻率與狀態機是否直覺；候選：把 target_reached / invalidated 的歷史寫入決策日誌供覆盤。
- **Notes / Warnings:** 參數凍結不得調參；UI/API 的已知代價揭露不得移除；別把關鍵價位升級成買賣指令或自動觸發；偵測規則別複製到第三處（單一來源 `find_w_breakout`）。同輪較早的台股 old_wang 回放與美股型態三出場對比為 ad-hoc 分析（scratchpad），證據記錄於對話與本檔前後文。

---

## 2026-07-12 — us_wang_breakout（老王美股版）5 年回放驗證（evaluation-only）

- **Date:** 2026-07-12
- **Task:** 使用者要「老王型：有拼有止損」的美股策略。設計突破+量能進場、MA10 波段、−8% 硬止損、SPY/QQQ 軟濾網；一年首測 +1.46%/筆後**參數凍結**，回補 5 年資料（`--months 60`，2021-06～2026-07 含 2022 空頭）做樣本外重測 + 生存者偏差敏感度測試。**不下單、不推薦、不調參、不改 production。**
- **Goal:** 回答「這種策略能不能信」。
- **Completed:**
  - 5 年回補：27 檔 × 1,279 rows（ARM 自 2023-09 IPO 起），total 33,961（本機 gitignored）。
  - `us_breakout_replay_service.py`：walk-forward（窗口只用 index ≤ i）、D+1 open 成交、止損優先於 MA10 出場、`params_frozen` 記錄在 config、summary 含尾部集中度（top1/top5 share）與逐筆累計和最大回落；`scripts/replay_us_breakout.py` 輸出 out/*.{json,csv}（gitignored）。
  - `test_us_breakout_replay.py`（11 測試）：進場三條件、量能 1.5x 邊界、竄改未來 bar 不影響訊號、濾網擋訊號計數、ETF 不交易、−8% 止損（跳空以次日 open 結算）、MA10 連 2 日（單日不出）、最後一日 unresolved、確定性、參數凍結斷言。
  - 報告 `docs/ai/us-wang-breakout-replay-5y.md`（規則、方法學、年度分解、敏感度、結論下修）。
- **Key findings:**
  - 全 23 檔：343 筆、勝率 46.1%、**+1.77%/筆**、+607 點；2022 空頭年濾網把訊號壓到 20 筆、只虧 −23 點；top1 僅佔 8.6%；止損平均 −9.83%（最差 −22.18% 跳空穿價）。**機制層健全。**
  - **敏感度測試翻盤**：拿掉貢獻前 5（NVDA/TSLA/AMD/MU/ARM）→ 269 筆 **+0.39%/筆、+106 點、6 年中 5 年虧損**（只剩 2024 正）。利潤 ≈ 「2026 年選的 universe 裡剛好有 AI 五大贏家」= 生存者偏差。**edge 無法與後見之明分離。**
  - **評級：不建議照此下單**；可考慮做成第二套觀察策略（candidate/watch + 理由），其價值取決於使用者滾動維護 universe 的品質（回測無法驗證）。
- **Changed Files:** 新增 `backend/app/services/us_breakout_replay_service.py`、`backend/scripts/replay_us_breakout.py`、`backend/tests/test_us_breakout_replay.py`、`docs/ai/us-wang-breakout-replay-5y.md`；修改 docs（roadmap / current-status / validation / handoff-log）。production / API / 前端零改動。
- **Validation:** `python3.11 -m pytest -q` 見完成回報；5 年真實回放 + 敏感度重跑成功。
- **Git Status:** 乾淨（commit 後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps（若續）:** 1) 做成觀察策略上線（非推薦）；2) 資金配置模擬；3) 時點 universe 資料（唯一能真正回答 edge 的路）。
- **Notes / Warnings:** **參數已凍結，不得調參重測**（過擬合）；**別引用 +607 點當策略有效的證據**（敏感度已否定）；out/ 結果檔與 5 年 ohlcv_us.csv 均不 commit。

---

## 2026-07-11 — us_trend_follow 逐日回放驗證（evaluation-only）

- **Date:** 2026-07-11
- **Task:** 用既有 `ohlcv_us.csv` 對 us_trend_follow 做 walk-forward 逐日回放（訊號窗 2026-06-15～06-30，退出觀察到 2026-07-10），比較兩套 evaluation-only 退出規則，找出候選進出邏輯的問題證據。**不改 production 規則、不做參數最佳化、不下單、不重新抓資料。**
- **Goal:** 用證據回答「candidate_exit 是否太敏感、trend_protect 是否較合理、gate / 邊界是否有問題」。
- **Completed:**
  - `us_strategy_replay_service.py`：walk-forward（`_build_asof_item` 只吃 `date<=D` 前綴切片；候選判定直接呼叫 production `classify_trend_follow`，零複製）；D+1 open 成交、無下一 open → unresolved；兩套退出（candidate_exit / trend_protect_exit：gate inactive／close<MA60／連續 2 日 close<MA20）；每日快照 + churn；每筆 trade 含 mfe/mae/entry_reasons；摘要含 win rate、再入選、exit_reason 統計；`limitations` 揭露 Yahoo 非官方、無股息滑價、小樣本、規則層後見之明。
  - `scripts/replay_us_strategy.py`：輸出 `out/us_strategy_replay_<start>_<end>.{json,csv}`（gitignored）+ 終端摘要。
  - `test_us_strategy_replay.py`（13 測試）：竄改未來資料不影響 as-of 結果（無洩漏）、D+1 open 成交、最後一日訊號 unresolved、candidate_exit（含進場當日觸發）、連續 2 日 MA20 計數（單日跌破不出）、MA60 / gate 觸發、gate 關閉不產生訊號、MFE/MAE 數學、trade/summary 契約、確定性（跑兩次相等）。
  - 報告：`docs/ai/us-trend-follow-replay-2026-06.md`（方法 / 每日候選表 / 兩套比較 / 逐題證據 / 限制）。
- **Key findings（證據，未改規則）：** gate 全程 bullish（未被壓力測試）；11 天中 10 天清單變動；**candidate_exit 太敏感成立**——平均持有 1.9 天、16 筆中 8 筆 3 日內再入選，主因入選邊界被對稱當退出（dist>8% 移除 6 次=「因漲太快被踢出」、RSI<50 移除 5 次、ASML 差 0.03% 貼線移除）；**trend_protect 結構較合理**（9.3 天、再入選 1 次）但本窗口報酬 −2.29%（持有穿越 7 月初回檔，6 筆樣本不可下結論）；資料完整（窗口內零 no_data）→ 抖動是策略邊界特性非資料問題。
- **Changed Files:** 新增 `backend/app/services/us_strategy_replay_service.py`、`backend/scripts/replay_us_strategy.py`、`backend/tests/test_us_strategy_replay.py`、`docs/ai/us-trend-follow-replay-2026-06.md`；修改 docs（roadmap / current-status / validation / handoff-log）。**production 策略 / API / 前端零改動；out 結果檔不 commit。**
- **Validation:** `python3.11 -m pytest -q` 見完成回報；真實 27 檔回放成功（16 / 8 筆訊號）。
- **Git Status:** 乾淨（commit 後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 若要正式 entry/exit contract：以 trend_protect 型為基底 + 遲滯設計（另案、需更長樣本）；gate 壓力測試需含 bearish 時段的窗口。**仍不做推薦 / 買賣 / 下單 / 參數最佳化。**
- **Notes / Warnings:** replay 是 evaluation-only——**別接進 API / 前端 / 排程**；別在 replay 複製策略規則（必須 import production 的 classify）；別依 11 天樣本改參數。
---

## 2026-07-11 — US 觀察策略第一套：us_trend_follow（大盤守門的趨勢延續）

- **Date:** 2026-07-11
- **Task:** 依 Fable 策略設計採用第一套：趨勢追蹤 + ETF benchmark filter + 防追高的**觀察策略**（非推薦、非買賣建議、非下單）；第二套 us_pullback_watch 刻意不做。
- **Goal:** 27 檔裡「值得優先看哪幾檔、其他為何不在清單」一眼可判，且大盤不允許時誠實關門。
- **Completed:**
  - `us_strategy_service.py`：純函式 `classify_trend_follow(analysis_item, bias)` + 聚合 `get_us_trend_follow()`。
    - **守門**：bullish → active；mixed → active 但 candidate 降 watch + reason「大盤分歧」；bearish/unknown → `active=false`、candidates=[]、note=「大盤在 MA60 下方或資料不足，本策略今日不產生觀察對象」，原符合者移入 excluded 註明守門關閉。bias 複用 `us_watch_signal_service._market_context`。
    - **入選**：close > MA20 > MA60、50 ≤ RSI ≤ 68、0 ≤ dist_ma20 ≤ +8、20 日漲跌幅 > 0、非 ETF/Benchmark。
    - **排除**（依序，各附 reasons）：ETF 量尺→watch；資料不足（< `MIN_SIGNAL_ROWS`）→avoid；RSI ≥ 70 或 dist ≥ +15（引用 `OVERHEATED_*`）→overheated；跌破 MA60→avoid；recovering→watch「均線尚未翻多，修復中」；入選條件不符→watch（逐項列未通過原因）。
    - **排序**：dist 小→大 → 20 日漲幅大→小 → code；rank 1 起。**無 0–100 分數。**
  - `GET /api/markets/us/strategy/trend-follow`（router 薄轉發）+ api.md 完整規格（含 gate 三態、規則、範例）。
  - 前端：「策略觀察：趨勢延續」區塊（**放觀察訊號上方**）：gate 橫幅（綠/黃/灰）、candidates 表（rank/分類/狀態 badge/理由/風險）、excluded `<details>`「為何不在清單（N 檔）」、固定非推薦聲明；空清單時明講「不是故障，是規則關門」。types + client + CSS。
  - `test_us_strategy.py` 16 測試：合成 analysis item 驗規則邊界（RSI 68 進 / 69 watch / 70 過熱；dist 8 進 / 10 防追高 / 15 過熱）、gate 三態（monkeypatch get_us_analysis）、排序 tiebreak、ETF 不進候選、candidate 必有 reasons+risk_notes、無 score、endpoint schema。
- **Changed Files:** 新增 `backend/app/services/us_strategy_service.py`、`backend/tests/test_us_strategy.py`；修改 `backend/app/routers/markets.py`、`backend/docs/api.md`（含美股段落標題更新為觀察層總述）、`frontend/src/types/index.ts`、`frontend/src/api/client.ts`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/App.css`；docs（roadmap / current-status / validation / handoff-log）。
- **Validation:** `python3.11 -m pytest -q` → **884 passed**（+16）；`npm run build` 成功。真實 27 檔實測：gate bullish、candidates=[AMD #1（dist +4.5%）、AAPL #2（dist +5.38%）]、excluded 25（avoid 11 / watch 13 / overheated 1）全部有 reasons；前端區塊在觀察訊號上方、摺疊 25 檔、無 console error。（截圖工具本輪故障，以 DOM 驗證替代。）
- **Git Status:** 乾淨（commit 後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 觀察 us_trend_follow 清單抖動 1–2 週後再評估第二套 us_pullback_watch（規則已在 Fable 設計 C 段）。**仍不做推薦 / 買賣 / 下單 / launchd / 回測 / 新指標。**
- **Notes / Warnings:** 策略門檻 RSI 50–68、dist ≤ +8 **只在 us_strategy_service 定義**；過熱與資料量門檻引用既有常數，別複製。守門空清單是規則——別「修」成永遠有輸出。別把 state 升級成買賣語言或加分數。

---

## 2026-07-11 — US 美股頁操作體驗：資料狀態面板 + hash deep link

- **Date:** 2026-07-11
- **Task:** 美股頁頂部加資料狀態面板（消費 e323291 的 status 欄位）；美股頁支援 hash deep link（`#/us` / `#/markets/us`），header 切換同步 hash。前端純呈現，不做策略 / 推薦 / 下單 / launchd / 自動回補。
- **Goal:** 回補缺口在 UI 一眼可見；美股頁可分享連結、重整不掉回台股。
- **Completed:**
  - **資料狀態面板**（`UsMarketPage`）：資料源 `source_label`、`tickers_with_data`/`universe_size` pill（完整=綠「27/27 已更新，最少 256 筆」、不完整=黃）、資料日 + `days_since_last` +（stale 時）「已過期」tag、`min_row_count`、`missing_tickers` / `insufficient_tickers` 非空時以紅字列出代碼與數量、手動更新指令 `cd backend && python3.11 scripts/backfill_ohlcv_us.py --months 12`（**只顯示**，`user-select: all` 方便複製；無 run-backfill API）。原單行 `us-freshness` 資料日併入面板（CSS 已移除）。
  - **hash deep link**（`App.tsx`，沿用既有 hash routing、未引 React Router）：`parseHash` 回傳 `region`；`#/us` 正準、`#/markets/us` 別名（`US_HASH_PATHS`）；`region` 由 hash **lazy-init**（同 tab 的 StrictMode-safe 模式）；hashchange handler 用 `regionRef` 同步 region（US 時不動台股 tab 狀態）；state→hash effect：region=US 時若 hash 已是美股路徑（含別名）**不改寫**，否則設 `#/us`；切回台股還原原 tab path。
  - types：`UsMarketStatus` 補 `missing_tickers` / `insufficient_tickers` / `min_row_count`（e323291 後端已提供）。
- **Changed Files:** `frontend/src/App.tsx`、`frontend/src/pages/UsMarketPage.tsx`、`frontend/src/types/index.ts`、`frontend/src/App.css`；docs（current-status / validation / handoff-log）。**未動後端**；api.md 無 API 變更故未動。
- **Validation:** `npm run build` 成功；`python3.11 -m pytest -q` 見完成回報。瀏覽器實測：`#/us` 直達美股頁、重整仍在美股頁、`#/markets/us` 別名可用且不被改寫、台股↔美股切換 hash 同步（`#/today` ↔ `#/us`）、back/forward 正常；真實資料面板「27/27 已更新，最少 256 筆」；mock 缺資料變體正確列出「無資料（2）：DIA、IWM」「筆數不足（1）：ARM」+ 黃 pill + 已過期 tag；無 console error。
- **Git Status:** 乾淨（commit 後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 候選：回補腳本結尾驗收摘要、完整 NYSE 假日曆 + launchd。**仍不做美股正式推薦 / 買賣 / 下單。**
- **Notes / Warnings:** `#/markets/us` 別名**刻意不改寫**成 `#/us`（避免多餘歷史紀錄），別統一。region 必須維持 hash lazy-init，別改回 skip-first ref（StrictMode 會掉 deep link）。指令只顯示——**不要**加 run-backfill API 或前端觸發回補。

---

## 2026-07-11 — US status 回補可觀測性（missing / insufficient / min_row_count）

- **Date:** 2026-07-11
- **Task:** 手動回補後難以一眼判斷「補齊了沒」。`/status` 只有 `tickers_with_data`，不知道少了誰、也不知道誰有資料但太短。做最小高值切片改善可觀測性。
- **Goal:** `/api/markets/us/status` 能直接回答「哪些 ticker 沒資料 / 哪些有資料但不足以算 MA60 / 目前最小筆數」。
- **Completed:**
  - `get_us_market_status()` 新增三欄（聚合放 service，router 不動、維持薄）：
    - `missing_tickers`：`has_data=false` 的代碼清單（已排序）。
    - `insufficient_tickers`：有資料但 `row_count < MIN_SIGNAL_ROWS`（=60）的代碼清單（已排序）。
    - `min_row_count`：所有有資料 ticker 的最小 `row_count`（無資料 → `None`）。
  - **門檻引用既有常數**：`us_market_service` 從 `us_watch_signal_service` `import MIN_SIGNAL_ROWS`，不在此處另寫死 60（CLAUDE.md §10）。import 方向無循環（watch_signal_service 不反向依賴 market_service，已驗證）。
  - 修 `backfill_ohlcv_us.py` argparse 描述殘留的「Stooq，免 key」→「Yahoo Finance，免 key」。
  - 測試：status schema 增三欄 + 型別；no-data 全 missing / insufficient=[] / min=None；混合 fixture（AAPL 65、MSFT 30）驗 missing 與 insufficient 互斥、`min_row_count=30`、門檻=60。
- **Changed Files:** `backend/app/services/us_market_service.py`、`backend/scripts/backfill_ohlcv_us.py`、`backend/tests/test_us_market.py`、`backend/docs/api.md`；docs（current-status / validation / handoff-log）。**未動前端**（本切片不做 UI）。
- **Validation:** `python3.11 -m pytest -q` → 見完成回報；真實 27 檔：`missing_tickers=[]`、`insufficient_tickers=[]`、`min_row_count`≈256。
- **Git Status:** 乾淨（commit 後）。
- **Commit:** 見完成回報。**未 push。**
- **Next Steps:** 候選：回補腳本結尾驗收摘要（呼叫 service，本輪刻意未做）、完整 NYSE 假日曆 + launchd、前端把 missing/insufficient 顯示在美股頁。**仍不做美股正式推薦 / 買賣 / 下單。**
- **Notes / Warnings:** `insufficient_tickers` 門檻**只有一個來源** `MIN_SIGNAL_ROWS`——別在 market_service 重寫 60。`missing`（沒資料）與 `insufficient`（有資料但短）語意不同、互斥，別合併。

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
