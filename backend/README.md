# 台灣股票分析與投資紀錄 — Backend

FastAPI 後端，提供台灣股票訊號分析、交易紀錄與投資組合管理的 REST API。

---

## 環境需求

- Python 3.10+

---

## 安裝

```bash
cd backend
pip install -r requirements.txt
```

---

## 啟動

```bash
cd backend
uvicorn app.main:app --reload --port 19000
```

- API 伺服器：`http://localhost:19000`
- Swagger UI：`http://localhost:19000/docs`

---

## 資料準備（初次使用必做）

### 1. 確認股票清單

`backend/data/leaders.json`：

```json
["2330", "2317", "2454"]
```

### 2. 回補歷史 OHLCV（建議 12 個月）

```bash
python scripts/backfill_ohlcv_twse.py --months 12
```

### 3. 執行訊號計算

```bash
python scripts/run_signals.py
```

---

## 每日更新

```bash
cd backend
python3 scripts/daily_update.py --months 1   # 補最近 1 個月 + 重算訊號 + 更新 Daily Check
```

### 健康檢查

```bash
cd backend
python3 scripts/daily_check.py
python3 scripts/daily_check.py --write-report
python3 scripts/doctor.py
python3 scripts/doctor.py --json
```

`daily_update.py` 是日常主要入口，底層沿用 `update_all_data.py`；`update_all_data.py`、`run_signals.py` 與 API 背景更新完成後會自動刷新 `backend/out/daily_check.json`。`daily_check.py` 可手動顯示資料日、交易輸出是否可用與 Top N 待辦；加 `--write-report` 可單獨重寫 Dashboard 快照。`doctor.py` 會輸出完整檢查明細。exit code：`0=OK`、`1=WARN`、`2=BLOCK`。

API 可讀取最近一次 daily check：

```bash
GET /api/system/daily-check
```

### 基本面避雷補資料

推薦策略固定只有老王 `old_wang` 與穩健動能 `steady_momentum`；基本面避雷只作為穩健動能的資料完整度與避雷輔助，不產生獨立候選股。

```bash
cd backend
python3 scripts/prepare_fundamentals_priority_import.py --write-template
# 依 backend/out/fundamentals_priority_import_template.csv 整理真實外部資料後：
python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv
python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply
python3 scripts/merge_priority_fundamentals.py
python3 scripts/merge_priority_fundamentals.py --apply --confirm MERGE_PRIORITY_FUNDAMENTALS
python3 scripts/run_signals.py
```

### 候選股復盤待辦

```bash
cd backend
python3 scripts/export_universe_review_todo.py
```

輸出 `backend/out/universe_report_review_todo.md`，只作人工復盤草稿，不會自動建立決策日誌或修改交易紀錄。

---

## 執行測試

```bash
cd backend
pytest -q
```

---

## 文件

| 文件 | 說明 |
|------|------|
| `docs/signal_rules.md` | 技術分析規則、訊號定義、輸出欄位規格 |
| `docs/architecture.md` | 分層架構（router / service / storage / model）說明 |
| `docs/api.md` | 所有 API 端點、請求 / 回應格式 |
| `docs/operations.md` | 資料更新、stale 檢查、錯誤排查、排程設定 |
| `docs/phases.md` | Phase 1–10 完成項目與已知限制 |

---

## 資料夾結構

```
backend/
├── app/
│   ├── main.py          # FastAPI 進入點
│   ├── routers/         # HTTP 路由（不做計算）
│   ├── services/        # 商業邏輯
│   ├── storage/         # 資料存取（CSV / JSON）
│   └── models/          # Pydantic 資料模型
├── data/
│   ├── leaders.json     # 追蹤股票代碼清單
│   ├── ohlcv.csv        # 歷史日線（backfill 產生）
│   └── trades.json      # 交易紀錄
├── out/                 # 訊號輸出（run_signals 產生）
├── scripts/
│   ├── backfill_ohlcv_twse.py  # 回補 TWSE 歷史資料
│   ├── run_signals.py          # 訊號計算
│   ├── daily_update.py         # 日常統一更新入口（推薦每日使用）
│   └── update_all_data.py      # 底層相容入口
├── tests/
├── docs/
└── requirements.txt
```
