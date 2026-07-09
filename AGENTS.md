# AGENTS.md

這是所有 AI agent 進入本 repo 的**入口規則**。任何 AI 在對本 repo 做任何事之前，必須先讀完本檔並遵守。

## 1. 進場先讀（必讀，依序）

進入 repo 後，先閱讀以下文件以取得完整脈絡：

1. `docs/ai/project-brief.md` — 專案是什麼、給誰用、技術棧、重要檔案。
2. `docs/ai/current-status.md` — 目前階段、已完成、進行中、風險、不要重做的事。
3. `docs/ai/roadmap.md` — 規劃方向與各 phase 的驗收標準。
4. `docs/ai/validation.md` — 這個專案怎麼驗收。
5. `docs/ai/handoff-log.md` — 最近幾次交接紀錄，理解前人做到哪。

> 本專案另有**具約束力的詳細協作規範**：repo root 的 `CLAUDE.md`（分層規範、可修改範圍、禁止事項、兩策略限制等）與 `backend/docs/status_overview.md`（系統現況總表）。上述 `docs/ai/*` 是統一 handoff 入口與摘要；遇到細節衝突時，以 `CLAUDE.md` 為準。
>
> 若上述任一檔案不存在，先回報，不要自行臆測專案狀態。

## 2. 開始前

- 先執行 `git status --short`，確認 working tree 狀態，並在回報中呈現。
- 若 working tree 不乾淨（有未預期的未提交改動），先回報再動作，不要覆蓋別人的工作。

## 3. Scope 規則

- **只做本次 task 的 scope**。不要順手改無關的檔案、不要做未被要求的重構。
- 有想做但超出 scope 的事，寫進交接紀錄的 `Next Steps`，不要直接做。

## 4. 硬性禁止（未經明確確認前，一律不可）

- **禁止 `git push`**（任何情況都不 push）。
- **禁止 `git reset --hard`**。
- **禁止 `git clean -fd`**。
- **禁止刪除資料 / drop table / 清空資料**（含破壞性覆寫 `backend/data/*`、`backend/out/*`）。
- **禁止輸出、印出或提交任何 secrets**（API key、token、`.env` 內容、憑證等）。

以上動作即使技術上可行，也必須先向使用者確認並取得明確同意。

## 5. 依賴與設定

- **不要改 `package.json` / lockfile**（本專案為 `frontend/package-lock.json`）或 `backend/requirements.txt`，除非任務**明確要求**。
- 不要新增非必要的依賴或工具（見 `CLAUDE.md`：禁止引入大型框架或資料庫）。

## 6. 指令執行方式（避免被截斷）

- **長指令不要直接塞進 shell 或 python heredoc 執行**。多行 / 複雜指令容易在 shell 中被錯誤截斷或跳脫。
- 正確做法：先把腳本或內容**寫到檔案**，再用 `node <file>`、`sh <file>` 或對應 exec 執行。
- 這樣可確保指令完整、可重跑、可檢查。

## 7. 完成後（必做）

1. **依 `docs/ai/validation.md` 驗收**本次改動，並記錄結果。
2. **更新 `docs/ai/handoff-log.md`**（最新紀錄放最上面），寫可接手摘要，不要貼完整聊天紀錄。
3. 若**狀態改變**，更新 `docs/ai/current-status.md`。
4. 若**規劃改變**，更新 `docs/ai/roadmap.md`。
5. 再次執行 `git status --short`。

## 8. 回報格式（每次任務結束必須包含）

- **修改檔案** — 列出所有 changed files。
- **完成內容** — 本次實際做了什麼。
- **驗收結果** — 依 `validation.md` 跑了什麼、結果如何；未跑的也要說明。
- **git status** — `git status --short` 的輸出。
- **commit hash** — 若有 commit，附上 hash；沒有就說明原因。
- **下一步建議** — 建議的 next task / 待辦。
