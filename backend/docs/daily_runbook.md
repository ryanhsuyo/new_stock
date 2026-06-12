# Daily Runbook

本文件是每天操作此專案時的短版流程。若與其他文件不一致，以 `backend/docs/current_rules.md` 與本文件的日常入口為準。

---

## 1. 開發伺服器

後端固定使用 9000 port：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 9000 --reload
```

前端固定使用 5173 port：

```bash
cd /Users/ryan/Desktop/code/new_stock/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## 2. 每日盤後標準流程

台股收盤後，先跑統一更新入口：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/daily_update.py --months 1
```

此流程會完成：

- 回補最近日線資料
- 同步籌碼 / 基本面骨架
- 匯入基本面 CSV
- 重算正式訊號
- 更新 `backend/out/update_status.json`
- 更新 `backend/out/summary.json`
- 更新 `backend/out/universe_report.csv`
- 更新 `backend/out/daily_brief.json`
- 刷新 `backend/out/daily_check.json`

完成後打開 Dashboard，先看：

- `Status Strip`：確認資料日、交易輸出是否可用，以及價格口徑是否為最新收盤價。
- `Primary Action`：先處理第一屏唯一最優先待辦。
- `Market Posture`：確認大盤姿態、人工盤後筆記日期與持股水位語氣。
- `Today Focus`：先看持股風險，再看候選股，最後看復盤 / 維護待辦。
- `PM Worklist` 明細：需要更多原因、指令或預期輸出時再往下看。
- `PM Daily Check` / `Update Workflow` / 檔案狀態：用於確認資料閉環與排查阻塞。

如果 `Status Strip` 或 `Primary Action` 顯示紅色阻塞，先不要把候選股當作今天的進場依據；等阻塞解除並刷新 Dashboard 後，再看候選股、持股與單檔技術分析。

---

## 2.1 價格與持倉口徑

- Dashboard、候選股、技術分析與投組估值預設使用 `backend/data/ohlcv.csv` 的最新收盤價，不是盤中即時市價。
- 盤中看到價格不同時，先確認資料日與 `summary.json.as_of`，不要直接把畫面收盤價當成即時報價。
- 真實買賣請記在 `backend/data/trades.json` 或透過前端交易紀錄功能新增；持股均價與部位會由交易紀錄推算。
- `backend/data/positions.json` 只保留為舊格式備援或狀態檢查，不建議手動維護。
- 買進均價會納入買進手續費；投組、候選股與持股分析需使用一致口徑。

---

## 3. 初次建資料或大範圍修復

如果新增大量股票、清空資料、或 Dashboard 顯示很多 `DATA_MISSING`：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/daily_update.py --months 12
```

不要優先手動跑 `backfill_ohlcv_twse.py`。該腳本只在單獨除錯 OHLCV 回補時使用，因為它不代表完整交易輸出都已刷新。

---

## 4. 看到紅色阻塞時

依 Dashboard 顯示的可複製指令處理，優先順序如下：

1. `Update Workflow` 的 next action
2. `PM Worklist` 第一筆
3. `PM Daily Check` 的 Top action

常見阻塞：

| 狀態 | 指令 | 跑完檢查 |
|------|------|----------|
| 日線資料過期 | `python3 scripts/daily_update.py --months 1` | `ohlcv.csv`、`summary.json`、`universe_report.csv`、`daily_brief.json`、`daily_check.json` |
| 大範圍缺資料 | `python3 scripts/daily_update.py --months 12` | 同上 |
| 原始日線已更新但報表落後 | `python3 scripts/run_signals.py` | `summary.json`、`universe_report.csv`、`daily_brief.json`、`daily_check.json` |
| Daily Check 快照過期 | `python3 scripts/daily_check.py --write-report` | `daily_check.json` |

---

## 5. 終端健康檢查

需要在終端確認狀態時：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/doctor.py
python3 scripts/daily_check.py --write-report
```

Exit code：

- `0`：正常
- `1`：有警告，可回顧但需補資料或復盤
- `2`：阻塞，不能把交易輸出當成今天依據

---

## 6. 巴菲特基本面補資料

Dashboard 若顯示 Buffett 基本面不足：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/check_fundamentals.py --write-priority-csv --write-report
```

填完 `backend/out/fundamentals_priority_fill.csv` 後：

```bash
python3 scripts/merge_priority_fundamentals.py
python3 scripts/merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS
python3 scripts/run_signals.py
python3 scripts/daily_check.py --write-report
```

---

## 7. 候選股復盤

若 PM Worklist 或候選股報告提示待補復盤：

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/export_universe_review_todo.py
```

此指令只產生 `backend/out/universe_report_review_todo.md` 草稿，不會修改交易紀錄、持倉或現金。

正式復盤仍應透過 Dashboard / Universe Report 的決策日誌功能處理。
