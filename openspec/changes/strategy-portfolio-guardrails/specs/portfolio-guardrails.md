# Portfolio guardrail requirements

- 回放 MUST 限制單檔、總曝險與每日新倉數量。
- 台股 D 日買進 MUST 只使用日期早於 D 的美股資料。
- defensive/extreme MUST 阻擋新倉；watch MUST 降低曝險。
- unknown MUST 在 evaluation-only 回放 fail closed 並留下原因。
- 被略過的候選 MUST 可稽核，不得無聲消失。
- 風控不得修改原始策略旗標、賣出與減碼訊號。
- 每個回放 mode MUST 回傳自身實際使用的 guardrail profile；不得只回傳一組全域限制。
