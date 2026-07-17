# Design

## Shared shell, market-aware services

前端沿用既有 market toggle，將可共用頁面接收 `region`，由 API 回傳市場化資料。後端維持 router 輕、service 厚、storage 專職 I/O；共用 service 只處理共通流程，市場規則交由 TW / US adapter。

## Required seams

- Price data: `ohlcv.csv` 與 `ohlcv_us.csv` 分離，由 region 選擇 storage。
- Analysis: 共用研究頁契約，但由 TW analysis 與 US analysis adapter 提供欄位；缺少的 US 欄位回 null 並說明，不偽造。
- Watchlists: item 必須保存 region；同 ticker/code 僅在相同 region 內判定重複。
- Trades: 每筆保存 region、currency、market；估值與統計不得跨幣別直接相加。
- Settings: 費率與稅率依 region 取得；US 未確認的成本不得套用 TW 0.1425% / 0.3%。
- Replay: 共用驗收 response shape 與 UI，回放引擎依 region / strategy 選擇。

## Migration

既有未帶 region 的 watchlist / trade 資料視為 `TW`，保持相容。任何持久化 migration 必須先 preview、備份並有測試；本 change 不允許直接破壞性覆寫個人資料。

## Delivery strategy

每個 phase 必須可獨立驗收並保持台股 baseline。上一 phase 未通過完整測試與 frontend build 前，不進下一 phase。
