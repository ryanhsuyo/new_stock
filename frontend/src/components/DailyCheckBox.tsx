import { useState } from 'react'
import type { DailyCheckReport } from '../types'

interface DailyCheckBoxProps {
  report: DailyCheckReport | null
  expectedDataAsOf?: string | null
  onFocusFundamentals?: () => void
}

export default function DailyCheckBox({
  report,
  expectedDataAsOf,
  onFocusFundamentals,
}: DailyCheckBoxProps) {
  const [copiedActionKey, setCopiedActionKey] = useState<string | null>(null)
  const statusText: Record<string, string> = {
    ok: '正常',
    warn: '待補',
    block: '阻塞',
  }
  const actionText: Record<string, string> = {
    ok: '完成',
    warn: '待補',
    block: '阻塞',
    info: '提醒',
  }
  const workflowStepText: Record<string, string> = {
    done: '完成',
    todo: '待處理',
    blocked: '卡住',
  }

  const copyDailyCheckAction = async (key: string, text: string) => {
    if (!text) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.setAttribute('readonly', 'true')
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedActionKey(key)
      window.setTimeout(() => setCopiedActionKey(null), 1600)
    } catch (error) {
      console.error('copy daily check action failed', error)
    }
  }

  const dailyCheckActionButton = (action: DailyCheckReport['top_actions'][number]) => {
    const payload = action.action_payload
    if (!payload) return null

    if (payload.kind === 'copy_text' && payload.copy_text) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.copy_text || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製清單'}
        </button>
      )
    }
    if (payload.kind === 'command' && payload.command) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.copy_command || payload.command || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製指令'}
        </button>
      )
    }
    if (payload.kind === 'file' && payload.file_path) {
      return (
        <button className="btn btn-ghost btn-xs" onClick={() => copyDailyCheckAction(action.key, payload.file_path || '')}>
          {copiedActionKey === action.key ? '已複製' : '複製路徑'}
        </button>
      )
    }
    return null
  }

  const fundamentalsWorkflow = (action: DailyCheckReport['top_actions'][number]) => {
    if (action.key !== 'fundamentals') return null
    const details = action.details
    const checklist = details?.workflow_checklist ?? []
    const primaryAction = details?.workflow_primary_action
    if (!details?.workflow_stage && !details?.workflow_headline && checklist.length === 0 && !primaryAction) {
      return null
    }

    const copyValue = primaryAction?.command || action.action_payload?.file_path || action.action_payload?.copy_text || ''

    return (
      <div className="daily-check-fundamentals-workflow">
        <div className="daily-check-fundamentals-head">
          <span>{details?.workflow_stage || 'fundamentals workflow'}</span>
          <strong>{details?.workflow_headline || '基本面避雷補資料流程'}</strong>
        </div>
        {primaryAction && (
          <div className="daily-check-fundamentals-primary">
            <span>下一步</span>
            <strong>{primaryAction.label || '處理基本面補資料'}</strong>
            {primaryAction.command && <code>{primaryAction.command}</code>}
            <div className="daily-check-fundamentals-actions">
              {copyValue && (
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={() => copyDailyCheckAction(`${action.key}_workflow`, copyValue)}
                >
                  {copiedActionKey === `${action.key}_workflow` ? '已複製' : '複製路徑'}
                </button>
              )}
              {onFocusFundamentals && (
                <button className="btn btn-secondary btn-xs" onClick={onFocusFundamentals}>
                  看基本面補資料區
                </button>
              )}
            </div>
          </div>
        )}
        {checklist.length > 0 && (
          <div className="daily-check-fundamentals-steps">
            {checklist.map(step => (
              <div className={`daily-check-fundamentals-step ${step.status || 'todo'}`} key={step.key}>
                <span>{workflowStepText[String(step.status || '')] ?? step.status ?? '待處理'}</span>
                <strong>{step.label || step.key}</strong>
                {step.detail && <p>{step.detail}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (!report) {
    return (
      <div className="daily-check-box daily-check-missing">
        <div className="daily-check-head">
          <div>
            <span className="old-wang-market-label">PM Daily Check</span>
            <strong>尚未產生每日摘要</strong>
            <em>先在後端產生 daily_check.json，Dashboard 會讀取最新快照。</em>
          </div>
          <span className="daily-check-badge warn">待產生</span>
        </div>
        <code>python3 scripts/daily_check.py --write-report</code>
      </div>
    )
  }

  const dataDateNeedsRefresh = Boolean(
    report.data_as_of
    && expectedDataAsOf
    && report.data_as_of < expectedDataAsOf
  )
  const snapshotNeedsRefresh = Boolean(report.snapshot_is_stale)
  const needsRefresh = dataDateNeedsRefresh || snapshotNeedsRefresh
  const dataRepair = report.data_repair
  const dataRepairCount = dataRepair?.total_count ?? 0

  return (
    <div className={`daily-check-box daily-check-${report.overall_status}`}>
      <div className="daily-check-head">
        <div>
          <span className="old-wang-market-label">PM Daily Check</span>
          <strong>每日摘要快照</strong>
          <em>
            摘要 {report.generated_at || '—'}
            {' '}· 資料日 {report.data_as_of || '—'}
            {report.source_report_generated_at ? ` · 來源 ${report.source_report_generated_at}` : ''}
          </em>
          {dataDateNeedsRefresh && (
            <em className="daily-check-stale">
              摘要需刷新：目前資料已到 {expectedDataAsOf}，Daily Check 仍停在 {report.data_as_of}
            </em>
          )}
          {snapshotNeedsRefresh && (
            <em className="daily-check-stale">
              {report.snapshot_stale_reason || 'Daily Check 快照需刷新。'}
              {report.snapshot_refresh_command ? ` 指令：${report.snapshot_refresh_command}` : ''}
              {report.snapshot_refresh_command && (
                <button
                  type="button"
                  className="btn btn-ghost btn-xs"
                  onClick={() => copyDailyCheckAction(
                    'snapshot_refresh',
                    report.snapshot_refresh_copy_command || report.snapshot_refresh_command || '',
                  )}
                >
                  {copiedActionKey === 'snapshot_refresh' ? '已複製' : '複製刷新指令'}
                </button>
              )}
            </em>
          )}
        </div>
        <span className={`daily-check-badge ${needsRefresh ? 'warn' : report.overall_status}`}>
          {needsRefresh ? '需刷新' : (statusText[report.overall_status] ?? report.overall_status)}
        </span>
      </div>

      <div className="daily-check-summary-grid">
        <div className={report.can_use_trade_outputs ? 'ok' : 'block'}>
          <span>交易輸出</span>
          <strong>{report.can_use_trade_outputs ? '可使用' : '暫停'}</strong>
        </div>
        <div className={report.exit_code === 0 ? 'ok' : 'warn'}>
          <span>檢查代碼</span>
          <strong>{report.exit_code}</strong>
        </div>
        <div className={report.top_actions.length > 0 ? 'warn' : 'ok'}>
          <span>Top 待辦</span>
          <strong>{report.top_actions.length}</strong>
        </div>
        <div className={dataRepairCount > 0 ? 'warn' : 'ok'}>
          <span>資料修復</span>
          <strong>{dataRepairCount}</strong>
        </div>
      </div>

      {dataRepair && dataRepair.total_count > 0 && (
        <div className="daily-check-repair-strip">
          <div>
            <strong>追蹤股日線需修復</strong>
            <span>
              缺日線 {dataRepair.no_data_count} 檔 / 資料不足 {dataRepair.insufficient_count} 檔
            </span>
          </div>
          <div className="daily-check-repair-list">
            {dataRepair.top_items.slice(0, 4).map(item => (
              <span key={item.code}>
                {item.name || item.code}
                <em>{item.code}</em>
                <small>{item.status_label} · {item.row_count}/{item.required_rows}</small>
              </span>
            ))}
          </div>
        </div>
      )}

      {report.top_actions.length > 0 ? (
        <div className="daily-check-action-list">
          {report.top_actions.slice(0, 3).map(action => (
            <div className={`daily-check-action ${action.status}`} key={action.key}>
              <span>{actionText[action.status] ?? action.status}</span>
              <strong>{action.title}</strong>
              <p>{action.message}</p>
              <small>{action.next_action}</small>
              {action.action_payload?.expected_outputs && action.action_payload.expected_outputs.length > 0 && (
                <ul className="daily-check-outputs">
                  {action.action_payload.expected_outputs.slice(0, 4).map(output => (
                    <li key={output}>{output}</li>
                  ))}
                </ul>
              )}
              {action.action_payload?.preview_items && action.action_payload.preview_items.length > 0 && (
                <div className="pm-worklist-codes">
                  {action.action_payload.preview_items.slice(0, 5).map(label => <span key={label}>{label}</span>)}
                </div>
              )}
              {fundamentalsWorkflow(action)}
              {dailyCheckActionButton(action)}
            </div>
          ))}
        </div>
      ) : (
        <p className="workflow-ready-text">目前沒有 PM 優先待辦。</p>
      )}
    </div>
  )
}
