import { useEffect, useRef, useState } from 'react'
import AnalysisRail from './components/AnalysisRail'
import AnalysisPage from './pages/AnalysisPage'
import UsMarketPage from './pages/UsMarketPage'
import UsResearchPage from './pages/UsResearchPage'
import Dashboard from './pages/Dashboard'
import PortfolioOverviewPage from './pages/PortfolioOverviewPage'
import PortfolioPage from './pages/PortfolioPage'
import StatsPage from './pages/StatsPage'
import StrategyValidationPage from './pages/StrategyValidationPage'
import StocksPage from './pages/StocksPage'
import TradesPage from './pages/TradesPage'
import UniverseReportPage from './pages/UniverseReportPage'
import WatchlistsPage from './pages/WatchlistsPage'

type Tab = 'dashboard' | 'stocks' | 'universe-report' | 'strategy-validation' | 'analysis' | 'watchlists' | 'overview' | 'portfolio' | 'trades' | 'stats'
type UniverseJournalFilter = 'all' | 'unrecorded' | 'recorded'

// 導覽分組：把平列 tab 收斂成有層級的 4 組（今日 / 研究 / 投組 / 系統）
// 只調整呈現層級，不改各頁元件與跳轉邏輯。
const TAB_GROUPS: { group: string; tabs: { id: Tab; label: string }[] }[] = [
  { group: '今日', tabs: [
    { id: 'dashboard', label: '訊號 Dashboard' },
  ] },
  { group: '研究', tabs: [
    { id: 'stocks',     label: '本週推薦' },
    { id: 'analysis',   label: '技術分析' },
    { id: 'watchlists', label: '觀察清單' },
  ] },
  { group: '投組', tabs: [
    { id: 'overview',  label: '投組總覽' },
    { id: 'portfolio', label: '持倉損益' },
    { id: 'trades',    label: '交易紀錄' },
    { id: 'stats',     label: '統計' },
  ] },
  { group: '系統', tabs: [
    { id: 'universe-report', label: '候選股篩選報告' },
    { id: 'strategy-validation', label: '策略驗收' },
  ] },
]

// ── 最小 hash 路由（不引入 React Router）───────────────────────────────
// 只同步「哪一個 tab」與「技術分析的股票代碼」，不同步頁面內部狀態。
const TAB_TO_PATH: Record<Tab, string> = {
  dashboard:         '/today',
  analysis:          '/research',
  overview:          '/portfolio',
  'universe-report': '/system',
  'strategy-validation': '/validation',
  stocks:            '/picks',
  watchlists:        '/watchlists',
  portfolio:         '/holdings',
  trades:            '/trades',
  stats:             '/stats',
}

const PATH_TO_TAB: Record<string, Tab> = {
  today:      'dashboard',
  research:   'analysis',
  portfolio:  'overview',
  system:     'universe-report',
  validation: 'strategy-validation',
  picks:      'stocks',
  watchlists: 'watchlists',
  holdings:   'portfolio',
  trades:     'trades',
  stats:      'stats',
}

function pathForState(tab: Tab, analysisCode?: string): string {
  if (tab === 'analysis' && analysisCode) return `/research/${encodeURIComponent(analysisCode)}`
  return TAB_TO_PATH[tab]
}

// 美股頁 deep link：#/us 為正準；#/markets/us 為別名（兩者都保留，不互相改寫）
const US_HASH_PATHS = new Set(['us', 'markets/us'])

function isUsHash(hash: string): boolean {
  return US_HASH_PATHS.has(hash.replace(/^#/, '').replace(/^\/+/, ''))
}

function parseHash(hash: string): { region: 'TW' | 'US'; tab: Tab; code?: string } {
  const raw = hash.replace(/^#/, '').replace(/^\/+/, '')
  // #/us 或 #/markets/us → 美股頁（美股頁內部無 tab，tab 僅回台股時使用）
  if (US_HASH_PATHS.has(raw)) return { region: 'US', tab: 'dashboard' }
  const [head, second] = raw.split('/')
  // #/research/2330 → 技術分析深連結
  if (head === 'research' && second) return { region: 'TW', tab: 'analysis', code: decodeURIComponent(second) }
  const tab = PATH_TO_TAB[head]
  return tab ? { region: 'TW', tab } : { region: 'TW', tab: 'dashboard' }
}

export default function App() {
  // 由網址 hash 初始化，避免掛載時 state 與 hash 不一致而覆蓋 deep link（StrictMode 下尤其明顯）
  const [tab, setTab] = useState<Tab>(() => parseHash(window.location.hash).tab)
  // 從投組頁點擊跳轉時帶入的股票代碼，undefined 表示手動進入
  const [analysisCode, setAnalysisCode] = useState<string | undefined>(() => parseHash(window.location.hash).code)
  const [analysisRequestId, setAnalysisRequestId] = useState(0)
  const [universeJournalFilter, setUniverseJournalFilter] = useState<UniverseJournalFilter>('all')
  // 遞增以通知左 rail 重新抓取（例如在研究頁成功加入觀察清單後）
  const [railRefreshKey, setRailRefreshKey] = useState(0)
  // 市場切換（TW / US）：與 tab 一樣由 hash lazy-init，支援 #/us deep link 重整還原
  const [region, setRegion] = useState<'TW' | 'US'>(() => parseHash(window.location.hash).region)
  const [usView, setUsView] = useState<'market' | 'research' | 'watchlists' | 'validation'>('market')
  const [usResearchCode, setUsResearchCode] = useState<string | undefined>()

  // 用 ref 讀取最新值，避免 hashchange handler 抓到過時 closure
  const tabRef = useRef(tab)
  tabRef.current = tab
  const codeRef = useRef(analysisCode)
  codeRef.current = analysisCode
  const regionRef = useRef(region)
  regionRef.current = region

  // 網址 hash → state：支援重整還原、deep link 與瀏覽器上一頁 / 下一頁
  useEffect(() => {
    const applyHash = () => {
      const { region: hr, tab: ht, code } = parseHash(window.location.hash)
      if (regionRef.current !== hr) setRegion(hr)
      if (hr === 'US') return // 美股頁無內部 tab，不動台股 tab 狀態
      if (tabRef.current !== ht) setTab(ht)
      if (ht === 'analysis' && codeRef.current !== code) {
        setAnalysisCode(code)
        setAnalysisRequestId(id => id + 1)
      }
    }
    // 首次載入：空 hash 用 replace 補上，不新增歷史；有 hash 則還原
    if (!window.location.hash) {
      window.history.replaceState(null, '', `#${pathForState(tabRef.current)}`)
    } else {
      applyHash()
    }
    window.addEventListener('hashchange', applyHash)
    return () => window.removeEventListener('hashchange', applyHash)
  }, [])

  // state → 網址 hash：region / tab / analysisCode 變動時反映到網址（產生歷史紀錄）
  // 掛載時 state 已由 lazy initializer 對齊 hash，故此處會是 no-op，不會覆蓋 deep link。
  useEffect(() => {
    if (region === 'US') {
      // #/markets/us 為合法別名：已在美股 hash 上就不改寫，避免多餘歷史紀錄
      if (!isUsHash(window.location.hash)) window.location.hash = '/us'
      return
    }
    const desired = pathForState(tab, analysisCode)
    if (window.location.hash.replace(/^#/, '') !== desired) {
      window.location.hash = desired
    }
  }, [region, tab, analysisCode])

  function handleTabClick(t: Tab) {
    // 手動點選「技術分析」tab 時清除自動跳轉代碼
    if (t === 'analysis') {
      setAnalysisCode(undefined)
      setAnalysisRequestId(id => id + 1)
    }
    if (t === 'universe-report') {
      setUniverseJournalFilter('all')
    }
    setTab(t)
  }

  function navigateToAnalysis(code: string) {
    setAnalysisCode(code.trim())
    setAnalysisRequestId(id => id + 1)
    setTab('analysis')
  }

  // 研究頁內部搜尋切股 → 同步 App 狀態（左 rail 高亮 + hash）；
  // 刻意不 bump requestId，避免重載已在畫面上的分析內容。
  function handleAnalysisCodeSync(code: string) {
    setAnalysisCode(code)
  }

  function navigateToUniverseReport(journalFilter: UniverseJournalFilter = 'all') {
    setUniverseJournalFilter(journalFilter)
    setTab('universe-report')
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">台灣股票分析與投資紀錄</h1>
        {/* 市場切換：US Phase 1 只做清單/基本行情，缺 key/無資料時 US 頁會誠實顯示 */}
        <div className="market-switch" role="tablist" aria-label="市場切換">
          <button
            type="button"
            role="tab"
            aria-selected={region === 'TW'}
            className={`market-switch-btn${region === 'TW' ? ' active' : ''}`}
            onClick={() => setRegion('TW')}
          >
            台股
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={region === 'US'}
            className={`market-switch-btn${region === 'US' ? ' active' : ''}`}
            onClick={() => setRegion('US')}
            title="美股（Phase 1：清單 / 基本行情）"
          >
            美股
          </button>
        </div>
      </header>

      {region === 'US' ? (
        <>
          <nav className="tab-nav us-tab-nav" aria-label="美股功能導覽">
            <div className="tab-group"><span className="tab-group-label">研究</span><div className="tab-group-btns">
              <button type="button" className={usView === 'market' ? 'active' : ''} onClick={() => setUsView('market')}>市場總覽</button>
              <button type="button" className={usView === 'research' ? 'active' : ''} onClick={() => setUsView('research')}>技術分析</button>
              <button type="button" className={usView === 'watchlists' ? 'active' : ''} onClick={() => setUsView('watchlists')}>觀察清單</button>
            </div></div>
            <div className="tab-group"><span className="tab-group-label">系統</span><div className="tab-group-btns">
              <button type="button" className={usView === 'validation' ? 'active' : ''} onClick={() => setUsView('validation')}>策略驗收</button>
            </div></div>
          </nav>
          {usView === 'market' && <UsMarketPage onNavigateResearch={code => { setUsResearchCode(code); setUsView('research') }} />}
          {usView === 'research' && <UsResearchPage initialCode={usResearchCode} />}
          {usView === 'watchlists' && <main className="app-main"><WatchlistsPage regionFilter="US" onNavigateAnalysis={code => { setUsResearchCode(code); setUsView('research') }} /></main>}
          {usView === 'validation' && <main className="app-main app-main-wide"><StrategyValidationPage initialRegion="US" onNavigateAnalysis={navigateToAnalysis} /></main>}
        </>
      ) : (
      <>
      <nav className="tab-nav">
        {TAB_GROUPS.map(g => (
          <div className="tab-group" key={g.group}>
            <span className="tab-group-label">{g.group}</span>
            <div className="tab-group-btns">
              {g.tabs.map(t => (
                <button
                  key={t.id}
                  className={`tab-btn${tab === t.id ? ' active' : ''}`}
                  onClick={() => handleTabClick(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <main className={`app-main${tab === 'universe-report' || tab === 'strategy-validation' ? ' app-main-wide' : ''}`}>
        {tab === 'dashboard'       && <Dashboard onNavigateAnalysis={navigateToAnalysis} onNavigateUniverseReport={navigateToUniverseReport} onNavigateStrategyValidation={() => setTab('strategy-validation')} />}
        {tab === 'stocks'          && <StocksPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'universe-report' && <UniverseReportPage onNavigateAnalysis={navigateToAnalysis} initialJournalFilter={universeJournalFilter} />}
        {tab === 'strategy-validation' && <StrategyValidationPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'analysis'        && (
          <div className="research-layout">
            <AnalysisRail activeCode={analysisCode} onSelect={navigateToAnalysis} refreshKey={railRefreshKey} />
            <div className="research-main">
              <AnalysisPage
                key={analysisRequestId}
                initialCode={analysisCode}
                requestId={analysisRequestId}
                onCodeChange={handleAnalysisCodeSync}
                onWatchlistChanged={() => setRailRefreshKey(k => k + 1)}
              />
            </div>
          </div>
        )}
        {tab === 'watchlists' && <WatchlistsPage onNavigateAnalysis={navigateToAnalysis} onWatchlistChanged={() => setRailRefreshKey(k => k + 1)} />}
        {tab === 'overview'   && <PortfolioOverviewPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'portfolio' && <PortfolioPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'trades' && <TradesPage />}
        {tab === 'stats' && <StatsPage />}
      </main>
      </>
      )}
    </div>
  )
}
