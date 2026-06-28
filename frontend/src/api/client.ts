import type { BuyRequest, DailyBrief, DailyCheckReport, DataStatus, DecisionJournalBulkCreateResult, DecisionJournalCreate, DecisionJournalEntry, DecisionJournalSummary, FundamentalsPriorityMergeResult, FundamentalsStatus, HoldingAnalysis, IntradayMonitor, ManualWatchlistReview, MarketNoteInput, MarketNoteSaveResult, OfficialFundamentalsStatus, PmWorklist, PortfolioSummary, Position, RecommendationStrategy, SellRequest, SignalsSummary, SignalsStatus, Stats, StockAnalysis, StockRecommendation, StockTrackingResult, StockUniverseItem, TradeRecord, TradingSettings, UniverseReportItem, UniverseReportReviewWorkflow, UpdateWorkflowStatus, WatchlistGroup, WorkflowStatus } from '../types'

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

  getFundamentalsStatus: () =>
    request<FundamentalsStatus>('/system/fundamentals-status'),

  getOfficialFundamentalsStatus: () =>
    request<OfficialFundamentalsStatus>('/system/fundamentals-official/status'),

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

  triggerUpdateNow: () =>
    request<{ message: string; status: string }>('/system/update-now', { method: 'POST' }),

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

  // ── Watchlists ────────────────────────────────────────────────────────────
  getWatchlists: () =>
    request<WatchlistGroup[]>('/watchlists'),

  createWatchlist: (name: string) =>
    request<WatchlistGroup>('/watchlists', { method: 'POST', ...json({ name }) }),

  deleteWatchlist: (group: string) =>
    request<{ deleted: string }>(`/watchlists/${encodeURIComponent(group)}`, { method: 'DELETE' }),

  addToWatchlist: (group: string, code: string, name: string) =>
    request<WatchlistGroup>(`/watchlists/${encodeURIComponent(group)}/stocks`, {
      method: 'POST',
      ...json({ code, name }),
    }),

  removeFromWatchlist: (group: string, code: string) =>
    request<WatchlistGroup>(
      `/watchlists/${encodeURIComponent(group)}/stocks/${encodeURIComponent(code)}`,
      { method: 'DELETE' },
    ),
}
