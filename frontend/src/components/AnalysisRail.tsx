import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { DecisionJournalDecision, RecommendationStrategy, StockRecommendation, UniverseReportReviewWorkflow, WatchlistGroup } from '../types'

interface Props {
  /** 目前研究頁載入中的股票代碼，用於高亮 */
  activeCode?: string
  /** 點擊清單股票時的回呼；由 App 走既有跳轉流程（載入 + 更新 hash） */
  onSelect: (code: string) => void
  /** 遞增時觸發 rail 重新抓取（例如頁內加入觀察清單後）；不變則不重抓 */
  refreshKey?: number
}

type RailSource = 'watchlist' | 'recommendations' | 'candidates'
type CandidateItem = UniverseReportReviewWorkflow['top_items'][number]

// 對齊 Dashboard 用詞；rail 內獨立狀態，不與 Dashboard 跨頁耦合
const STRATEGY_OPTIONS: { key: RecommendationStrategy; label: string }[] = [
  { key: 'steady_momentum', label: '穩健動能' },
  { key: 'old_wang',        label: '老王短波段' },
]

// 候選股輕量檢視：只依後端已回傳的 decision_suggestion 欄位分視圖，
// 不重算 signal / score / no_buy_reason / 分桶邏輯。
type CandidateView = 'all' | 'actionable' | 'watch'
const CANDIDATE_VIEWS: { key: CandidateView; label: string }[] = [
  { key: 'all',        label: '全部' },
  { key: 'actionable', label: '可行動' },
  { key: 'watch',      label: '觀望' },
]
// 後端建議 watch / skip 視為「觀望」，其餘視為「可行動」——純視圖分類，非重算
const WAIT_DECISIONS = new Set<DecisionJournalDecision>(['watch', 'skip'])
function matchesCandidateView(item: CandidateItem, view: CandidateView): boolean {
  if (view === 'all') return true
  const waiting = WAIT_DECISIONS.has(item.decision_suggestion)
  return view === 'watch' ? waiting : !waiting
}

// 純呈現排序：只依後端既有的 priority 欄位做數值排序，不重算任何分數 / 分桶
type CandidateSort = 'priority_desc' | 'priority_asc'

/** rail 單列：純作為「進個股」入口，只呈現代碼 / 名稱 / 後端既有標記，不重算任何策略 */
function RailItem({
  code, name, badge, active, onSelect,
}: {
  code: string
  name: string
  badge?: string | number | null
  active: boolean
  onSelect: (code: string) => void
}) {
  return (
    <button
      type="button"
      className={`research-rail-item${active ? ' active' : ''}`}
      onClick={() => onSelect(code)}
      title={`${name}（${code}）`}
    >
      <span className="research-rail-code">{code}</span>
      <span className="research-rail-name">{name}</span>
      {badge != null && badge !== '' && <span className="research-rail-badge">{badge}</span>}
    </button>
  )
}

/**
 * 研究頁左側常駐 rail —— 來源：觀察清單 / 本週推薦 / 候選股（精選可行動）。
 * 純消費後端既有契約，不重算 signal / score / 推薦桶，不把 no_buy_reason / 分桶邏輯搬進前端。
 * 本週推薦支援 steady_momentum / old_wang 子切換，只改 getRecommendations 的 strategy 參數。
 */
export default function AnalysisRail({ activeCode, onSelect, refreshKey }: Props) {
  const [source, setSource] = useState<RailSource>('watchlist')
  const [groups, setGroups] = useState<WatchlistGroup[]>([])
  const [recs, setRecs] = useState<StockRecommendation[]>([])
  const [candidates, setCandidates] = useState<CandidateItem[]>([])
  const [recStrategy, setRecStrategy] = useState<RecommendationStrategy>('steady_momentum')
  const [candidateView, setCandidateView] = useState<CandidateView>('all')
  const [candidateSort, setCandidateSort] = useState<CandidateSort>('priority_desc')
  const [loading, setLoading] = useState(true)
  const [recsLoading, setRecsLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const mountedRef = useRef(true)

  // 每次掛載都重設為 true（StrictMode 會 mount→unmount→remount，不能只在卸載時設 false）
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  // 觀察清單 + 候選股（不含推薦；推薦依 strategy 另外抓）
  const reload = useCallback(async () => {
    setRefreshing(true)
    const [w, c] = await Promise.allSettled([
      api.getWatchlists(),
      api.getUniverseReportReviewWorkflow(null, 12),
    ])
    if (!mountedRef.current) return
    if (w.status === 'fulfilled') setGroups(w.value)
    if (c.status === 'fulfilled') setCandidates(c.value.top_items ?? [])
    setRefreshing(false)
    setLoading(false)
  }, [])

  // 本週推薦：只換 strategy 參數消費後端結果
  const loadRecs = useCallback(async (strategy: RecommendationStrategy) => {
    setRecsLoading(true)
    try {
      const r = await api.getRecommendations(strategy)
      if (mountedRef.current) setRecs(r)
    } catch {
      if (mountedRef.current) setRecs([])
    } finally {
      if (mountedRef.current) setRecsLoading(false)
    }
  }, [])

  // 掛載時抓一次；refreshKey 變動時（例如頁內加入觀察清單成功）重新抓取
  useEffect(() => { reload() }, [reload, refreshKey])
  useEffect(() => { loadRecs(recStrategy) }, [loadRecs, recStrategy])

  // ⟳ 同步重抓三來源（推薦用目前選中的策略）
  const handleRefresh = useCallback(() => {
    reload()
    loadRecs(recStrategy)
  }, [reload, loadRecs, recStrategy])

  const active = activeCode?.trim().toUpperCase()
  const watchlistCount = groups.reduce((n, g) => n + g.stocks.length, 0)
  const visibleCandidates = candidates.filter(c => matchesCandidateView(c, candidateView))
  const sortedCandidates = [...visibleCandidates].sort((a, b) => {
    const pa = a.priority ?? 0
    const pb = b.priority ?? 0
    return candidateSort === 'priority_desc' ? pb - pa : pa - pb
  })

  const tabs: { key: RailSource; label: string; count: number }[] = [
    { key: 'watchlist',       label: '觀察清單', count: watchlistCount },
    { key: 'recommendations', label: '本週推薦', count: recs.length },
    { key: 'candidates',      label: '候選股',   count: candidates.length },
  ]

  return (
    <aside className="research-rail" aria-label="研究清單快速切換">
      <div className="research-rail-bar">
        <span className="research-rail-heading">研究清單</span>
        <button
          type="button"
          className="research-rail-refresh"
          onClick={handleRefresh}
          disabled={refreshing}
          title="重新整理清單（含頁內新增的觀察股）"
          aria-label="重新整理清單"
        >
          {refreshing ? '…' : '⟳'}
        </button>
      </div>

      <div className="research-rail-tabs" role="tablist">
        {tabs.map(t => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={source === t.key}
            className={`research-rail-tab${source === t.key ? ' active' : ''}`}
            onClick={() => setSource(t.key)}
          >
            {t.label}{t.count > 0 ? ` ${t.count}` : ''}
          </button>
        ))}
      </div>

      {source === 'recommendations' ? (
        <>
          <div className="research-rail-chiprow" role="tablist" aria-label="推薦策略">
            {STRATEGY_OPTIONS.map(o => (
              <button
                key={o.key}
                type="button"
                role="tab"
                aria-selected={recStrategy === o.key}
                className={`research-rail-chip${recStrategy === o.key ? ' active' : ''}`}
                onClick={() => setRecStrategy(o.key)}
              >
                {o.label}
              </button>
            ))}
          </div>
          {recsLoading ? (
            <p className="research-rail-empty">載入中…</p>
          ) : recs.length === 0 ? (
            <p className="research-rail-empty">此策略目前無本週推薦，請先在「訊號 Dashboard」產生訊號。</p>
          ) : (
            <ul className="research-rail-list">
              {recs.map(r => (
                <li key={r.stock_id}>
                  <RailItem
                    code={r.stock_id}
                    name={r.name}
                    badge={r.score}
                    active={active === r.stock_id.toUpperCase()}
                    onSelect={onSelect}
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      ) : loading ? (
        <p className="research-rail-empty">載入中…</p>
      ) : source === 'watchlist' ? (
        groups.length === 0 ? (
          <p className="research-rail-empty">尚無觀察清單，請先到「觀察清單」頁建立群組。</p>
        ) : (
          <div className="research-rail-groups">
            {groups.map(g => (
              <div key={g.name} className="research-rail-group">
                <div className="research-rail-group-name">{g.name}</div>
                {g.stocks.length === 0 ? (
                  <div className="research-rail-group-empty">（空）</div>
                ) : (
                  <ul className="research-rail-list">
                    {g.stocks.map(s => (
                      <li key={s.code}>
                        <RailItem
                          code={s.code}
                          name={s.name}
                          active={active === s.code.toUpperCase()}
                          onSelect={onSelect}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        <>
          <div className="research-rail-chiprow" role="tablist" aria-label="候選股檢視">
            {CANDIDATE_VIEWS.map(v => (
              <button
                key={v.key}
                type="button"
                role="tab"
                aria-selected={candidateView === v.key}
                className={`research-rail-chip${candidateView === v.key ? ' active' : ''}`}
                onClick={() => setCandidateView(v.key)}
              >
                {v.label}
              </button>
            ))}
          </div>
          {sortedCandidates.length === 0 ? (
            <p className="research-rail-empty">
              {candidates.length === 0
                ? '目前無可行動候選，請先產生訊號或完成資料更新。'
                : '此檢視目前沒有候選股。'}
            </p>
          ) : (
            <>
              <div className="research-rail-sortrow">
                <button
                  type="button"
                  className="research-rail-sort"
                  onClick={() => setCandidateSort(s => s === 'priority_desc' ? 'priority_asc' : 'priority_desc')}
                  title="依後端 priority 排序（純呈現，不重算）"
                >
                  優先度 {candidateSort === 'priority_desc' ? '高 → 低' : '低 → 高'}
                </button>
              </div>
              <ul className="research-rail-list">
                {sortedCandidates.map(c => (
                  <li key={c.code}>
                    <RailItem
                      code={c.code}
                      name={c.name}
                      badge={c.label}
                      active={active === c.code.toUpperCase()}
                      onSelect={onSelect}
                    />
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </aside>
  )
}
