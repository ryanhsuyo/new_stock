# Validation

> 這個專案怎麼驗收。AI 完成任務後，依本檔驗收並在回報中記錄結果。
> 指令以本 repo 實際內容為準（見下方 Known Test Commands），不要沿用其他專案的猜測指令。
> Last updated: 2026-07-24

## Required Checks

> 每次改動**都必須**通過的檢查（依改動範圍取用；docs-only 例外見下方）。

- [ ] 動到後端 `backend/app`、`backend/scripts`、`backend/tests` → 後端測試全綠：`cd backend && python3 -m pytest -q`。
- [ ] 動到前端 `frontend/src` → 前端 build 成功（含型別檢查）：`cd frontend && npm run build`。

## Optional Checks

> 視改動範圍決定是否要跑。

- [ ] 資料流冒煙：`cd backend && python3 scripts/daily_update.py --months 1`（會連 TWSE / 寫檔，非必要時可跳過）。
- [ ] 健康檢查：`cd backend && python3 scripts/doctor.py`。
- [ ] 每日健康檢查快照：`cd backend && python3 scripts/daily_check.py --write-report`。
- [ ] 前端手動實測互動流程（見 Manual Verification）。
- [ ] 盤前風險中心：確認 stale 行情顯示「待確認」而非「正常」、官方來源可展開，且手機寬度無整頁橫向溢出。
- [ ] 盤前風險零分狀態顯示「未觸發額外防守」，不可宣稱「正常／安全」；需提醒盤中突發新聞、跳空與市場廣度仍可能改變風險。

## Docs-only Rules

> 若本次**只改文件 / 註解 / markdown**（不含 runtime code）：

- 不需要跑完整測試套件。
- 但仍要在回報中**明確說明**：這是 docs-only 改動，所以未跑測試。
- 本 repo 目前沒有 markdown lint / 連結檢查工具；若日後新增，仍應跑。

## Manual Verification

> 無法自動化、需要人工確認的項目。

- 啟動後端 + 前端後，打開 `http://localhost:5173`，確認 Dashboard 有資料（資料日 / 最後更新非「—」）。
- 研究頁動線：Today → 研究 → rail 切股 → 搜尋切股 → 瀏覽器 back/forward 一致；deep link（`#/research/<code>`）重整能還原。
- 美股頁動線：`#/us`（或別名 `#/markets/us`）直達美股頁、重整仍留在美股頁；header 台股/美股切換同步 hash、back/forward 一致；頂部資料狀態面板：資料完整時顯示覆蓋率，缺資料 / 筆數不足時列出代碼；「立即更新美股」觸發獨立 US background backfill，按鈕進入更新中、3 秒輪詢，成功後自動刷新，失敗顯示錯誤。
- 後端關閉時，Dashboard 頂部應出現明確錯誤 / 連線中斷橫幅（不是靜默空白）。
- 台股策略驗收：重跑含大跌日的區間後，確認「組合風控已啟用」顯示當前 mode 的實際策略別限制，且逐筆略過原因可展開；盤前風險只使用成交日前資料，防守／極端／資料不足日不得新開倉。此結果只供 evaluation，不得改動 production 訊號。
- 台股計畫停損驗收：持倉須保存訊號日 `stop_price`；盤中最低價觸及時以停損價套賣出滑價，跳空低開跌破時以開盤價套賣出滑價，且同日不得再重複執行日線退出。報告需顯示停損次數。
- 停損重進驗收：個股在 D 日計畫停損後，同一個 D 日收盤訊號不得排入 D+1 重買；`skipped_entries` 需留下 `same_day_stop_reentry`，但不得自行延伸為任意多日冷卻。
- 風險恢復驗收：防守／極端／資料不足後首個 normal 日只使用 watch 容量；`risk_by_day` 同時保留原始 `level`、`effective_level` 與 `recovery_confirmation`。至少比較近期、較長及拆分窗口，不得只採用單一區間結果。
- **不當沖（使用者規則，2026-08-03，台股與美股皆適用）**：任何部位都必須至少持有一個交易日，`exit_date` 必須嚴格晚於 `entry_date`。回放、前推驗收與報告都不得產生同日進出，也不得用「當天開盤→收盤」估算未平倉損益——那是一筆當沖損益。訊號進場日剛好是資料末日時，該筆標 `awaiting_next_session` 並排除於績效統計，不得補一個當日報酬。進場當天就跌破失效價時，出場仍是下一個交易日開盤。
- **護欄在 production 的驗收（2026-08-02 起）**：進場候選在盤前風險 defensive／extreme、超過每日新倉或總曝險上限、或老王濾網為 block（僅 combined／old_wang）時，必須從「今日可能進場／觀察」移除並出現在「今日不新增（風控擋下）」，帶人看得懂的原因而非 reason_code；今日結論的分桶數必須加總回候選總數。護欄不得影響賣出、減碼與出場警示。**恢復台股下單前必須重新檢視是否維持 `GUARDRAILS_ENABLED`——護欄驗收結論仍是未通過。**
- 三份 per-profile 報告：同一檔可在某 profile 進場、在另一 profile 被擋。每份報告必須印出「上限僅在本報告內有效，同時依多份報告進場會放大實際曝險」。任一份未在本輪重新產生時，排程不得寫成功 marker。
- 盤前風險降級推估：production 不得輸出 `unknown`。輸入不完整時推出的等級**不得寬鬆於可得資料所支持的等級**（缺資料不得產生比較安全的結論），並標示 `degraded` 與缺漏項。
- 訊號前推驗收：進場基準必須是快照 `generated_at` 之後的第一個交易日開盤，不得用 `as_of`；出場只用訊號當日記錄的失效價；缺失效價的訊號標 `no_stop_defined` 並排除於勝率統計，不得補值。台股與美股樣本不得合併計算。
- 證據狀態區塊：必須出現在「今日結論」之前；樣本為 0 時要印出窗口內實際涵蓋的快照日數，並說明 0 筆是紀錄不足而非訊號不存在。不得新增綜合評分、健康度或策略排名。
- 美股 signal snapshot：每日保存全部桶（含已失效），同一 `as_of` 重複執行覆寫而非新增；快照未寫出時該次執行不得標記成功。前推只有「可紙上追蹤」桶計分；**不得改用觀望桶充樣本、不得延長窗口湊樣本、不得用量幅目標當停利出場**。
- Dashboard 策略驗收摘要：確認保存份數與最新區間正確，三模式皆顯示報酬／MDD／買賣／略過數；「查看完整報告」跳到 `#/validation`。375px 寬度卡片單欄且整頁無橫向溢出。
- 官方事件摘要：只顯示人工查證的未來 14 天官方事件、來源連結與查證日；超過 7 天未查證需提示過期。事件不得直接改變盤前風險分數，也不得宣稱涵蓋即時或突發新聞。
- 交易紀錄完整性：`#/trades` 若有異常成交價須顯示「績效暫估」與待確認筆數；單筆修正不得允許改股票／方向，儲存後需刷新狀態，且 `backend/data/backups/` 留下修改前備份。
- 分市場報告：台股每日行動報告不得混入逐筆歷史交易；歷史稽核使用獨立 artifact。若 `universe_report.csv` 任一逐股資料日未對齊 summary `as_of`，Today Scan 與台股日報都必須阻擋交易輸出／動作清單；台股排程為 15:40。美股主要決策清單的已突破 W 底不得在下方詳表重複出現。

## Known Test Commands

> 這個專案實際可用的指令清單（讓 AI 不用猜）。

| 目的 | 指令 |
| --- | --- |
| 後端測試 | `cd backend && python3 -m pytest -q` |
| 後端啟動 | `cd backend && uvicorn app.main:app --reload --port 19000` |
| 前端 build（含 typecheck） | `cd frontend && npm run build` |
| 前端 dev server | `cd frontend && npm run dev`（port 5173，proxy `/api` → `127.0.0.1:19000`） |
| 分市場報告 | `cd backend && python3.11 scripts/generate_strategy_trade_report.py --market tw\|us [--as-of YYYY-MM-DD]` |
| 每日更新 | `cd backend && python3 scripts/daily_update.py --months 1` |
| 產生訊號 | `cd backend && python3 scripts/run_signals.py` |
| 今日掃描 | `cd backend && python3 scripts/today_scan.py` |
| 健康檢查 | `cd backend && python3 scripts/doctor.py` |
| 每日健康檢查 | `cd backend && python3 scripts/daily_check.py --write-report` |
| 美股回補（免 key） | `cd backend && python3.11 scripts/backfill_ohlcv_us.py [--months N]` |
| 排程安裝（台+美，launchd） | `bash backend/scripts/setup_schedule.sh`（`ASSUME_YES=1` 免互動；卸載用 `remove_schedule.sh`） |
| 排程 wrapper 決策檢查 | `cd backend && python3.11 scripts/scheduled_update.py --market tw\|us --dry-run` |

### 美股（US Market）驗收 —— 分兩層

- **資料源方向**：主源 = **Yahoo Finance chart endpoint（免 API key、非官方、best-effort）**；**Stooq 已停用**（需瀏覽器 JS 驗證）；Finnhub = future optional（`FINNHUB_API_KEY`，不進 git）。

**A. AI 可自行驗收（不需真實對外網路）：**
- `python3.11 -m pytest -q` 全綠：`test_us_market.py`（Yahoo 解析 / Stooq 停用 / Finnhub 缺 key / 資料新鮮度 / universe + category / status 回補可觀測性 `missing_tickers` · `insufficient_tickers` · `min_row_count`）、`test_us_analysis.py`（指標數學、**六種狀態**、fixture 端到端）、`test_us_watch_signals.py`（五種觀察訊號、SPY/QQQ 大盤基準、fixture 端到端、no-data 誠實、`/markets/us/signals` schema）、`test_us_strategy.py`（us_trend_follow：gate 三態 + 關門空清單、RSI 68/69/70 與 dist 8/10/15 邊界、ETF 不進候選、candidate 必有 reasons + risk_notes、排序 tiebreak、無 0–100 分數、endpoint schema）。
- US 觀察策略 `/markets/us/strategy/trend-follow`：**非推薦、非買賣、非下單**；`market_gate.active=false`（bearish/unknown）時 `candidates=[]` 是規則不是故障；每筆 excluded 都要有 reasons。
- us_trend_follow 回放（evaluation-only）：`test_us_strategy_replay.py`（walk-forward 無未來洩漏、D+1 open 成交、candidate_exit / trend_protect_exit、連續 2 日跌破 MA20 計數、MFE/MAE、unresolved、確定性）；真實回放：`cd backend && python3.11 scripts/replay_us_strategy.py`（讀既有 ohlcv_us.csv，不打網路；輸出 `out/us_strategy_replay_*.{json,csv}`，gitignored）。報告：`docs/ai/us-trend-follow-replay-2026-06.md`。
- us_wbottom_target（W 底觀察策略）：`test_us_wbottom.py`（型態偵測邊界：低點確認 3 日 / 間距 10–40 / 價差 3% / 突破新鮮度與 ≤20 日、無未來洩漏、量幅目標數學、觀察狀態機五態、gate 關閉註記、回放 D+1 open 與目標 / 停損出場、確定性、endpoint schema）；真實回放：`cd backend && python3.11 scripts/replay_us_wbottom.py`。報告：`docs/ai/us-wbottom-replay-5y.md`。
- 排程 wrapper：`test_scheduled_update.py`（門檻前不跑、無 marker 跑、當日已成功跳過、隔日開機補跑、門檻前的成功不算數、美股 08:30 門檻）。launchd 實測：載入後兩 agent 端到端 exit 0、markers 寫入、`launchctl start` 重複觸發正確跳過。
- 台股 old_wang 桶回放（evaluation-only）：`cd backend && python3.11 scripts/replay_tw_old_wang.py`（候選判定 = production 訊號管線 as-of 截斷、零複製規則；同步 pool 換速度；輸出 `out/tw_old_wang_replay_*.json`，gitignored）。無獨立測試（重用已測的 production 管線；模擬層與 US 回放同構）。結論見 `docs/ai/strategy-evaluation-ledger.md`。
- us_wang_breakout 回放（evaluation-only，參數凍結）：`test_us_breakout_replay.py`（進場三條件與量能邊界、無未來洩漏、大盤濾網擋訊號、D+1 open、−8% 止損、MA10 連 2 日出場、unresolved、確定性、參數凍結斷言）；真實回放：`cd backend && python3.11 scripts/replay_us_breakout.py`。報告（含生存者偏差敏感度測試）：`docs/ai/us-wang-breakout-replay-5y.md`。
- `/api/markets/us/status` 回補可觀測性：27 檔全數回補後 `missing_tickers=[]`、`insufficient_tickers=[]`、`min_row_count`≈256；缺資料 / 筆數不足的 fixture 下能正確分出「無資料」與「有資料但 < 60 筆」（互斥）。門檻沿用 `MIN_SIGNAL_ROWS`，非另寫死。
- US 觀察訊號：`/markets/us/signals` 用 **fixture `ohlcv_us.csv`** 或真實資料回**每檔 leader 一筆** + `market_bias`；`ohlcv_us.csv` 不存在 → 全 `avoid_weak` / `market_bias=unknown`（誠實）。**非推薦、非買賣、非下單。**
- `npm run build` 成功。
- API 在**無資料**時：`/markets/us/analysis` 回 `no_data` + 指標 null；用 **fixture** 時算出 MA/RSI/漲跌幅並歸類狀態。狀態六種：`trend_up` / `recovering` / `pullback_watch` / `overheated` / `weak` / `no_data`——**`no_data`（算不出來）與 `weak`（跌破 MA60）必須分開**，資料完整的股票不得顯示為「資料不足」。
- 前端：缺資料誠實顯示；有資料顯示指標 + 狀態 badge。**驗收用 fixture 後務必刪除 `backend/data/ohlcv_us.csv`（gitignored），以免污染真實回補。**

**B. 需使用者本機（真實 Yahoo）後續驗收：**
- `cd backend && python3.11 scripts/backfill_ohlcv_us.py --months 12`（**免 key**）；需**正常對外網路**（自簽憑證代理環境會 `CERTIFICATE_VERIFY_FAILED`，backfill 會優雅 skip）。
- `backend/data/ohlcv_us.csv` 實際產生（只寫此檔，**不動台股 `ohlcv.csv`**）。
- `/api/markets/us/status` 顯示 `tickers_with_data > 0`。
- 前端美股頁顯示**真實**收盤價 / 資料日 / 指標 / 狀態。

> 注意事項（repo 實況，勿改成錯的）：
> - 後端 port 是 **19000**（不是 9000）。
> - 前端套件管理器是 **npm**（`frontend/package-lock.json`），build 指令為 `npm run build`（不是 `pnpm build`）。
> - 後端依賴（fastapi / uvicorn / pytest / httpx，另用 pandas / numpy / requests）在本機以 **`python3.11`** 安裝；若 `python3` 預設不是 3.11，請用 `python3.11 -m pytest -q`，否則會因缺依賴而失敗。
> - 測試不得依賴真實網路（TWSE），需用固定測資。

## How to Report Unrun Tests

> 若某些檢查**沒有跑**（環境限制、docs-only、時間不足、指令失敗等），必須誠實回報，不可假裝通過。

回報時請包含：

- **哪些檢查沒跑** — 明列。
- **為什麼沒跑** — docs-only / 環境缺依賴（例如 interpreter 非 python3.11）/ 指令不存在 / 時間 / 其他。
- **風險評估** — 沒跑這些檢查可能漏掉什麼。
- **建議** — 下一個接手的人該補跑什麼。
