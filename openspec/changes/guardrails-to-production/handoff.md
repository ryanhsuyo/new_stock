# Handoff — guardrails-to-production

日期：2026-08-02。全部 33 項 tasks 完成，`1072 passed`。未 commit。

## 做了什麼

- 新增 `signal_forward_validation_service`：讀 `out/signal_snapshots/`，以 `generated_at` 次一交易日開盤為進場基準，用訊號自帶的 `daily_invalidation` 出場，輸出 `out/signal_forward_validation.json`。
- 台股與美股每日報告在「今日結論」之前新增「策略當前證據狀態」區塊。
- 護欄從 evaluation-only 接進 production 進場清單；被擋候選進「今日不新增（風控擋下）」並帶原因。
- 台股報告改為三份 per-profile artifact（combined / old_wang / steady_momentum）。
- 盤前風險 `unknown` 改為保守推估等級（`estimate_pre_market_risk`）。
- `signal_snapshot` 補存 `old_wang_market_filter`、`old_wang_market_regime` 與 `pre_market_risk`。
- 排程改為驗證所有 artifact 都在本輪重新產生，否則不寫成功 marker。

## 當下跑過的數字

| 項目 | 結果 |
|---|---|
| 近 30 天（19 個快照日）37 個 BUY 訊號前推 | 平均 -6.35%、勝率 10.8%、已出場 32 筆 |
| 全部 54 筆 | 平均 -6.94%、勝率 11.1% |
| 同期市場中位（07-01→07-31，77 檔） | -14.18%、80.5% 下跌 |
| 同期 0050 | -6.33% |
| 護欄回放 combined 07-01→07-29 | -10.06%、MDD 10.06% |
| 護欄回放 old_wang 同期 | -10.66%、MDD 10.98% |

## 必須知道的反面證據

**護欄留下的訊號比擋下的更差。** 以 combined profile、normal 風險回推 54 筆：

- 護欄留下 33 筆：平均 -8.33%、勝率 9.1%
- 護欄擋下 21 筆：平均 -4.75%、勝率 14.3%

護欄取的是 `daily_priority` / `score` 前 N 名，而這個排序在這份樣本上與後續報酬呈反向。樣本 33/21、差距 3.6pp，統計上不顯著，但足以否定「接上護欄會讓結果變好」。護欄的作用是限制曝險，不是改善選股——這與 design.md 的 Non-Goals 一致。

## 本 change 沒有做的事

- 沒有調整任何策略參數、閾值或評分。
- 沒有新增策略。
- 沒有宣稱績效改善，也沒有宣稱策略無效——樣本期只有 5 週且集中於跌段。
- 沒有改動賣出、減碼與出場警示路徑。
- 沒有動 trades / holdings / cash。
- 沒有讓三份報告的曝險上限互相知情：同時依三份進場，實際曝險可達單一 profile 上限的三倍。系統擋不住，只在報告中揭露。

## 已知限制

- 既有 23 份快照沒有風控欄位，前推驗收對它們的 `risk_source` 全部標 `rebuilt`（37/37）。補存只對新快照生效。
- 降級推估的等級會實際決定擋不擋單。約束是「不得寬鬆於可得資料所支持的等級」，有 16 種組合的不變式測試守著，但推估本身仍是推估。
- 每日 artifact 從 2 份增為 5 份（台股 3 + 稽核 1 + 美股 1）+ 驗收 JSON。Monitor 卡片尚未調整。

## 下一步（未做）

- Monitor / Dashboard 呈現三份報告與證據狀態。
- 美股尚無 signal snapshot，證據狀態永遠是樣本 0；要驗收美股得先開始存快照。
- `openspec validate` 對其餘三個既有 change 仍失敗（扁平 specs 檔名 + 非 delta 格式），本 change 未處理。
