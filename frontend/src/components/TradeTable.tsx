import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TradeIntegrityItem, TradeRecord, TradingSettings } from '../types'
import { DEFAULT_TRADING_SETTINGS, tradeRecordAmounts } from '../utils/tradingFees'

interface Props {
  trades: TradeRecord[]
  integrity?: Map<string, TradeIntegrityItem>
  onEdit?: (trade: TradeRecord) => void
}

function fmtMoney(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function TradeTable({ trades, integrity, onEdit }: Props) {
  const [settings, setSettings] = useState<TradingSettings>(DEFAULT_TRADING_SETTINGS)

  useEffect(() => {
    api.getTradingSettings().then(setSettings).catch(() => undefined)
  }, [])

  if (trades.length === 0) {
    return <p className="empty-hint">尚無交易紀錄。</p>
  }

  const sorted = [...trades].sort((a, b) => b.date.localeCompare(a.date))

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>類型</th>
            <th>股票</th>
            <th>價格（元）</th>
            <th>股數</th>
            <th>成交金額</th>
            <th>手續費</th>
            <th>證交稅</th>
            <th>實付 / 實收</th>
            <th>資料檢查</th>
            <th>備註</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(t => {
            const amounts = tradeRecordAmounts(t, settings)
            const check = integrity?.get(t.id)
            return (
              <tr key={t.id}>
                <td>{t.date}</td>
                <td>
                  <span className={`trade-badge ${t.trade_type}`}>
                    {t.trade_type === 'buy' ? '買入' : '賣出'}
                  </span>
                </td>
                <td>
                  <span className="td-name">{t.name}</span>
                  <span className="td-id">{t.stock_id}</span>
                </td>
                <td>{t.price.toFixed(2)}</td>
                <td>{t.shares.toLocaleString()}</td>
                <td>{fmtMoney(amounts.gross)}</td>
                <td>{fmtMoney(amounts.fee)}</td>
                <td>{amounts.tax > 0 ? fmtMoney(amounts.tax) : '—'}</td>
                <td className={t.trade_type === 'buy' ? 'down' : 'up'}>
                  {fmtMoney(amounts.net)}
                </td>
                <td>
                  <span className={`trade-integrity ${check?.status ?? 'unverified'}`}>
                    {check?.status === 'ok' ? '價格範圍正常' : check?.status === 'warning' ? '價格待確認' : '無同日行情'}
                  </span>
                  {check && <small className="trade-integrity-note">{check.reason}</small>}
                  {onEdit && <button className="btn trade-edit-btn" type="button" onClick={() => onEdit(t)}>修正這筆</button>}
                </td>
                <td className="td-note">{t.note || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
