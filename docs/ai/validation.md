# Validation

> 這個專案怎麼驗收。AI 完成任務後，依本檔驗收並在回報中記錄結果。
> 指令以本 repo 實際內容為準（見下方 Known Test Commands），不要沿用其他專案的猜測指令。
> Last updated: 2026-07-09

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

## Known Test Commands

> 這個專案實際可用的指令清單（讓 AI 不用猜）。

| 目的 | 指令 |
| --- | --- |
| 後端測試 | `cd backend && python3 -m pytest -q` |
| 後端啟動 | `cd backend && uvicorn app.main:app --reload --port 19000` |
| 前端 build（含 typecheck） | `cd frontend && npm run build` |
| 前端 dev server | `cd frontend && npm run dev`（port 5173，proxy `/api` → `127.0.0.1:19000`） |
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
