import { useState } from 'react'
import type { StockUniverseItem } from '../types'

const DATA_REPAIR_COMMAND = [
  'cd /Users/ryan/Desktop/code/new_stock/backend',
  'python3 scripts/daily_update.py --months 12',
].join('\n')

interface DataRepairQueueBoxProps {
  universe: StockUniverseItem[]
  onNavigateAnalysis?: (code: string) => void
}

export default function DataRepairQueueBox({
  universe,
  onNavigateAnalysis,
}: DataRepairQueueBoxProps) {
  const [copied, setCopied] = useState(false)
  const missing = universe.filter(item => item.data_status === 'no_data')
  const insufficient = universe.filter(item => item.data_status === 'insufficient')
  const repairItems = [...missing, ...insufficient].slice(0, 8)
  const hiddenCount = missing.length + insufficient.length - repairItems.length

  const copyRepairCommand = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(DATA_REPAIR_COMMAND)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = DATA_REPAIR_COMMAND
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch (error) {
      console.error('copy data repair command failed', error)
    }
  }

  if (universe.length === 0) {
    return (
      <div className="data-repair-box data-repair-missing">
        <div className="data-repair-head">
          <div>
            <span>資料修復隊列</span>
            <strong>尚無追蹤股票資料</strong>
            <em>請先確認 backend/data/leaders.json 是否存在。</em>
          </div>
        </div>
      </div>
    )
  }

  if (repairItems.length === 0) {
    return (
      <div className="data-repair-box data-repair-ready">
        <div className="data-repair-head">
          <div>
            <span>資料修復隊列</span>
            <strong>追蹤股票日線完整</strong>
            <em>{universe.length} 檔皆已有足夠日線資料。</em>
          </div>
          <span className="data-repair-badge ok">OK</span>
        </div>
      </div>
    )
  }

  return (
    <div className="data-repair-box data-repair-warn">
      <div className="data-repair-head">
        <div>
          <span>資料修復隊列</span>
          <strong>有 {missing.length + insufficient.length} 檔需補日線</strong>
          <em>缺日線 {missing.length} 檔 / 資料不足 {insufficient.length} 檔；修完再看正式交易判斷。</em>
        </div>
        <div className="data-repair-actions">
          <button className="btn btn-primary btn-sm" onClick={copyRepairCommand}>
            {copied ? '已複製' : '複製修復指令'}
          </button>
        </div>
      </div>
      <div className="data-repair-command">
        <pre>{DATA_REPAIR_COMMAND}</pre>
      </div>
      <div className="data-repair-list">
        {repairItems.map(item => (
          <button
            type="button"
            className={`data-repair-item ${item.data_status}`}
            key={item.code}
            onClick={() => onNavigateAnalysis?.(item.code)}
            disabled={!onNavigateAnalysis}
            title={onNavigateAnalysis ? '前往技術分析頁查看單檔診斷' : undefined}
          >
            <strong>{item.name} <em>{item.code}</em></strong>
            <span>{item.data_status === 'no_data' ? '尚未回補' : '資料不足'}</span>
            <small>
              {item.row_count}/{60} 筆
              {item.last_data_as_of ? ` · 最後 ${item.last_data_as_of}` : ' · 無資料日'}
            </small>
          </button>
        ))}
      </div>
      {hiddenCount > 0 && <p className="data-repair-more">另有 {hiddenCount} 檔未列出，修復指令會一起處理全部追蹤股票。</p>}
    </div>
  )
}
