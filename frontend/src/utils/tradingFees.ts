import type { TradeRecord, TradingSettings } from '../types'

export const DEFAULT_TRADING_SETTINGS: TradingSettings = {
  brokerage_fee_rate: 0.001425,
  brokerage_discount: 1,
  min_brokerage_fee: 0,
  sell_transaction_tax_rate: 0.003,
}

function brokerageFee(gross: number, settings: TradingSettings) {
  const discountedFee = Math.round(gross * settings.brokerage_fee_rate * settings.brokerage_discount)
  return gross > 0 && settings.min_brokerage_fee > 0
    ? Math.max(discountedFee, Math.round(settings.min_brokerage_fee))
    : discountedFee
}

export function estimateTradeAmounts(
  tradeType: 'buy' | 'sell',
  price: number,
  shares: number,
  settings: TradingSettings,
) {
  const gross = Math.round(price * shares)
  const fee = brokerageFee(gross, settings)
  const tax = tradeType === 'sell' ? Math.round(gross * settings.sell_transaction_tax_rate) : 0
  const net = tradeType === 'buy' ? gross + fee : gross - fee - tax
  return { gross, fee, tax, net }
}

export function tradeRecordAmounts(t: TradeRecord, settings: TradingSettings) {
  const estimated = estimateTradeAmounts(t.trade_type, t.price, t.shares, settings)
  return {
    gross: t.gross_amount ?? estimated.gross,
    fee: t.fee ?? estimated.fee,
    tax: t.tax ?? estimated.tax,
    net: t.net_amount ?? estimated.net,
  }
}
