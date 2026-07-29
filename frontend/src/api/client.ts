import type { BuyRequest, DailyBrief, DailyCheckReport, DataStatus, DecisionJournalBulkCreateResult, DecisionJournalCreate, DecisionJournalEntry, DecisionJournalSummary, FundamentalsPriorityMergeResult, FundamentalsStatus, HoldingAnalysis, IntradayMonitor, ManualWatchlistReview, MarketNoteInput, MarketNoteSaveResult, OfficialFundamentalsCoverageAudit, OfficialFundamentalsReportsResult, OfficialFundamentalsStatus, PmWorklist, PortfolioSummary, Position, PreMarketRiskReport, RecommendationStrategy, SellRequest, SignalAlertReviewStatus, SignalsSummary, SignalsStatus, Stats, StockAnalysis, StockRecommendation, StockTrackingResult, StockUniverseItem, StrategyValidationReport, StrategyValidationRunStatus, TodayScanReport, TradeIntegrityReport, TradeRecord, TradeUpdateRequest, TradingSettings, UniverseReportItem, UniverseReportReviewWorkflow, UpdateWorkflowStatus, UsAnalysisItem, UsDataFreshness, UsMarketStatus, UsStockAnalysis, UsStrategyValidationReport, UsTrendFollow, UsUniverseItem, UsUpdateStatus, UsWatchSignals, UsWbottom, WatchlistGroup, WorkflowStatus } from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = (body as { detail?: unknown }).detail
    const msg =
      typeof detail === 'string' ? detail
      : typeof detail === 'object' && detail !== null
        ? (detail as { message?: string }).message ?? JSON.stringify(detail)
        : `HTTP ${res.status}`
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  getRecommendations: (strategy: RecommendationStrategy = 'steady_momentum') =>
    request<StockRecommendation[]>(`/stocks/recommendations?strategy=${strategy}`),

  getTrades: () =>
    request<TradeRecord[]>('/trades'),

  getTradeIntegrity: () =>
    request<TradeIntegrityReport>('/trades/integrity'),

  updateTrade: (tradeId: string, req: TradeUpdateRequest) =>
    request<TradeRecord>(`/trades/${encodeURIComponent(tradeId)}`, { method: 'PATCH', ...json(req) }),

  buyStock: (req: BuyRequest) =>
    request<TradeRecord>('/trades/buy', { method: 'POST', ...json(req) }),

  sellStock: (req: SellRequest) =>
    request<TradeRecord>('/trades/sell', { method: 'POST', ...json(req) }),

  getPortfolio: () =>
    request<Position[]>('/portfolio'),

  getStats: (period: 'monthly' | 'all') =>
    request<Stats>(`/stats?period=${period}`),

  getSignalsStatus: () =>
    request<SignalsStatus>('/stocks/signals/status'),

  saveMarketNote: (note: MarketNoteInput) =>
    request<MarketNoteSaveResult>('/stocks/market-notes', { method: 'POST', ...json(note) }),

  runSignals: (asOfDate?: string) =>
    request<Record<string, unknown>>('/stocks/signals/run', {
      method: 'POST',
      ...json(asOfDate ? { as_of_date: asOfDate } : {}),
    }),

  getStockAnalysis: (code: string, asOf?: string) =>
    request<StockAnalysis>(`/stocks/${code}/analysis${asOf ? `?as_of=${asOf}` : ''}`),

  addStockToTracking: (code: string, name?: string | null) =>
    request<StockTrackingResult>(`/stocks/${encodeURIComponent(code)}/tracking`, {
      method: 'POST',
      ...json({ name: name ?? null }),
    }),

  getIntradayMonitor: (
    code: string,
    params?: { price?: number; open_price?: number; high?: number; low?: number; volume?: number },
  ) => {
    const qs = new URLSearchParams()
    Object.entries(params ?? {}).forEach(([key, value]) => {
      if (value != null) qs.set(key, String(value))
    })
    return request<IntradayMonitor>(`/stocks/${code}/intraday-monitor${qs.size ? `?${qs}` : ''}`)
  },

  getPortfolioAnalysis: () =>
    request<HoldingAnalysis[]>('/portfolio/analysis'),

  getPortfolioSummary: () =>
    request<PortfolioSummary>('/portfolio/summary'),

  getDataStatus: () =>
    request<DataStatus>('/system/data-status'),

  getPreMarketRiskOrNull: () =>
    request<PreMarketRiskReport>('/system/pre-market-risk').catch(() => null as PreMarketRiskReport | null),

  getFundamentalsStatus: () =>
    request<FundamentalsStatus>('/system/fundamentals-status'),

  getOfficialFundamentalsStatus: () =>
    request<OfficialFundamentalsStatus>('/system/fundamentals-official/status'),

  getOfficialFundamentalsCoverageAuditOrNull: () =>
    request<OfficialFundamentalsCoverageAudit>('/system/fundamentals-official/coverage-audit')
      .catch(() => null as OfficialFundamentalsCoverageAudit | null),

  runOfficialFundamentalsReports: (payload: { apply?: boolean } = { apply: false }) =>
    request<OfficialFundamentalsReportsResult>('/system/fundamentals-official/reports', {
      method: 'POST',
      ...json({ apply: payload.apply ?? false }),
    }),

  mergeFundamentalsPriorityFill: (dryRun = true, confirm?: string | null) =>
    request<FundamentalsPriorityMergeResult>('/system/fundamentals-priority-fill/merge', {
      method: 'POST',
      ...json({ dry_run: dryRun, confirm: confirm ?? null }),
    }),

  getWorkflowStatus: () =>
    request<WorkflowStatus>('/system/workflow-status'),

  getPmWorklist: () =>
    request<PmWorklist>('/system/pm-worklist'),

  getUpdateWorkflow: () =>
    request<UpdateWorkflowStatus>('/system/update-workflow'),

  getDailyCheckOrNull: () =>
    request<DailyCheckReport>('/system/daily-check').catch(() => null as DailyCheckReport | null),

  getTodayScanOrNull: () =>
    request<TodayScanReport>('/system/today-scan').catch(() => null as TodayScanReport | null),

  getDecisionJournal: (
    limit = 20,
    filters?: { date?: string | null; code?: string | null; decision?: string | null },
  ) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (filters?.date) qs.set('date', filters.date)
    if (filters?.code) qs.set('code', filters.code)
    if (filters?.decision) qs.set('decision', filters.decision)
    return request<DecisionJournalEntry[]>(`/decision-journal?${qs}`)
  },

  getDecisionJournalSummary: (date?: string | null) =>
    request<DecisionJournalSummary>(`/decision-journal/summary${date ? `?date=${encodeURIComponent(date)}` : ''}`),

  createDecisionJournalEntry: (entry: DecisionJournalCreate) =>
    request<DecisionJournalEntry>('/decision-journal', { method: 'POST', ...json(entry) }),

  createDecisionJournalFromPortfolioTasks: (date?: string | null) =>
    request<DecisionJournalBulkCreateResult>('/decision-journal/from-portfolio-tasks', {
      method: 'POST',
      ...json({ date: date ?? null }),
    }),

  getUniverseReportReviewWorkflow: (date?: string | null, limit = 10) => {
    const qs = new URLSearchParams({ limit: String(limit) })
    if (date) qs.set('date', date)
    return request<UniverseReportReviewWorkflow>(`/decision-journal/universe-report-workflow?${qs}`)
  },

  createDecisionJournalFromUniverseReport: (date?: string | null, limit = 10) =>
    request<DecisionJournalBulkCreateResult>('/decision-journal/from-universe-report', {
      method: 'POST',
      ...json({ date: date ?? null, limit }),
    }),

  updateDecisionJournalEntry: (id: string, entry: DecisionJournalCreate) =>
    request<DecisionJournalEntry>(`/decision-journal/${encodeURIComponent(id)}`, { method: 'PUT', ...json(entry) }),

  deleteDecisionJournalEntry: (id: string) =>
    request<{ deleted: string }>(`/decision-journal/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  getTradingSettings: () =>
    request<TradingSettings>('/system/settings/trading'),

  getStrategyValidation: () =>
    request<StrategyValidationReport>('/system/strategy-validation'),

  runStrategyValidation: (start: string, end: string) =>
    request<StrategyValidationRunStatus>(`/system/strategy-validation?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`, { method: 'POST' }),

  getStrategyValidationStatus: () =>
    request<StrategyValidationRunStatus>('/system/strategy-validation/status'),

  runUsStrategyValidation: (start: string, end: string) =>
    request<UsStrategyValidationReport>(`/markets/us/strategy-validation?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`, { method: 'POST' }),

  triggerUpdateNow: () =>
    request<{ message: string; status: string }>('/system/update-now', { method: 'POST' }),

  acknowledgeSignalAlerts: (payload: { reviewer?: string; note?: string } = {}) =>
    request<SignalAlertReviewStatus>('/system/signal-alert-reviews/current', {
      method: 'POST',
      ...json({
        reviewer: payload.reviewer ?? 'dashboard',
        note: payload.note ?? null,
      }),
    }),

  // 讀取最近一次訊號 summary；若尚未產生（404）靜默回傳 null
  getSummaryOrNull: () =>
    request<SignalsSummary>('/stocks/signals/summary').catch(() => null as SignalsSummary | null),

  getDailyBriefOrNull: () =>
    request<DailyBrief>('/stocks/signals/daily-brief').catch(() => null as DailyBrief | null),

  getManualWatchlistReviewOrNull: () =>
    request<ManualWatchlistReview>('/stocks/signals/manual-watchlist-review')
      .catch(() => null as ManualWatchlistReview | null),

  // 候選股篩選報告（JSON array）；若尚未產生（404）靜默回傳 null
  getUniverseReportOrNull: () =>
    request<UniverseReportItem[]>('/stocks/signals/universe-report').catch(() => null as UniverseReportItem[] | null),

  // ── Universe ──────────────────────────────────────────────────────────────
  getUniverse: () =>
    request<StockUniverseItem[]>('/stocks/universe'),

  // ── US Market (Phase 1) ───────────────────────────────────────────────────
  getUsUniverse: () =>
    request<UsUniverseItem[]>('/markets/us/universe'),

  getUsMarketStatus: () =>
    request<UsMarketStatus>('/markets/us/status'),

  getUsUpdateStatus: () =>
    request<UsUpdateStatus>('/markets/us/update-status'),

  triggerUsUpdate: (months = 1) =>
    request<UsUpdateStatus>(`/markets/us/update-now?months=${months}`, { method: 'POST' }),

  getUsDataFreshness: () =>
    request<UsDataFreshness>('/markets/us/data-freshness'),

  getUsAnalysis: () =>
    request<UsAnalysisItem[]>('/markets/us/analysis'),

  getUsStockAnalysis: (code: string) =>
    request<UsStockAnalysis>(`/markets/us/analysis/${encodeURIComponent(code)}`),

  getUsSignals: () =>
    request<UsWatchSignals>('/markets/us/signals'),

  getUsTrendFollow: () =>
    request<UsTrendFollow>('/markets/us/strategy/trend-follow'),

  getUsWbottom: () =>
    request<UsWbottom>('/markets/us/strategy/w-bottom'),

  // ── Watchlists ────────────────────────────────────────────────────────────
  getWatchlists: () =>
    request<WatchlistGroup[]>('/watchlists'),

  createWatchlist: (name: string) =>
    request<WatchlistGroup>('/watchlists', { method: 'POST', ...json({ name }) }),

  deleteWatchlist: (group: string) =>
    request<{ deleted: string }>(`/watchlists/${encodeURIComponent(group)}`, { method: 'DELETE' }),

  addToWatchlist: (group: string, code: string, name: string, region: 'TW' | 'US' = 'TW') =>
    request<WatchlistGroup>(`/watchlists/${encodeURIComponent(group)}/stocks`, {
      method: 'POST',
      ...json({ code, name, region }),
    }),

  removeFromWatchlist: (group: string, code: string, region: 'TW' | 'US' = 'TW') =>
    request<WatchlistGroup>(
      `/watchlists/${encodeURIComponent(group)}/stocks/${encodeURIComponent(code)}?region=${region}`,
      { method: 'DELETE' },
    ),
}
