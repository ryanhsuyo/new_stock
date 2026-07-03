# AGENTS.md — 專案協作規範（給 Codex CLI / AI 代理使用）

本專案為「React 18 (TypeScript) + FastAPI」的台灣股票分析與投資紀錄系統。
請嚴格遵守以下規範，避免大改架構、引入不必要複雜度，或產出看似完成但實際不可用的功能。

---

## 0) 專案定位與優先順序

本專案的優先順序如下：

1. 資料流可跑通（backfill -> signals -> API -> 前端呈現）
2. 可觀測性（summary / universe_report 能解釋「為何不買」、「為何不是入場點」）
3. 最小測試（保護最關鍵資料流，不追求全覆蓋）
4. 之後才是：UI 美化、更多策略、更多指標

---

## 1) 可修改範圍（避免亂改）

✅ 允許修改 / 新增：
- `backend/app/**`
- `backend/scripts/**`
- `backend/tests/**`
- `backend/data/**`（僅在需要新增 leaders / positions / 測試資料等檔案時）
- `backend/out/**`（輸出檔案由程式產生，不手動編輯）
- `frontend/**`（僅限使用者或 active phase 明確允許的產品化呈現 / 狀態可讀性改善；不得在前端重算策略、分數、推薦桶或基本面規則）

❌ 不要修改：
- 專案資料夾結構（不要重命名 / 搬移大量檔案）
- 不要把檔案拆太多層造成維護困難

---

## 2) 分層規範（必須遵守）

- `routers/`：只負責 HTTP（路由、參數解析、response_model、錯誤碼）
  - ❌ 不做計算
  - ❌ 不讀寫 CSV / JSON
  - ❌ 不打外部 API
- `services/`：商業邏輯（回補、訊號產生、推薦整理、統計、技術分析）
- `storage/`：資料存取（讀寫 `backend/data/*.csv|json`、`backend/out/*`）
- `models/`：Pydantic models（API 輸入 / 輸出結構）

原則：router 輕、service 厚、storage 專職 I/O。

---

## 3) 路徑與資料位置（避免 data 路徑混亂）

本專案資料檔案一律放在 `backend/data/`：
- `backend/data/leaders.json`：股票代碼清單
- `backend/data/ohlcv.csv`：歷史日 OHLCV（backfill 產生 / 更新）
- `backend/data/positions.json`：持倉與現金
- `backend/data/trades.json`：交易紀錄

策略輸出檔一律放在 `backend/out/`：
- `backend/out/summary.json`
- `backend/out/universe_report.csv`
- `backend/out/daily_brief.json`
- `backend/out/daily_check.json`
- `backend/out/today_scan.json`
- `backend/out/signal_alerts.json`

請在程式中使用「以 backend 為基準」的穩定路徑（建議用 `Path(__file__).resolve()` 推導根目錄），不要依賴使用者在哪個資料夾執行命令。

---

## 4) 外部依賴與框架限制

- ✅ 允許：`requests`, `pandas`, `numpy`, `fastapi`, `pydantic`, `uvicorn`, `pytest`
- ❌ 禁止：引入新的大型框架或資料庫（例如 Celery / Redis / Kafka / ORM / SQLAlchemy / 大型爬蟲框架），除非我明確要求
- 資料儲存先用 CSV / JSON，不上 DB

---

## 5) 變更輸出要求（每次改完都要提供）

每次提交改動，請提供：
1. 修改了哪些檔案（清單）
2. 如何執行（指令）
3. 驗收方式與預期輸出（例如會產生哪些檔案、summary 長什麼樣）
4. 若有風險或未完成項，清楚列出

---

## 6) 重要行為要求（避免「看似完成但其實沒用」）

- 任何批次抓資料（TWSE）必須：
  - 有節流（sleep）
  - 有清楚的 SKIP 清單與原因（印出 stat / message）
  - merge 去重 `(code, date)`，排序後再寫回 CSV
- 任何訊號 / 推薦結果若為空：
  - 必須在 summary 中解釋原因（資料不足 / 趨勢不符 / 無買點 / 型態未完成）
- 不要默默吞錯：
  - 至少要 log 出錯原因與代碼 / 月份 / 步驟
- 不要產出無法解釋的分數：
  - 若有 score，必須同時附帶 reasons / risk_notes

---

## 7) 最小測試策略（不要一開始寫太多）

測試只做最關鍵：
- signals run 能產出 out 檔案與 summary 結構
- recommendations endpoint schema 正確
- universe_report 有 `data_ok` / `no_buy_reason` 欄位
- 型態或訊號邏輯至少有最小固定測資驗證

測試不得依賴真實網路（TWSE），需用固定測資（小 CSV / JSON）跑。

---

## 8) 常用指令（供驗收）

後端啟動：
```bash
cd backend
uvicorn app.main:app --reload
```

執行回補 / 訊號（依現有 script 命名調整）：

```bash
cd backend
python3 scripts/backfill_ohlcv_twse.py          # 回補最近 12 個月
python3 scripts/backfill_ohlcv_twse.py --months 1  # 每日更新（只補最近 1 個月）
python3 scripts/run_signals.py
```

測試：

```bash
cd backend
pytest -q
```

---
 
## 9) 規則文件指引

技術分析、訊號分類、分數規則、API 分析輸出欄位、`summary.json` / `universe_report.csv` 欄位規格，
請遵守 `backend/docs/signal_rules.md`。

每次處理以下工作前，請先閱讀 `backend/docs/current_rules.md`：
- 策略 / 訊號 / 進出場價格
- 候選股篩選報告
- 技術分析頁
- Dashboard 大盤濾網或人工盤後筆記
- `summary.json` / `universe_report.csv` 的交易判斷欄位

`current_rules.md` 是目前實際工作用的快速總表；`signal_rules.md` 是完整規格。若兩者有衝突，先回報並更新文件，再改程式。

---

## 10) 禁止事項

- 不要在 `router` 寫商業邏輯
- 不要直接讀寫 CSV / JSON 於 `router`
- 不要在 `frontend/**` 重算策略、分數、推薦桶、PM priority 或基本面規則；前端只能消費後端 API / out 契約做呈現
- 不要引入資料庫，除非我明確要求
- 不要為了「看起來專業」加入大量難維護指標
- 不要把規則散落在 `script` / `router` / `storage` 多處重複實作
- 不要大幅重構專案目錄
- 不要引入新的大型框架

---

## 11) 實作策略偏好（重要）

優先做：

1. 支撐壓力
2. 長短線趨勢
3. `breakout` / `breakdown`
4. `signal` 分類
5. `summary` / `universe_report` 解釋
6. 再做型態
7. 再做 `score` 細化
8. 最後才考慮前端呈現優化

不要一開始就追求：

- 複雜預測模型
- 多策略拼盤
- 過多指標同時上線
- 華麗 UI

---

## 12) 驗收標準

若功能完成，至少要滿足：

- 可以從固定資料產生 `signals`
- 可以輸出 `summary.json`
- 可以輸出 `universe_report.csv`
- API schema 穩定
- 能看出某檔股票為何進入某個訊號分類
- 若某檔不符合條件，也能清楚解釋原因

若做不到以上，視為尚未完成。
