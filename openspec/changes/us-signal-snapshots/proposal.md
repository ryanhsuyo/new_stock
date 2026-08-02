# US signal snapshots

## Why

`guardrails-to-production` 讓台股每日報告能印出「近 30 天 37 個訊號、平均 -6.35%」這種當前證據狀態，因為台股從 2026-01 起就在 `out/signal_snapshots/` 留下每日快照。美股一份都沒有，所以美股報告的證據狀態永遠是「可驗收樣本 0 筆」——不是因為策略沒訊號，是因為訊號發生過就消失了。

美股是觀察模組，能產出的最高等級只有「可紙上追蹤」。這種訊號的唯一用途就是事後驗證，而事後驗證需要當時的紀錄。現在每天產生的分桶結果在報告寫完之後就不存在了，隔天重跑只會得到當天的狀態。

## What Changes

- 每日產生美股報告時同步寫出 `out/us_signal_snapshots/us_signal_snapshot_<as_of>.json`，保存當日全部追蹤標的的分桶、動作、關鍵價位與兩個大盤濾網狀態。
- 前推驗收支援美股：只有「可紙上追蹤」桶計入績效，其餘桶只保存不計分。
- 美股報告的證據狀態改用實際快照計算；累積前仍明示樣本數。
- 快照保存 `generated_at`，前推驗收沿用「產出日次一交易日開盤」的進場基準。

## Capabilities

### New Capabilities
- `us-signal-snapshots`: 每日保存美股觀察訊號的分桶與價位，使美股訊號可被事後驗收。

### Modified Capabilities
- `signal-forward-validation`: 前推驗收從只支援台股擴充為市場感知，並定義美股哪一桶才計分。

## Impact

- `backend/scripts/generate_strategy_trade_report.py`：產生美股報告時寫出快照。
- `backend/app/services/`：新增美股快照服務；前推驗收加入市場參數。
- `backend/out/us_signal_snapshots/`：新增每日 artifact。
- `backend/scripts/scheduled_strategy_report.py`：美股 artifact 清單加入快照。
- 使用者面向影響：美股證據狀態要累積數月才有意義；在那之前它會持續顯示樣本不足，這是預期行為。
