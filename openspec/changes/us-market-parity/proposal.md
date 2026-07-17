# US market parity

## Why

美股目前已有行情、資料狀態、基本技術狀態、觀察訊號與兩套獨立觀察策略，但日常操作仍停留在單一長頁。台股已具備研究、自選、更新、交易、投組、統計與驗收工作流。使用者希望除策略本身外，美股盡量沿用台股操作方式。

## What changes

- 將共用產品能力改為 market-aware：頁面、API 與資料契約明確帶 `region=TW|US`。
- 美股補齊台股已有的單股研究、自選清單、更新狀態、交易紀錄、投組損益、統計與驗收入口。
- 共用 UI 結構與互動語言，避免複製兩套難以同步的頁面。
- 美股策略仍使用 `us_trend_follow` 與 `us_wbottom_target`；不得套用 `old_wang` 或 `steady_momentum`。

## Market-specific differences

- US 使用 USD、US ticker、NYSE/NASDAQ/ETF market metadata、US 交易日與時區。
- US 費率、稅務與交易單位不得沿用台股預設值；未設定時必須誠實標示，不得假造。
- TW 與 US OHLCV、排程狀態、輸出快照保持分離。
- 所有策略觀察仍是研究用途，非自動下單。

## Scope order

1. 單股研究頁 + 美股 deep link + 自選清單整合。
2. 前端一鍵更新 + 更新狀態 / stale / coverage 工作流。
3. market-aware 交易紀錄、持倉、投組與統計。
4. 美股策略驗收（沿用相同驗收 UI，使用美股自己的策略與回放引擎）。

## Out of scope

- 不把台股策略套到美股。
- 不做券商串接、自動下單或即時報價。
- 不新增資料庫或大型框架。
- 不在前端重算指標、策略、費稅或績效。
