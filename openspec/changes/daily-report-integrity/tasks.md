# Tasks

- [x] 拆分 TW daily / audit builders 與兩個 artifacts。
- [x] TW daily 對資料異常只顯示摘要並將績效標示暫估。
- [x] 新增安全的單筆交易修正 API、storage 與固定測試。
- [x] 交易紀錄頁提供待確認提示與單筆修正操作。
- [x] 美股主要決策清單與 W 底詳表去除重複。
- [x] 新增 fixed-as-of 未來資料隔離測試。
- [x] 產生真實 artifacts，跑 backend / frontend / Monitor 驗收。
- [x] 更新 current status、validation 與 handoff。
- [x] Daily Check 寫入後刷新 Today Scan usage status，補完整流程回歸。
- [x] 台股混合資料日改為阻擋 Today Scan／日報決策清單，報告排程改為 15:40。
- [x] 交易完整性文案改為「價格範圍正常／待確認」。
- [x] Dashboard 策略驗收摘要顯示產生日期與歷史區間提示。
- [x] 重產 artifact 並跑 backend / frontend / Monitor 驗收。
- [x] 大盤濾網封鎖時，Today Scan 明示只供觀察與風險處理，不把老王觀察桶誤讀為今日進場。
- [x] 台股日報將 `block`、`exit_warning` 等內部代碼翻譯為讀者文案。
- [x] 盤前風險零分狀態改為「未觸發額外防守」，避免把有限資料誤述為市場正常或安全。
