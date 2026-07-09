# Roadmap

> 專案的方向與規劃。用 Now / Next / Later 分層，細節放在各 Phase。
> 規劃改變時就更新這裡。
> Last updated: 2026-07-09

## Vision

打造一個**自用、可解釋、可信任**的台股決策工作台：資料流穩定跑通，訊號與候選股都能說明「為何買 / 為何不買 / 為何不是入場點」，前端只做呈現與決策動線；**不碰自動交易**。

## Now

> 現在正在做 / 即將做的（對應 `current-status.md` 的 Current Phase）。

- 前端研究頁 UX 與可觀測性收尾（rail、hash 路由、錯誤橫幅、連線偵測）。
- 導入 AI Project Handoff Standard（本次 docs-only）。

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
