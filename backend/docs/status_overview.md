# 系統現況總表 & 待辦優先清單

> 最後更新：2026-06-13
> 狀態快照，建議每次重大里程碑後更新。

---

## 1. 已完成功能總表

### 1.1 資料層

| 功能 | 檔案 | 說明 |
|------|------|------|
| TWSE OHLCV 回補 | `scripts/backfill_ohlcv_twse.py` | 按月份拉取，1.2s 節流，(code,date) 去重 merge |
| 股票代碼清單管理 | `backend/data/leaders.json` | 支援巢狀結構，backfill 自動攤平 |
| 歷史資料儲存 | `backend/data/ohlcv.csv` | 約 474 KB，欄位：date, code, open, high, low, close, volume |
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
| 趨勢線（擺動點） | 同上 | 5 Bar 窗口找擺動高低點，各連最近兩點 |
| W 底辨識 | `pattern_service` | 兩相近擺動低點 + 頸線；forming/confirmed/failed |
| M 頂辨識 | 同上 | 兩相近擺動高點 + 頸線；forming/confirmed/failed |
| 分數計算（附原因） | 同上 | 50 基礎分，各條件加減分，必附 reasons + risk_notes |
| 全量訊號輸出 | `run_daily_signals` | 產出 summary.json + universe_report.csv（含 no_buy_reason） |
| 歷史日期模擬 | `?as_of=YYYY-MM-DD` | signals / analysis 均支援 as_of 參數 |

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
| stale 計算 | 超過 2 天未更新標記 is_stale；前端顯示黃色警示 |
| macOS 排程 | `scripts/setup_schedule.sh` / `remove_schedule.sh`（launchd） |
| cron 範例 | `scripts/cron_example.txt` |

### 1.5 前端層

| 頁面 | 主要功能 |
|------|---------|
| 訊號 Dashboard | 更新狀態 Banner（running/stale/failed）、檔案健康檢查、BUY 推薦卡片 |
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
| `test_update_status.py` | 39 tests：更新狀態讀寫、stale 計算、API schema、409 防重複 |
| `test_signals_api.py` | signals endpoint schema、空資料行為 |
| `test_pattern_service.py` | W 底 / M 頂 forming/confirmed/failed 三狀態 |
| `test_signals_pattern.py` | 型態整合進訊號計算 |
| `test_stock_analysis.py` | 個股分析、支撐壓力線計算 |
| `test_holdings.py` | 持倉計算、未實現損益 |
| `test_portfolio_summary.py` | 投組摘要欄位與計算 |
| `test_watchlists.py` | 自選清單 CRUD + 邊界條件 |
| `test_notify.py` | 通知 stub |
| `test_schedule.py` | 排程機制 |

---

## 2. 已知限制

### 2.1 資料層

| 限制 | 影響 | 說明 |
|------|------|------|
| 僅支援 TWSE 上市股票 | 上櫃股無資料 | TPEX 上櫃 API 另有格式，backfill 自動 SKIP |
| `ohlcv.csv` 無索引 | 持倉多時讀取略慢 | 目前 50 支股票可接受；超過 200 支需優化 |
| 未實現損益用歷史收盤價 | 非即時報價 | 需 WebSocket / 輪詢外部 API 才能做即時報價 |
| JSON 儲存交易紀錄 | 不適合大量資料 | 數千筆以內無問題；更多需遷移至 SQLite |
| `positions.json` 目前未積極維護 | 與 trades.json 功能重疊 | 可考慮移除或改為快取用途 |

### 2.2 訊號層

| 限制 | 影響 | 說明 |
|------|------|------|
| 最少需要 60 根 K 棒 | 新上市股或資料不足時顯示 DATA_MISSING | 合理限制，短期不改 |
| 型態只支援 W 底 / M 頂 | `signal_rules.md` 要求支援頭肩底 | 待實作 |
| 趨勢線只取兩個擺動點 | 複雜型態趨勢線不準確 | 多點趨勢線為未來優化項 |
| 訊號計算為同步 | 60 支股票約 5–10 秒 | 超過 200 支需改異步或快取 |
| `_STOCK_NAMES` 硬編碼 | 新增股票需手動維護名稱對照 | 可改為從 leaders.json 讀取 |

### 2.3 API 層

| 限制 | 影響 | 說明 |
|------|------|------|
| CORS 固定 `localhost:5173` | 無法部署至生產環境 | 需改為環境變數設定 |
| 無認證機制 | 不可公開暴露 | 所有人共用同一份交易資料 |
| `POST /signals/run` 為同步 | 大量股票時 API 等待時間長 | 應改為異步（類似 update-now 模式） |

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
| H1 | **首頁 Today Focus 契約持續完善** | `pm-worklist.today_focus` 已有第一版；後續補更多 fixture 與視覺驗收 | 0.5d |
| H2 | **Dashboard 大檔拆分前的契約整理** | Dashboard 仍過大，後續拆分前先固定後端欄位與 action renderer 契約 | 0.5d |
| H3 | **stale 閾值改為只計算交易日** | 目前 2 日曆天；週末 + 假日後回來 is_stale=True 屬誤報，應跳過非交易日 | 0.5d |

### 🟡 中優先（改善可觀測性與分析品質）

| # | 項目 | 說明 | 估時 |
|---|------|------|------|
| M1 | **候選股表格降低資訊密度** | 長理由折疊，保留主要理由、進出場區間與詳細入口 | 1d |
| M2 | **首頁截圖驗收** | 建立桌面與手機狀態截圖，驗證第一屏不重疊、不過量 | 1d |
| M3 | **universe_report 加入型態欄位** | 目前 CSV 缺 `pattern_type` / `pattern_status` 實際值（可能為空字串）；加入方便批次分析 | 0.5d |
| M4 | **`notify_service` 實作（LINE Notify / Email）** | 目前為 stub；更新成功/失敗時能收到通知可大幅提升運維品質 | 1d |
| M5 | **每支股票計算時間過長時的 timeout 保護** | 若某支股票資料異常導致計算卡死，全量 signals 會掛住 | 0.5d |
| M6 | **`positions.json` 釐清職責或移除** | 目前與 trades.json 功能重疊，造成維護混亂；決定保留（作為快取）或移除 | 0.25d |

### 🟢 低優先（品質改善 / 未來擴充）

| # | 項目 | 說明 | 估時 |
|---|------|------|------|
| L1 | **即時報價整合** | 需對接外部 WebSocket 或輪詢 API；目前用歷史收盤價 | 2–3d |
| L2 | **多點趨勢線** | 目前僅取兩個擺動點；多點回歸趨勢線精度更高 | 1d |
| L3 | **CORS 改為環境變數設定** | 部署至生產環境前必做，但目前本機開發不影響使用 | 0.25d |
| L4 | **React Router + URL 深連結** | 讓特定分析頁面可直接分享 URL | 1d |
| L5 | **SQLite 遷移（交易 / 訊號快取）** | 資料量超過數千筆時 JSON 效能下降 | 2d |
| L6 | **使用者認證（簡單 token）** | 若要部署給多人使用 | 1–2d |
| L7 | **行動版 RWD 優化** | 桌面版已穩定後再做 | 1d |
| L8 | **K 線圖加入成交量子圖** | 目前 StockChart 只有價格圖；量能確認突破需要 | 0.5d |
| L9 | **`ohlcv.csv` 轉為按股票分檔儲存** | 目前單一大 CSV，股票多時讀取效能下降；分檔可大幅加速 | 1d |
| L10 | **自動排程健康監控** | launchd / cron 靜默失敗時不易發現；加入 last_run 超時警告 | 0.5d |

---

## 4. 下一步最建議先做的 3 件事

### 第 1 件：H3 — stale 閾值改計交易日

```
目前問題：週六 / 週日 / 假日後回來，is_stale=True，前端顯示黃色警示，
         但股市本來就沒開盤，這是誤報。
影響：Dashboard 永遠顯示警示，使用者警覺性下降（wolf effect）。
做法：在 _compute_stale() 中，改為計算「距上一個交易日」的天數差；
     可先用簡單規則：跳過週六 / 週日，假日可先忽略。
```

### 第 2 件：HP-009 — 候選股表格降低資訊密度

```
目前問題：候選股列有大量 reasons / risk / no_buy_reason，
         掃描成本高。
影響：使用者難以快速找出今天最需要看的 3 支股票。
做法：長理由預設折疊，只露出主要理由、進場區間、停損與詳細入口。
```

### 第 3 件：HP-013 — 首頁截圖驗收

```
目前問題：首頁已重組為 Decision Console，但還缺桌面與手機截圖驗收。
影響：可能在不同寬度下仍有資訊過量或文字溢出。
做法：建立固定狀態 fixture 或瀏覽器驗收流程，至少覆蓋 ready / blocked / empty。
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
