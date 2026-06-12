# 運維操作手冊

本文件說明如何進行日常資料更新、狀態查看、stale 檢查與錯誤排查。

---

## 目錄

- [每日短版 Runbook](#每日短版-runbook)
- [初始化資料](#初始化資料)
- [每日更新流程](#每日更新流程)
- [檢查資料新鮮度（stale）](#檢查資料新鮮度stale)
- [查看更新狀態](#查看更新狀態)
- [排查更新失敗](#排查更新失敗)
- [自動排程設定](#自動排程設定)
- [常用指令速查](#常用指令速查)

---

## 每日短版 Runbook

日常操作請先看 `backend/docs/daily_runbook.md`。本文件保留較完整的運維、排程與排錯細節。

---

## 初始化資料

適用情境：全新安裝、清空重來、補缺大量歷史資料。

### 步驟 1：確認股票清單

```bash
cat backend/data/leaders.json
```

格式為 JSON 陣列或任意巢狀結構，系統會自動展開所有字串值：

```json
["2330", "2317", "2454"]
```

若清單不存在，先建立：

```bash
echo '["2330", "2317", "2454"]' > backend/data/leaders.json
```

### 步驟 2：建立 12 個月資料與報表

```bash
cd backend
python3 scripts/daily_update.py --months 12
```

- 每日更新入口會回補 OHLCV、更新籌碼、重算訊號並刷新 `daily_check.json`
- 資料寫入 `backend/data/ohlcv.csv`，報表輸出到 `backend/out/`

### 步驟 3：驗收

```bash
# 確認資料筆數
wc -l backend/data/ohlcv.csv

# 確認輸出檔案
ls -la backend/out/

# 查看 summary
cat backend/out/summary.json | python3 -m json.tool
```

---

## 巴菲特基本面資料

巴菲特方案只讀基本面資料，不會用 K 線補假分數。日常做法是先整理 CSV，再轉成系統使用的 JSON。

### 步驟 1：填寫 CSV

```bash
backend/data/fundamentals.csv
```

若 `leaders.json` 新增股票，`daily_update.py` 會自動同步 CSV 骨架；也可以手動執行，既有數值不會被覆蓋：

```bash
cd backend
python3 scripts/sync_fundamentals_template.py
```

必要欄位：

| 欄位 | 說明 |
|------|------|
| `code` | 股票代碼 |
| `roe_5y_avg` | 5 年平均 ROE |
| `operating_margin_5y_avg` | 5 年平均營業利益率 |
| `free_cash_flow_positive_years` | 近 5 年自由現金流為正年數 |
| `operating_cash_flow_to_net_income` | 營業現金流 / 淨利 |
| `debt_to_equity` | 負債權益比 |
| `interest_coverage` | 利息保障倍數 |
| `revenue_growth_5y_cagr` | 營收 5 年 CAGR |
| `eps_growth_5y_cagr` | EPS 5 年 CAGR |
| `pe` | 本益比 |
| `fcf_yield` | 自由現金流殖利率 |
| `dividend_years` | 連續配息年數 |

### 步驟 2：匯入 JSON

```bash
cd backend
python3 scripts/import_fundamentals.py
```

輸出：

```bash
backend/data/fundamentals.json
```

### 步驟 3：檢查覆蓋率

```bash
cd backend
python3 scripts/check_fundamentals.py
python3 scripts/check_fundamentals.py --json
```

確認 `完整可評分` 數量增加後，再執行 `python3 scripts/run_signals.py` 或 `python3 scripts/daily_update.py`。

---

## 每日更新流程

台股收盤後（建議 15:30 以後）執行：

### 標準日常指令（目前推薦）

```bash
cd /Users/ryan/Desktop/code/new_stock/backend
python3 scripts/daily_update.py --months 1
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 9000 --reload
```

前端開發伺服器另開一個 terminal：

```bash
cd /Users/ryan/Desktop/code/new_stock/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

- `daily_update.py --months 1` 是每日主要入口，會補 OHLCV、同步籌碼 / 基本面骨架、匯入基本面、重算訊號、更新 workflow 狀態並刷新 Daily Check。
- `daily_update.py --months 12` 是初次建資料、缺很久資料或大範圍修復的主要入口。
- `backfill_ohlcv_twse.py --months 12` 只在需要單獨除錯 OHLCV 回補時使用。
- `run_signals.py` 只在 OHLCV 已更新、但 `summary.json` / `universe_report.csv` 落後時單獨使用。
- `current_price` / 投組估值使用最新收盤價，不是即時市價；盤中價格只能作監控，不可直接覆蓋正式訊號。

### 方式 A：統一更新入口（推薦）

```bash
cd backend
python3 scripts/daily_update.py                 # 補最近 1 個月（預設）
python3 scripts/daily_update.py --months 1      # 明確指定
```

一次完成：
1. 回補 OHLCV（backfill）
2. 更新輔助籌碼資料
3. 依 `leaders.json` 補齊 `fundamentals.csv` row
4. 將 `backend/data/fundamentals.csv` 匯入 `fundamentals.json`
5. 重算訊號（run_signals）
6. 寫入 `backend/out/update_status.json`（前端 data-status 讀取來源）

`daily_update.py` 是日常操作入口，底層沿用 `update_all_data.py`，因此排程或既有自動化仍可繼續使用 `update_all_data.py`。

### 方式 B：分開執行（僅除錯）

```bash
cd backend
python3 scripts/backfill_ohlcv_twse.py --months 1   # 補資料
python3 scripts/run_signals.py                       # 重算訊號
```

> 日常不要優先使用方式 B；它適合確認 OHLCV 或訊號計算哪一段出錯。正式盤後流程請回到 `python3 scripts/daily_update.py --months 1`。

### 方式 C：透過 API 觸發（適合已開啟 server 時）

```bash
curl -X POST http://localhost:9000/api/stocks/signals/run \
     -H "Content-Type: application/json" -d '{}'
```

> 注意：此方式只重算訊號，不會回補 OHLCV。

---

## 檢查資料新鮮度（stale）

### 方式 1：前端投組總覽頁

開啟瀏覽器 → 切換到「投組總覽」tab → 查看頁面頂部的新鮮度列：

- **綠底**：資料正常（距今 ≤ 3 個交易日）
- **黃底 + ⚠**：資料已過舊（> 3 個交易日）

### 方式 2：API 查詢

```bash
curl http://localhost:9000/api/system/data-status | python3 -m json.tool
```

關鍵欄位：

| 欄位 | 說明 |
|------|------|
| `is_stale` | `true` 表示資料過舊 |
| `stale_days` | 距今天數 |
| `last_data_as_of` | 資料最新日期 |
| `last_run_status` | 最近一次更新狀態 |
| `last_warning_summary` | 更新完成但仍有警告時的摘要，例如資料仍過期 |

### 方式 3：直接查看輸出檔

```bash
# 查看 summary 中的資料日期
python3 -c "import json; d=json.load(open('backend/out/summary.json')); print(d.get('as_of'))"

# 查看 ohlcv.csv 最新日期
tail -5 backend/data/ohlcv.csv
```

---

## 查看更新狀態

### update_status.json

```bash
cat backend/out/update_status.json | python3 -m json.tool
```

```json
{
  "last_run_started_at": "2026-04-11T15:30:00",
  "last_run_finished_at": "2026-04-11T15:35:02",
  "last_run_status": "success",
  "last_error": null,
  "last_error_summary": null,
  "last_warning": null,
  "last_warning_summary": null,
  "last_data_as_of": "2026-04-11",
  "is_stale": false,
  "stale_days": 3
}
```

若 `last_run_status = "stale"`，代表 backfill / signals 流程跑完，但 `last_data_as_of` 仍落後於最新交易日。此時不要把盤後作戰表視為最新決策，需先查看 `backend/out/update.log` 與 backfill 的 `SKIP` / error 訊息，常見原因是網路/DNS 無法連到 TWSE / TPEx。

### update.log（如有設定）

```bash
tail -50 backend/out/update.log
```

log 格式：

```
2026-04-11 15:30:00 [INFO] === update_all_data 開始  months=1 ===
2026-04-11 15:30:01 [INFO] 開始回補 OHLCV，月數=1
2026-04-11 15:34:58 [INFO] 訊號計算完成
2026-04-11 15:35:02 [INFO] ✓ 更新成功  資料最新日=2026-04-11  stale=False(3天)
```

### 監看 running 狀態（更新進行中）

```bash
# 每 3 秒輪詢一次狀態（確認是否還在 running）
watch -n 3 'curl -s http://localhost:9000/api/system/data-status | python3 -m json.tool'
```

或開啟前端「投組總覽」，當 `last_run_status = "running"` 時頁面會自動每 3 秒 poll 並顯示 spinner。

---

## 排查更新失敗

### Step 1：確認失敗類型

```bash
cat backend/out/update_status.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('status:', d['last_run_status']); print('error:', d['last_error'])"
```

### Step 2：查看完整 log

```bash
# 找最近的錯誤
grep -A 5 'ERROR\|Exception\|失敗' backend/out/update.log | tail -30
```

### 常見失敗原因與處理

| 現象 | 可能原因 | 處理方式 |
|------|----------|----------|
| `ConnectionError` / `Timeout` | TWSE API 暫時不通 | 稍後重試；可先只執行 `run_signals.py` |
| `ohlcv.csv not found` | 尚未建立日線與報表 | `python3 scripts/daily_update.py --months 12` |
| `leaders.json not found` | 股票清單檔案不存在 | 建立 `backend/data/leaders.json` |
| `DATA_MISSING` 占多數 | ohlcv 資料太少（< 60 根） | 重新執行 `python3 scripts/daily_update.py --months 12` |
| 巴菲特方案皆為資料不足 | `fundamentals.json` 尚未填入真實基本面欄位 | 補齊 `backend/data/fundamentals.json` 中 ROE、FCF、估值等欄位 |
| `已有另一個 instance 在執行` | 上次更新未完成或殭屍 PID 檔 | 確認沒有其他 Python process 後刪除 `backend/out/update.pid` |
| `update_status.json` 顯示 `running` 但不動 | 更新中途崩潰，PID 檔殘留 | 確認 process 不存在後刪除 PID 檔，再重試 |

### 手動清除殭屍鎖

```bash
# 確認沒有相關 Python process
ps aux | grep 'daily_update\|update_all_data\|backfill_ohlcv'

# 若確認無 process，清除 PID 檔
rm -f backend/out/update.pid
```

### 手動重置 update_status（僅供測試）

```bash
python3 -c "
from pathlib import Path
import json
p = Path('backend/out/update_status.json')
p.write_text(json.dumps({'last_run_status': None, 'last_error': None}, ensure_ascii=False))
"
```

---

## 自動排程設定

### macOS（launchd，推薦）

```bash
cd backend/scripts
./setup_schedule.sh     # 設定每日 15:30 自動更新
./remove_schedule.sh    # 移除排程
```

### macOS / Linux（cron）

```bash
crontab -e
```

貼入（替換路徑）：

```cron
30 15 * * 1-5 cd /ABSOLUTE/PATH/TO/backend && /usr/local/bin/python3 scripts/daily_update.py --months 1
```

- `30 15 * * 1-5`：週一至週五 15:30 執行
- 取得絕對路徑：`which python3` 與 `cd backend && pwd`
- 驗證：`crontab -l`

---

## 常用指令速查

```bash
# === 資料回補 ===
cd backend
python3 scripts/daily_update.py --months 12           # 初次建資料 / 大範圍修復（推薦）
python3 scripts/daily_update.py                       # 每日更新（推薦）
python3 scripts/backfill_ohlcv_twse.py --months 12    # 僅除錯 OHLCV 回補
python3 scripts/update_all_data.py                    # 統一更新底層入口 / 排程相容
python3 scripts/sync_fundamentals_template.py         # 依 leaders 補齊 fundamentals.csv row
python3 scripts/import_fundamentals.py                # 將 fundamentals.csv 匯入 JSON
python3 scripts/check_fundamentals.py                 # 檢查巴菲特基本面資料覆蓋率

# === 訊號計算 ===
python3 scripts/run_signals.py                        # 使用最新資料日
python3 scripts/run_signals.py --as-of 2026-01-01     # 指定基準日（回測）

# === 狀態查看 ===
curl http://localhost:9000/api/system/data-status     # 更新狀態 API
cat backend/out/update_status.json                    # 原始狀態檔
tail -50 backend/out/update.log                       # 更新 log
cat backend/out/summary.json                          # 最新訊號摘要

# === 測試 ===
cd backend && pytest -q                               # 執行所有測試
cd backend && pytest tests/test_signals_api.py -v    # 單一測試檔

# === 伺服器 ===
uvicorn app.main:app --reload --port 9000             # 開發模式
uvicorn app.main:app --host 0.0.0.0 --port 9000       # 指定 host/port
```
