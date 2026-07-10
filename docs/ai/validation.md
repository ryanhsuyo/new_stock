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
| 美股回補（免 key） | `cd backend && python3 scripts/backfill_ohlcv_us.py [--months N]` |

### 美股（US Market）驗收 —— 分兩層

- **資料源方向**：主源 = **Yahoo Finance chart endpoint（免 API key、非官方、best-effort）**；**Stooq 已停用**（需瀏覽器 JS 驗證）；Finnhub = future optional（`FINNHUB_API_KEY`，不進 git）。

**A. AI 可自行驗收（不需真實對外網路）：**
- `python3.11 -m pytest -q` 全綠：`test_us_market.py`（Yahoo JSON 解析 / null 跳過 / error、Stooq 已停用、Finnhub 缺 key）、`test_us_analysis.py`（指標數學、四種狀態分類、**fixture `ohlcv_us.csv` 端到端**、`/markets/us/analysis` schema）。
- `npm run build` 成功。
- API 在**無資料**時：`/markets/us/analysis` 回 `weak_or_no_data` + 指標 null；用 **fixture** 時算出 MA/RSI/漲跌幅並歸類狀態。
- 前端：缺資料誠實顯示；有資料顯示指標 + 狀態 badge。**驗收用 fixture 後務必刪除 `backend/data/ohlcv_us.csv`（gitignored），以免污染真實回補。**

**B. 需使用者本機（真實 Yahoo）後續驗收：**
- `cd backend && python3 scripts/backfill_ohlcv_us.py --months 12`（**免 key**）；需**正常對外網路**（自簽憑證代理環境會 `CERTIFICATE_VERIFY_FAILED`，backfill 會優雅 skip）。
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
