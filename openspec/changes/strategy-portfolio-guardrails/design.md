# Design

## Frozen evaluation guardrails

- 合併帳戶正常：單檔最高 15%、總曝險最高 60%、每日最多 3 個新倉；警戒：10%／40%／2。
- 老王單策略正常：20%／80%／4；警戒：10%／40%／2。
- 穩健動能單策略維持嚴格設定：正常 15%／60%／3；警戒 10%／40%／2。放寬至 20%／80%／5 的候選設定在長窗口惡化至 +4.12%／MDD 18.51%，已拒絕。
- 防守／極端：停止新倉。
- 盤前證據不足：evaluation-only 回放停止新倉，並留下 `pre_market_unknown` audit；不宣稱市場安全。

策略別設定只調整組合容量，不改候選排序、分數、旗標與出場。設定直接隨每個 mode 的報告輸出，避免前端或讀者誤認所有帳戶限制相同。

## No future leakage

台股成交日 D 只能使用 `date < D` 的美股日 K。不得使用台股 D 日之後才收盤的美股資料。市場筆記不納入歷史回放，避免現行 snapshot 污染歷史。

## Auditability

每個 mode 回傳 `entry_guardrails`、`skipped_entries`、`skipped_entry_count` 與每日 `risk_level`。略過原因區分盤前風險、每日名額、單檔／總曝險與缺資料。
