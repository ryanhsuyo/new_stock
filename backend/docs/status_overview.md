# 系統現況總表 & 待辦優先清單

> 最後更新：2026-06-27
> 狀態快照，建議每次重大里程碑後更新。

## 0. 目前執行狀態

| 項目 | 目前狀態 |
|------|----------|
| Active phase | 無。`backend/docs/ai_execution_plan.md` 與 `backend/docs/ai_tasks/loop_state.md` 皆為 `none` |
| 最近完成 | D1.0 — Daily Check / Today Scan 可解釋性欄位與回歸測試 |
| 目前策略 | 只保留兩個推薦策略：`old_wang` 與 `steady_momentum` |
| 內部訊號 | `core_technical_v2` 僅作為技術訊號引擎，不是推薦桶 |
| 基本面定位 | 基本面避雷 / 補資料只輔助 `steady_momentum`，不產生獨立候選股 |
| 最新 Daily Check | `generated_at=2026-06-27`、`data_as_of=2026-06-26`、`overall_status=warn`、`can_use_trade_outputs=true` |
| 最新 Today Scan | `as_of=2026-06-26`、可小試 7、老王觀察 5、穩健動能 17、風險處理 21 |
| 目前主要阻塞 | 真實外部基本面資料尚未匯入；不可偽造基本面數字 |
| 自動心跳下一步 | 若無新資料或新需求，應安靜巡檢；有真實基本面 CSV 或明確下一個 phase 後才繼續開發 |

---

## 1. 已完成功能總表

### 1.1 資料層

| 功能 | 檔案 | 說明 |
|------|------|------|
| TWSE OHLCV 回補 | `scripts/backfill_ohlcv_twse.py` | 按月份拉取，1.2s 節流，(code,date) 去重 merge |
| 股票代碼清單管理 | `backend/data/leaders.json` | 支援巢狀結構，backfill 自動攤平 |
| 歷史資料儲存 | `backend/data/ohlcv.csv` | 約 474 KB，欄位：date, code, open, high, low, close, volume |
| 本地交易日曆 | `backend/data/trading_calendar.json`（選填） | 可設定休市日與補班交易日；缺檔時退回週一至週五 |
| 資料覆蓋率報告 | `backend/out/data_coverage_report.json` | 追蹤股票 `ok` / `missing` / `insufficient` / `lagging` 狀態、coverage 與 batch_id |
| 交易紀錄持久化 | `backend/data/trades.json` | UUID 主鍵，含 buy/sell 雙向 |
| 持倉快照（選填） | `backend/data/positions.json` | 目前由 trades.json 推算，非必要 |
| 自選清單持久化 | `backend/data/watchlists.json` | 群組 + 個股，idempotent CRUD |

### 1.2 訊號計算層

| 功能 | 服務 | 說明 |
|------|------|------|
| 7 狀態訊號系統 | `signals_service._compute_signal` | watchlist / ready_to_enter / entry_confirmed / hold / take_profit_warning / exit_warning / invalidated |
| 技術指標 | 同上 | MA5 / MA20 / MA60 / RSI14 / vol_ratio |
| 長短線趨勢判斷 | 同上 | 長線：MA60 關係；短線：MA20+MA60 關係 |
| 支撐壓力線 | `analysis_service` | 20/60 日靜態高低點 + MA20/MA60 動態線 |
| 趨勢線（擺動點） | 同上 | 5 Bar 窗口找擺動高低點；優先三點以上、2% 容差的多點確認，無候選時回退最近兩點 |
| W 底辨識 | `pattern_service` | 兩相近擺動低點 + 頸線；forming/confirmed/failed |
| M 頂辨識 | 同上 | 兩相近擺動高點 + 頸線；forming/confirmed/failed |
| 分數計算（附原因） | 同上 | 50 基礎分，各條件加減分，必附 reasons + risk_notes |
| 全量訊號輸出 | `run_daily_signals` | 產出 summary.json + universe_report.csv（含 no_buy_reason） |
| 訊號 lineage | `summary.json.batch_id` / `lineage` | 完整更新沿用 update batch；手動重算產生 signal-only batch |
| 歷史日期模擬 | `?as_of=YYYY-MM-DD` | signals / analysis 均支援 as_of 參數 |
| Core 單股回測 | `backtest_service` / `run_backtest.py` | D 日收盤訊號、D+1 開盤成交、滑價／費稅、交易明細、回撤與 buy-and-hold 比較 |
| 兩策略推薦桶 | `summary.json.recommendation_buckets` | 對外只列 `old_wang` 與 `steady_momentum` |
| 基本面避雷輔助 | `fundamental_service` | 只作為穩健動能的資料輔助與補資料流程，不產生獨立候選股 |

### 1.3 API 層（全部 endpoints）

| Endpoint | 方法 | 說明 |
|----------|------|------|
| `/stocks/recommendations` | GET | BUY 訊號股清單（含 score/reason/risk_warning） |
| `/stocks/universe` | GET | 所有追蹤股票的資料覆蓋狀況 |
| `/stocks/{code}/analysis` | GET | 單股深度分析（含 120 根 K 棒、支撐壓力、趨勢線、型態） |
| `/stocks/signals/status` | GET | 輸出檔案存在與否 + 時間戳 |
| `/stocks/signals/run` | POST | 觸發訊號計算（背景執行，透過 status 輪詢） |
| `/stocks/signals/summary` | GET | 讀取 summary.json |
| `/stocks/signals/universe_report` | GET | 下載 universe_report.csv |
| `/trades` | GET | 交易紀錄清單 |
| `/trades/buy` | POST | 記錄買入（含持股驗證） |
| `/trades/sell` | POST | 記錄賣出（含超賣驗證） |
| `/portfolio` | GET | 持倉損益（均攤成本 + 未實現損益） |
| `/portfolio/positions` | GET | 原始持倉（無報價） |
| `/portfolio/analysis` | GET | 持倉 + 技術訊號（依緊急度排序） |
| `/portfolio/summary` | GET | 投組摘要（總成本 / 收盤估值 / 損益 / 訊號分布） |
| `/stats` | GET | 月結 / 全期統計（買賣次數 / 勝率 / 已實現損益） |
| `/system/data-status` | GET | 更新狀態 + stale 計算 |
| `/system/update-now` | POST | 觸發背景更新（409 if already running） |
| `/system/daily-check` | GET | 讀取 Daily Check 快照 |
| `/system/pm-worklist` | GET | 讀取 PM Worklist 與 Primary Action |
| `/system/fundamentals-status` | GET | 基本面避雷覆蓋率、priority CSV 狀態與補資料 workflow |
| `/system/fundamentals-priority-fill` | GET | 下載優先補資料 CSV |
| `/system/fundamentals-priority-fill/merge` | POST | 預覽 / 確認合併優先補資料 CSV |
| `/watchlists` | GET/POST | 自選清單群組 CRUD |
| `/watchlists/{group}` | DELETE | 刪除群組 |
| `/watchlists/{group}/stocks` | POST | 加入個股 |
| `/watchlists/{group}/stocks/{code}` | DELETE | 移除個股 |

### 1.4 更新排程層

| 功能 | 說明 |
|------|------|
| 背景更新（API 觸發） | `trigger_background_update` + threading.Lock 防重複 |
| CLI 更新腳本 | `scripts/daily_update.py` 為日常入口；底層沿用 `scripts/update_all_data.py`，PID 鎖，支援 `--months N` |
| 更新狀態持久化 | `backend/out/update_status.json`（running / success / failed + error） |
| stale 計算 | 交易日邏輯，支援本地休市 / 補班交易日覆寫 |
| 覆蓋率阻塞 | coverage < 80% 時 Update Workflow / Daily Check blocked |
| macOS 排程 | `scripts/setup_schedule.sh` / `remove_schedule.sh`（launchd） |
| cron 範例 | `scripts/cron_example.txt` |

### 1.5 前端層

| 頁面 | 主要功能 |
|------|---------|
| 訊號 Dashboard | Decision Console、Primary Action、Today Focus、PM Worklist、Daily Check、檔案健康檢查 |
| 推薦清單 | 推薦股票卡片、一鍵買入 Modal |
| 技術分析 | K 線圖（MA5/20/60 + 支撐壓力線 + 趨勢線）、分析面板（型態/訊號/評分）、鍵盤導航 |
| 觀察清單 | 群組 CRUD、個股加入 / 移除 |
| 投組總覽 | 資料新鮮度列、持倉摘要、可排序持股清單（點擊跳轉技術分析） |
| 持倉損益 | 持倉表格（成本/損益）+ 技術訊號卡片 |
| 交易紀錄 | 買賣歷史清單 |
| 統計 | 月結 / 全期統計（勝率 / 損益） |
| 前端觸發更新 | POST /system/update-now、3s polling、完成後自動刷新資料 |

### 1.6 測試覆蓋

| 測試檔案 | 涵蓋面 |
|---------|--------|
| `test_update_status.py` | 更新狀態讀寫、stale 計算、batch lineage、API schema、409 防重複 |
| `test_trading_calendar_service.py` | 本地交易日曆、休市日、補班交易日與 fallback |
| `test_data_coverage_service.py` | coverage report 分類、寫檔與 expected outputs |
| `test_signals_api.py` | signals endpoint schema、空資料行為 |
| `test_pattern_service.py` | W 底 / M 頂 / 頭肩底 / 頭肩頂 forming/confirmed/failed 與幾何拒絕條件 |
| `test_signals_pattern.py` | 型態分數、reasons / risk_note 與 CSV 整合 |
| `test_stock_analysis.py` | 個股分析、支撐壓力線計算 |
| `test_holdings.py` | 持倉計算、未實現損益 |
| `test_portfolio_summary.py` | 投組摘要欄位與計算 |
| `test_watchlists.py` | 自選清單 CRUD + 邊界條件 |
| `test_notify.py` | 通知 stub |
| `test_schedule.py` | 排程機制 |
| `test_fundamental_service.py` | 基本面避雷資料驗證、priority CSV、模板與匯入流程 |
| `test_fundamentals_cli.py` | 基本面 CLI、template / dry-run / apply 與文字輸出 |
| `test_today_scan_service.py` / `test_today_scan_cli.py` | 今日規則掃描與分桶輸出 |
| `test_daily_check.py` / `test_doctor.py` / `test_pm_worklist.py` | Daily Check、Doctor、PM Worklist 與補資料 workflow |

---

## 2. 已知限制

### 2.1 資料層

| 限制 | 影響 | 說明 |
|------|------|------|
| TWSE / TPEX 資料來源格式可能變動 | 回補需觀察來源錯誤 | 目前已支援 TWSE 與 TPEX fallback，特殊商品仍需確認 |
| `ohlcv.csv` 無索引 | 持倉多時讀取略慢 | 目前 50 支股票可接受；超過 200 支需優化 |
| 未實現損益用歷史收盤價 | 非即時報價 | 需 WebSocket / 輪詢外部 API 才能做即時報價 |
| JSON 儲存交易紀錄 | 不適合大量資料 | 數千筆以內無問題；更多需遷移至 SQLite |
| `positions.json` 目前未積極維護 | 與 trades.json 功能重疊 | 可考慮移除或改為快取用途 |

### 2.2 訊號層

| 限制 | 影響 | 說明 |
|------|------|------|
| 最少需要 60 根 K 棒 | 新上市股或資料不足時顯示 DATA_MISSING | 合理限制，短期不改 |
| 型態已支援 W 底 / M 頂 / 頭肩底 / 頭肩頂 | 複雜型態仍可能誤判 | 型態新鮮度與距離權重仍可優化 |
| 趨勢線 API 只回傳兩個定義端點 | 圖表不顯示全部觸點 | 已用多點觸碰驗證選線；尚未採回歸線或 `anchors[]` 合約 |
| CLI 訊號計算為同步 | 60 支股票約 5–10 秒 | API 已背景觸發；CLI 仍是批次同步流程 |
| `_STOCK_NAMES` 硬編碼 | 新增股票需手動維護名稱對照 | 可改為從 leaders.json 讀取 |
| 基本面避雷覆蓋率不足 | `overall_status=warn`，但交易輸出仍可回顧 | 需要使用者提供真實外部基本面資料；不可用技術資料或假數字補齊 |
| 基本面輔助欄位需避免誤讀 | 容易被誤會成第三策略 | `fundamental_*` 是正式基本面輔助欄位，不代表推薦策略 |

### 2.3 API 層

| 限制 | 影響 | 說明 |
|------|------|------|
| 無認證機制 | 不可公開暴露 | 所有人共用同一份交易資料 |
| `POST /signals/run` 為背景觸發 | 需透過 status 輪詢結果 | 與 update-now 類似，避免 API 長時間等待 |

### 2.4 前端層

| 限制 | 影響 | 說明 |
|------|------|------|
| Tab 導航不支援 URL 深連結 | 無法分享特定分析頁面 | 需加入 React Router |
| 股票搜尋僅含 40 支預設 | 搜尋體驗有限 | 已可從 `/stocks/universe` 取得完整清單 |
| 無登入機制 | 多人使用會衝突 | 本機單人使用無問題 |
| 行動版未最佳化 | 手機閱讀體驗差 | 桌面版優先，RWD 為後期項目 |

---

## 3. 待辦優先級清單

### 🔴 高優先（阻塞實際使用 / 資料正確性）

| # | 項目 | 說明 | 估時 |
|---|------|------|------|
| R10 | **匯入真實基本面資料** | 等使用者提供外部 CSV 後，走 template / dry-run / apply / merge / run_signals；不可偽造資料 | 外部資料到位後 0.5d |
| D1 | **保持 Daily Check / Today Scan 可解釋** | 目前可用但 WARN；若更新資料後 counts 或 blocker 改變，需同步檢查 daily_check / today_scan | 持續 |

### 🟡 中優先（改善可觀測性與分析品質）

| # | 項目 | 說明 | 估時 |
|---|------|------|------|
| M1 | **補充真實基本面後的驗收報告** | 合併基本面資料後，確認覆蓋率、基本面避雷分數、summary / universe_report / Daily Check 文字一致 | 0.5d |
| M2 | **候選股表格持續降低資訊密度** | 已固定股票身份欄並折疊長理由；後續可再優化欄位密度與手機閱讀 | 1d |
| M3 | **universe_report 加入型態欄位** | 已完成：CSV 已輸出 `pattern_type` / `pattern_status`，並有固定測試驗證合法值 | — |
| M4 | **`notify_service` 最小通知** | 已完成：支援 opt-in macOS 通知與 Slack Incoming Webhook，並有成功/失敗隔離測試；不宣稱支援 LINE 或 Email | — |
| M5 | **每支股票計算時間過長時的 timeout 保護** | 已完成：逐檔 spawn process timeout、可解釋 fallback、summary / CSV / CLI 逾時資訊與後續股票續跑測試 | — |
| M6 | **`positions.json` 持倉來源職責** | 已完成：`trades.json` 成功載入即為權威來源，空持倉不回退；只有主來源例外才讀取舊 `positions.json` 備援 | — |

### 🟢 低優先（品質改善 / 未來擴充）

| # | 項目 | 說明 | 估時 |
|---|------|------|------|
| L1 | **即時報價整合** | 需對接外部 WebSocket 或輪詢 API；目前用歷史收盤價 | 2–3d |
| L2 | **多點趨勢線** | 已完成：三點以上觸碰、2% 容差、破線失效、候選排序與兩點 fallback；未採回歸線 | — |
| L3 | **CORS 環境變數設定** | 已完成：支援逗號分隔 `CORS_ALLOWED_ORIGINS`、localhost 安全預設、wildcard 拒絕與 preflight 測試 | — |
| L4 | **React Router + URL 深連結** | 讓特定分析頁面可直接分享 URL | 1d |
| L5 | **SQLite 遷移（交易 / 訊號快取）** | 資料量超過數千筆時 JSON 效能下降 | 2d |
| L6 | **使用者認證（簡單 token）** | 若要部署給多人使用 | 1–2d |
| L7 | **行動版 RWD 優化** | 桌面版已穩定後再做 | 1d |
| L8 | **K 線圖加入成交量子圖** | 目前 StockChart 只有價格圖；量能確認突破需要 | 0.5d |
| L9 | **`ohlcv.csv` 轉為按股票分檔儲存** | 目前單一大 CSV，股票多時讀取效能下降；分檔可大幅加速 | 1d |
| L10 | **自動排程健康監控** | 已完成：`data-status` 分開回報 healthy / running / failed / overdue / never_run / invalid_timestamp，並以平日規則避免週末誤報 | — |

---

## 4. 下一步最建議先做的 3 件事

### 第 1 件：等待 / 匯入真實基本面資料

```
目前問題：Daily Check 仍提示基本面避雷覆蓋不足。
影響：穩健動能的基本面避雷分數只能維持保守 / 中性，不能假裝完整。
做法：使用外部真實 CSV，走 prepare_fundamentals_priority_import.py template / dry-run / apply，
     再 merge_priority_fundamentals.py 預覽與確認合併，最後 run_signals / daily_check。
```

### 第 2 件：維持兩策略文件與輸出一致

```
目前問題：基本面避雷欄位若措辭不準，容易被誤認成推薦策略。
影響：文件、Dashboard 或 API 說明若措辭不準，會把基本面避雷誤讀成推薦桶。
做法：所有新文件與 UI 只說 `old_wang` / `steady_momentum` 兩策略；
     `fundamental_*` 只能寫成正式基本面輔助欄位，不可寫成第三策略。
```

### 第 3 件：下一個產品 slice 需重新選定

```
目前問題：loop_state 目前沒有 Next Phase Candidates。
影響：心跳不應自行開新大任務，以免偏離使用者真正要的產品方向。
做法：若使用者要繼續自動完善，先從 homepage_pm_roadmap / current_rules 選一個小而安全的 phase。
```

---

## 5. 快速驗收指令

```bash
# 後端測試
cd backend && python3 -m pytest -q

# 後端啟動
cd backend && uvicorn app.main:app --reload --port 9000

# 手動回補（最近 1 個月）
cd backend && python3 scripts/daily_update.py --months 1

# 手動產生訊號
cd backend && python3 scripts/run_signals.py

# 今日規則掃描
cd backend && python3 scripts/today_scan.py

# 每日健康檢查
cd backend && python3 scripts/daily_check.py --write-report

# 基本面避雷補資料流程
cd backend && python3 scripts/prepare_fundamentals_priority_import.py --write-template
cd backend && python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv
cd backend && python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply
cd backend && python3 scripts/merge_priority_fundamentals.py
cd backend && python3 scripts/merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS

# 全量更新（backfill + signals + 寫狀態檔）
cd backend && python3 scripts/daily_update.py --months 1

# 前端啟動
cd frontend && npm run dev

# 前端 build 驗證
cd frontend && npm run build
```

---

## 6. 文件索引

| 文件 | 內容 |
|------|------|
| `docs/signal_rules.md` | 技術分析核心規則、訊號定義、輸出欄位規格 |
| `docs/architecture.md` | 分層架構說明（router / service / storage / model） |
| `docs/api.md` | 所有 API endpoint 規格 |
| `docs/operations.md` | 資料更新、排程設定、stale 機制、錯誤處理 |
| `docs/phases.md` | 開發階段記錄（Phase 1–10）與已知限制歷史 |
| `docs/status_overview.md` | **本文件**：當前狀態快照 + 待辦優先清單 |
| `CLAUDE.md` | AI 協作規範（修改範圍、分層規則、禁止事項） |
