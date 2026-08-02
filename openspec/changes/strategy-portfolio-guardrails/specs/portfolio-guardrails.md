# Portfolio guardrail requirements

- 回放 MUST 限制單檔、總曝險與每日新倉數量。
- 台股 D 日買進 MUST 只使用日期早於 D 的美股資料。
- defensive/extreme MUST 阻擋新倉；watch MUST 降低曝險。
- unknown MUST 在 evaluation-only 回放 fail closed 並留下原因。
- 被略過的候選 MUST 可稽核，不得無聲消失。
- 風控不得修改原始策略旗標、賣出與減碼訊號。
- 每個回放 mode MUST 回傳自身實際使用的 guardrail profile；不得只回傳一組全域限制。

## 已被取代（2026-08-02）

- 「風控為 evaluation-only、不改 production 推薦旗標」由 `guardrails-to-production` 取代：
  護欄現在同時作用於 production 每日進場清單。
- `unknown` 在 evaluation-only 回放 fail closed 的規則，在 production 改為保守推估等級
  （見 `guardrails-to-production` 的 `portfolio-guardrails` delta）；回放行為不變。
