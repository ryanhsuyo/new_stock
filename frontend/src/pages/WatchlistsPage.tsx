import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { WatchlistGroup } from '../types'

interface Props {
  onNavigateAnalysis?: (code: string) => void
  /** watchlist CRUD 成功後通知 App，讓研究頁 rail 重新抓取 */
  onWatchlistChanged?: () => void
  regionFilter?: 'TW' | 'US'
}

export default function WatchlistsPage({ onNavigateAnalysis, onWatchlistChanged, regionFilter }: Props) {
  const [groups, setGroups]         = useState<WatchlistGroup[]>([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [newName, setNewName]       = useState('')
  const [creating, setCreating]     = useState(false)
  const [createErr, setCreateErr]   = useState('')

  const loadGroups = () =>
    api.getWatchlists()
      .then(setGroups)
      .catch(e => setError(e instanceof Error ? e.message : '載入失敗'))

  useEffect(() => {
    loadGroups().finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate() {
    const name = newName.trim()
    if (!name) return
    setCreating(true)
    setCreateErr('')
    try {
      await api.createWatchlist(name)
      onWatchlistChanged?.()
      setNewName('')
      await loadGroups()
    } catch (e) {
      setCreateErr(e instanceof Error ? e.message : '建立失敗')
    } finally {
      setCreating(false)
    }
  }

  async function handleDeleteGroup(groupName: string) {
    if (!confirm(`確定要刪除群組「${groupName}」及其所有股票？`)) return
    try {
      await api.deleteWatchlist(groupName)
      onWatchlistChanged?.()
      await loadGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : '刪除失敗')
    }
  }

  async function handleRemoveStock(groupName: string, code: string, region: 'TW' | 'US' = 'TW') {
    try {
      await api.removeFromWatchlist(groupName, code, region)
      onWatchlistChanged?.()
      await loadGroups()
    } catch (e) {
      setError(e instanceof Error ? e.message : '移除失敗')
    }
  }

  if (loading) return <p className="page-loading">載入中…</p>
  if (error)   return <p className="page-error">{error}</p>

  return (
    <div className="watchlists-page">
      <div className="page-actions">
        <h2 className="page-subtitle">觀察清單{regionFilter ? ` · ${regionFilter === 'US' ? '美股' : '台股'}` : ''}</h2>
      </div>

      {/* ── 建立新群組 ── */}
      <div className="watchlist-create-bar">
        <input
          type="text"
          className="watchlist-name-input"
          value={newName}
          onChange={e => { setNewName(e.target.value); setCreateErr('') }}
          onKeyDown={e => e.key === 'Enter' && handleCreate()}
          placeholder="輸入新群組名稱，例：科技股"
          maxLength={30}
        />
        <button
          className="btn btn-primary btn-sm"
          onClick={handleCreate}
          disabled={creating || !newName.trim()}
        >
          {creating ? '建立中…' : '+ 建立群組'}
        </button>
        {createErr && <span className="form-error">{createErr}</span>}
      </div>

      {/* ── 群組列表 ── */}
      {groups.length === 0 ? (
        <p className="empty-hint">尚無觀察清單群組，請先建立一個群組。</p>
      ) : (
        <div className="watchlist-groups">
          {groups.map(group => {
            const stocks = group.stocks.filter(stock => !regionFilter || (stock.region ?? 'TW') === regionFilter)
            return (
            <div key={group.name} className="watchlist-group-card">
              <div className="watchlist-group-header">
                <span className="watchlist-group-name">{group.name}</span>
                <span className="watchlist-group-count">{stocks.length} 支</span>
                <button
                  className="btn-icon-del"
                  onClick={() => handleDeleteGroup(group.name)}
                  title={`刪除群組「${group.name}」`}
                >
                  ✕
                </button>
              </div>

              {stocks.length === 0 ? (
                <p className="watchlist-empty-group">此群組尚無股票，可在「技術分析」頁加入。</p>
              ) : (
                <table className="data-table watchlist-table">
                  <thead>
                    <tr>
                      <th>股票</th>
                      <th>加入日期</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {stocks.map(s => (
                      <tr key={`${s.region ?? 'TW'}-${s.code}`}>
                        <td>
                          {onNavigateAnalysis ? (
                            <button
                              className="link-btn"
                              onClick={() => onNavigateAnalysis(s.code)}
                              title={`查看 ${s.name}（${s.code}）技術分析`}
                            >
                              <span className="td-name">{s.name}</span>
                              <span className="td-id">{s.code}</span>
                              <span className={`watchlist-region-badge region-${(s.region ?? 'TW').toLowerCase()}`}>{s.region ?? 'TW'}</span>
                            </button>
                          ) : (
                            <>
                              <span className="td-name">{s.name}</span>
                              <span className="td-id">{s.code}</span>
                              <span className={`watchlist-region-badge region-${(s.region ?? 'TW').toLowerCase()}`}>{s.region ?? 'TW'}</span>
                            </>
                          )}
                        </td>
                        <td style={{ color: '#888', fontSize: 12 }}>{s.added_at}</td>
                        <td>
                          <button
                            className="btn-icon-del"
                            onClick={() => handleRemoveStock(group.name, s.code, s.region ?? 'TW')}
                            title={`從「${group.name}」移除 ${s.name}`}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )})}
        </div>
      )}
    </div>
  )
}
