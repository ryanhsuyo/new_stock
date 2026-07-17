# Market parity requirements

## Requirement: shared navigation and identity

- 使用者切到 US 後，共用頁面必須保留 US region，不得意外讀取台股資料。
- 股票身份必須包含 region + code；畫面顯示正確市場、幣別與資料日。

## Requirement: US research

- 每檔美股可從清單進入單股研究頁。
- 研究頁至少呈現 K 線、MA20、MA60、RSI、技術狀態、reasons / risk notes 與資料新鮮度。
- 缺資料時顯示可解釋原因，不得把資料不足標成弱勢。

## Requirement: watchlists

- 自選清單可同時保存 TW 與 US，並能依 region 過濾。
- 新增或移除 US ticker 不影響同代碼的 TW item。

## Requirement: updates

- US 提供與台股一致的一鍵更新、running / success / failed、stale、coverage 與重試提示。
- 更新只寫 `ohlcv_us.csv` 與 US 狀態，不得修改台股 OHLCV。

## Requirement: portfolio records

- US trade 保存 region、USD currency、market 與市場化成本設定。
- TW 與 US 可分開查看損益與統計；未提供匯率時不得直接顯示跨幣別總額。

## Requirement: validation

- 驗收頁可選 TW / US、策略與日期區間。
- US 回放只允許已核准的 US 策略，不得出現 old_wang / steady_momentum。
- 回放必須無未來資料洩漏，並清楚標示紙上回放、費率、滑價與資料偏誤。
