# Project Brief

> 專案的穩定背景說明。這裡寫「不太會變」的東西：專案是什麼、給誰、怎麼架的。
> 易變的進度請寫在 `current-status.md`，未來規劃寫在 `roadmap.md`。

## Project Name

new_stock

## Purpose

台灣股票分析 / 選股 / 訊號 / dashboard 專案。從 TWSE/TPEX 回補行情資料，計算技術訊號與候選股報表，並在前端 dashboard 呈現「今天該做什麼」的決策視角。核心目標是**資料流可跑通**與**可觀測性**（能解釋「為何不買」「為何不是入場點」）。

## Users

Ryan（自用）。用於個人投資研究、策略觀察與投資紀錄；單人本機使用，無多人 / 認證需求。

## Tech Stack

- Language: Python 3（後端；本機以 `python3.11` 安裝依賴）、TypeScript（前端）
- Framework: Backend = FastAPI；Frontend = React 18 + Vite
- Runtime / Platform: uvicorn（後端 ASGI）；Vite dev server（前端）；macOS 本機
- Database: 無。資料以 CSV / JSON 存放於 `backend/data/` 與 `backend/out/`（刻意不上 DB）
- 測試: pytest（後端）；`tsc` 型別檢查（前端 build 內含）
- 其他關鍵工具 / 服務: 資料腳本（daily update / backfill / signals / doctor / daily check / today scan）；lightweight-charts（前端 K 線圖）

### 重要 port

- Backend（FastAPI / uvicorn）: **19000**
  - 注意：本 repo 實際使用 `19000`（README、`scripts/dev-all.mjs`、`frontend/vite.config.ts` 皆為 19000）。
- Frontend（Vite）: **5173**
  - Vite dev server 以 proxy 將 `/api` 轉到 `http://127.0.0.1:19000`（用 127.0.0.1 而非 localhost，避免 Node 走 IPv6 連不到只綁 IPv4 的後端）。

## Core Features

- 股票 universe 管理（`backend/data/leaders.json`，支援巢狀結構）與資料覆蓋狀態
- OHLCV / 指標資料更新（TWSE/TPEX 回補、去重 merge、節流、SKIP 說明）
- Signal 計算與 universe report（7 狀態訊號、支撐壓力、趨勢線、型態、分數 + reasons/risk_notes）
- 兩策略推薦桶：`old_wang`（老王短波段）與 `steady_momentum`（穩健動能）
- Frontend dashboard（Decision Console、PM Worklist、Primary Action、Today Scan、Daily Check）
- 研究頁（AnalysisPage）+ 左側 rail（觀察清單 / 本週推薦 / 候選股，含策略切換與檢視過濾）
- 交易紀錄 / 投組損益 / 統計；決策日誌（復盤）

## Important Files

> 接手的人最該先看的檔案 / 目錄，附一句說明。

- `backend/` — FastAPI 後端；`app/`（config/main/models/routers/services/storage/utils）、`scripts/`、`tests/`、`data/`、`out/`、`docs/`。
- `frontend/` — React 18 + Vite 前端（`src/pages/`、`src/components/`、`src/api/client.ts`、`src/types/`）。
- `backend/scripts/daily_update.py` — 每日更新入口（回補 + 同步輔助資料 + 匯入基本面 + 重算訊號 + 刷新 Daily Check）。
- `backend/scripts/backfill_ohlcv_twse.py` — TWSE/TPEX OHLCV 回補（單獨除錯用）。
- `backend/scripts/run_signals.py` — 產生 signals / summary / universe_report。
- `backend/scripts/update_all_data.py` — daily_update 底層的全量更新流程。
- `backend/scripts/doctor.py` — 健康檢查 / 診斷。
- `backend/scripts/daily_check.py` — 每日 PM 健康檢查（`--write-report` 產生 `out/daily_check.json`）。
- `backend/scripts/today_scan.py` — 今日規則掃描（分桶輸出）。
- `CLAUDE.md` / `AGENTS.md` — AI 協作規範（分層、可修改範圍、禁止事項、兩策略限制）。
- `backend/docs/status_overview.md` — 系統現況總表與待辦優先清單。
- `backend/docs/signal_rules.md` / `backend/docs/api.md` / `backend/docs/architecture.md` — 規則、API、架構規格。

## Architecture Notes

- 分層：`routers/`（只做 HTTP，不計算、不讀寫檔、不打外部 API）→ `services/`（商業邏輯）→ `storage/`（讀寫 `data/*` 與 `out/*`）→ `models/`（Pydantic）。原則：router 輕、service 厚、storage 專職 I/O。
- 資料流：`leaders.json` + `ohlcv.csv` → `signals_service` → `summary.json` / `universe_report.csv` / `daily_brief.json` / `signal_alerts.json`；前端讀 `/api/*` 契約呈現。
- 資料位置：輸入在 `backend/data/`，程式產出在 `backend/out/`（不手動編輯）。
- 前端只**消費**後端 API / out 契約，不重算策略、分數、推薦桶或基本面規則。
- 更新排程：`scripts/daily_update.py` 為日常入口；API 端 `POST /system/update-now` 背景觸發；macOS launchd（`com.stockapp.daily-update`）每日 15:30 跑一次。

## Non-goals

> 明確**不做**的事，避免 scope 蔓延。

- 不直接下單 / 串接券商自動交易。
- 不保證投資報酬。
- 不把 AI 建議當作買賣指令。
- 不自動推送交易決策。
- 不上資料庫、不引入大型框架（Celery / Redis / Kafka / ORM 等）。
- 前端不重算策略 / 分數 / 推薦桶 / 基本面規則。

## Known Constraints

> 技術 / 商業 / 法規 / 環境上的限制。

- 對外只保留兩個推薦策略：`old_wang` 與 `steady_momentum`；`core_technical_v2` 僅為內部訊號引擎，不是推薦桶。
- 不可偽造基本面數字（ROE / FCF / CAGR / interest coverage / dividend years 等）；基本面只作為 `steady_momentum` 的避雷輔助。
- 資料以 CSV / JSON 儲存，數千筆內可用；更大量才需考慮遷移。
- 無認證機制，僅限本機單人使用，不可公開暴露。
- 後端依賴（fastapi / uvicorn / pytest / httpx，另用 pandas / numpy / requests）目前於本機的 `python3.11` 安裝；其他 interpreter 可能沒有依賴。
