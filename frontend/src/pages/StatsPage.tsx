import { useEffect, useState } from 'react'
import { api } from '../api/client'
import StatsPanel from '../components/StatsPanel'
import type { Stats } from '../types'

export default function StatsPage() {
  const [monthly, setMonthly] = useState<Stats | null>(null)
  const [all, setAll] = useState<Stats | null>(null)
  const [activePeriod, setActivePeriod] = useState<'monthly' | 'all'>('all')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.getStats('monthly'), api.getStats('all')])
      .then(([m, a]) => { setMonthly(m); setAll(a) })
      .catch(e => setError(e.message))
  }, [])

  if (error) return <p className="page-error">{error}</p>

  return (
    <div>
      <h2 className="page-subtitle">投資統計</h2>
      <StatsPanel
        monthly={monthly}
        all={all}
        activePeriod={activePeriod}
        onChangePeriod={setActivePeriod}
      />
    </div>
  )
}
