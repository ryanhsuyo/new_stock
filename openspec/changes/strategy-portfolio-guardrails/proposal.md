# Strategy portfolio guardrails

## Why

近期策略驗收顯示，steady_momentum 可在同一天產生多檔進場，每檔沿用單股建議部位後使帳戶快速接近滿倉。2026-07-08～07-15 的回放在首日同時買進 5 檔，短窗口 return -8.56%、MDD 11.52%。問題首先是組合級曝險與事件風險未受控，不應直接以單次下跌調整選股分數。

## What changes

- 台股策略驗收加入單檔上限、總曝險上限與每日新倉數量上限。
- 使用台股開盤前已完成的美股 SPY／QQQ／TSM 收盤資料作歷史盤前風險閘門。
- 所有被風控略過的進場記錄 code、日期、規則與原因，避免只看到「沒有買」。
- 規則先在 evaluation-only 回放驗證，不直接改 production 推薦桶。
- 合併帳戶與單策略帳戶使用各自凍結的曝險上限，避免以合併模式的限制錯殺單策略；盤前 defensive/extreme/unknown gate 仍一致 fail closed。
- Dashboard 顯示最近一份驗收報告的三模式摘要與目前保存份數，完整交易明細仍連回策略驗收頁。
- 驗收持倉必須沿用進場訊號既有的 `stop_price`；不得只在報告顯示停損、回放卻等待隔日日線 exit。

## Out of scope

- 不改 old_wang / steady_momentum 分數與旗標。
- 不新增策略，不自動交易。
- 不用 2026-07-17 單一事件最佳化參數。
