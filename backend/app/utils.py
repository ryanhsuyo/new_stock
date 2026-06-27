"""app/utils.py — 共用小工具"""

from datetime import date

from app.services.trading_calendar_service import count_missed_trading_days_since


def count_missed_trading_days(data_date: date, *, today: date | None = None) -> int:
    """
    計算 data_date 之後到「昨天」（不含今天）有幾個交易日（週一～週五）未被資料覆蓋。

    回傳 0 表示資料是最新的（沒有錯過任何已結束的交易日）。
    回傳 > 0 表示至少錯過一個完整交易日，資料已 stale。

    設計說明：今日不計入（當天市場可能尚未收盤 / 更新尚未完成）。
    台灣國定假日目前不處理，僅以週末過濾，已可消除大多數誤報。
    """
    return count_missed_trading_days_since(data_date, today=today or date.today())
