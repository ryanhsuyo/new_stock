# Guardrails to production, and evidence on the front page

## Why

`strategy-portfolio-guardrails` 的組合護欄已全部完成並通過回放驗證，但依該 change 的決定停在 evaluation-only：`tw_portfolio_replay_*.json` 的 limitations 明寫「Portfolio guardrails are evaluation-only and do not change production recommendation flags」。production 的每日報告因此完全不受護欄約束——`_tw_current_rows()` 的進場篩選只看 `daily_action` 與 `internal_signal`，`old_wang_market_filter` 只被拿去印一行字，一列都沒擋掉。

用系統自己留下的 23 天快照前推驗證（以 `generated_at` 次一交易日開盤進場，避免前視偏誤）：54 個 `BUY` 訊號平均 **-6.94%**、勝率 **11.1%**、50/54 觸發系統自訂失效價出場。同期市場中位 -12.09%、0050 -2.42%。護欄回放 2026-07-01→07-29 為 -10.06%、MDD 10.06%。

也就是說：使用者每天看到的報告會列出進場候選，卻沒有任何地方告訴他這些候選近期的實際表現是負的，而一套已經驗證過、會擋掉這些單的護欄就躺在 evaluation-only 裡沒有生效。

## What Changes

- **BREAKING**：組合護欄從 evaluation-only 提升為 production 進場清單的實際擋單條件。`daily_action=enter/probe/watch` 的候選在盤前風險 defensive/extreme、或超過每日新倉與曝險上限時，MUST 不再列入「今日可能進場／觀察」。
- **BREAKING**：台股每日報告由一份改為三份，每個 guardrail profile（combined / old_wang / steady_momentum）各自套用自己的上限並產生獨立 artifact。
- 被護欄擋掉的候選 MUST 移入獨立的「今日不新增（風控擋下）」區塊並保留原因，不得無聲消失；分桶數 MUST 加總回候選總數。
- 盤前風險為 `unknown` 時 MUST 由當下可得資料推出等級而非停在 unknown；推估結果 MUST 標示為降級推估並列出缺少的輸入，且 MUST NOT 比可得資料支持的等級更寬鬆。
- 台股與美股每日報告新增「策略當前證據狀態」區塊，置於今日結論之前，印出近 1 個月訊號前推績效、同期市場中位對照與最近一次護欄回放結果。沒有足夠樣本時 MUST 印出「證據不足」而不是留白。
- 新增訊號前推驗收：讀取 `out/signal_snapshots/`，以 `generated_at` 次一交易日開盤為進場基準計算已實現與未平倉報酬，輸出可稽核 artifact。
- `signal_snapshot` 補存 `old_wang_market_filter`、`old_wang_market_regime` 與盤前風險等級，讓未來的驗收可以重建當日風控狀態。
- 美股報告沿用同一「證據狀態」契約；美股尚無實單與快照，MUST 明示樣本為 0 而非借用台股數字。

## Capabilities

### New Capabilities
- `signal-forward-validation`: 用歷史快照對系統自己發出的訊號做無前視偏誤的前推驗收，並把結果放進每日報告。

### Modified Capabilities
- `portfolio-guardrails`: 護欄從「evaluation-only，不改 production 推薦旗標」改為「production 進場清單的實際擋單條件」，並要求被擋候選在報告中可見。

## Impact

- `backend/scripts/generate_strategy_trade_report.py`：進場篩選改為套用護欄；新增證據狀態與風控擋下區塊；台股輸出改為 per-profile 三份。
- `backend/scripts/scheduled_strategy_report.py`：台股排程需產生三份 artifact，任一份失敗不得讓其餘兩份被視為成功。
- `backend/app/services/signal_snapshot_service.py`：`_compact_signal` 補存風控欄位。
- `backend/app/services/` 新增前推驗收服務；沿用既有 `tw_portfolio_replay` 的盤前風險 helper，不另建平行實作。
- `backend/out/`：新增前推驗收 artifact。
- 既有 `strategy-portfolio-guardrails` 的 evaluation-only 限制條文被本 change 取代。
- 使用者面向影響：每日報告的進場候選數量會下降，且首次出現負面績效陳述。這是預期行為，不是退步。
