import { useState } from 'react'
import AnalysisPage from './pages/AnalysisPage'
import Dashboard from './pages/Dashboard'
import PortfolioOverviewPage from './pages/PortfolioOverviewPage'
import PortfolioPage from './pages/PortfolioPage'
import StatsPage from './pages/StatsPage'
import StocksPage from './pages/StocksPage'
import TradesPage from './pages/TradesPage'
import UniverseReportPage from './pages/UniverseReportPage'
import WatchlistsPage from './pages/WatchlistsPage'

type Tab = 'dashboard' | 'stocks' | 'universe-report' | 'analysis' | 'watchlists' | 'overview' | 'portfolio' | 'trades' | 'stats'
type UniverseJournalFilter = 'all' | 'unrecorded' | 'recorded'

const TABS: { id: Tab; label: string }[] = [
  { id: 'dashboard',       label: '訊號 Dashboard' },
  { id: 'stocks',          label: '推薦清單' },
  { id: 'universe-report', label: '候選股篩選報告' },
  { id: 'analysis',        label: '技術分析' },
  { id: 'watchlists',      label: '觀察清單' },
  { id: 'overview',        label: '投組總覽' },
  { id: 'portfolio',       label: '持倉損益' },
  { id: 'trades',          label: '交易紀錄' },
  { id: 'stats',           label: '統計' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
  // 從投組頁點擊跳轉時帶入的股票代碼，undefined 表示手動進入
  const [analysisCode, setAnalysisCode] = useState<string | undefined>(undefined)
  const [analysisRequestId, setAnalysisRequestId] = useState(0)
  const [universeJournalFilter, setUniverseJournalFilter] = useState<UniverseJournalFilter>('all')

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

  function navigateToUniverseReport(journalFilter: UniverseJournalFilter = 'all') {
    setUniverseJournalFilter(journalFilter)
    setTab('universe-report')
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">台灣股票分析與投資紀錄</h1>
      </header>

      <nav className="tab-nav">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn${tab === t.id ? ' active' : ''}`}
            onClick={() => handleTabClick(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className={`app-main${tab === 'universe-report' ? ' app-main-wide' : ''}`}>
        {tab === 'dashboard'       && <Dashboard onNavigateAnalysis={navigateToAnalysis} onNavigateUniverseReport={navigateToUniverseReport} />}
        {tab === 'stocks'          && <StocksPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'universe-report' && <UniverseReportPage onNavigateAnalysis={navigateToAnalysis} initialJournalFilter={universeJournalFilter} />}
        {tab === 'analysis'        && <AnalysisPage key={analysisRequestId} initialCode={analysisCode} requestId={analysisRequestId} />}
        {tab === 'watchlists' && <WatchlistsPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'overview'   && <PortfolioOverviewPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'portfolio' && <PortfolioPage onNavigateAnalysis={navigateToAnalysis} />}
        {tab === 'trades' && <TradesPage />}
        {tab === 'stats' && <StatsPage />}
      </main>
    </div>
  )
}
