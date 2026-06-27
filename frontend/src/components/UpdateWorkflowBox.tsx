import { useState } from 'react'
import type { UpdateWorkflowStatus } from '../types'

export default function UpdateWorkflowBox({ workflow }: { workflow: UpdateWorkflowStatus | null }) {
  const [copied, setCopied] = useState(false)
  const statusText: Record<string, string> = {
    ready: '完成',
    action_required: '待處理',
    blocked: '阻塞',
  }
  const stepText: Record<string, string> = {
    done: '完成',
    warning: '提醒',
    blocked: '阻塞',
    running: '執行中',
  }

  const copyCommand = async () => {
    const command = workflow?.next_action?.copy_command || workflow?.next_action?.command
    if (!command) return
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(command)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = command
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
      console.error('copy update workflow command failed', error)
    }
  }

  if (!workflow) {
    return (
      <div className="daily-check-box daily-check-missing">
        <div className="daily-check-head">
          <div>
            <span className="old-wang-market-label">Update Workflow</span>
            <strong>每日更新流程尚未讀取</strong>
            <em>重新整理 Dashboard 後會顯示目前卡在哪一步。</em>
          </div>
          <span className="daily-check-badge warn">待讀取</span>
        </div>
      </div>
    )
  }

  const badgeClass = workflow.overall_status === 'ready'
    ? 'ok'
    : workflow.overall_status === 'blocked' ? 'block' : 'warn'

  return (
    <div className={`daily-check-box daily-check-${badgeClass}`}>
      <div className="daily-check-head">
        <div>
          <span className="old-wang-market-label">Update Workflow</span>
          <strong>每日更新流程</strong>
          <em>{workflow.headline}</em>
          {workflow.next_action && (
            <em className="daily-check-stale">
              下一步：{workflow.next_action.title}
              {workflow.next_action.command ? ` · ${workflow.next_action.command}` : ''}
            </em>
          )}
        </div>
        <span className={`daily-check-badge ${badgeClass}`}>
          {statusText[workflow.overall_status] ?? workflow.overall_status}
        </span>
      </div>

      <div className="daily-check-summary-grid">
        <div className={workflow.can_use_trade_outputs ? 'ok' : 'block'}>
          <span>交易輸出</span>
          <strong>{workflow.can_use_trade_outputs ? '可使用' : '暫停'}</strong>
        </div>
        {workflow.steps.map(step => (
          <div className={step.status === 'done' ? 'ok' : step.status === 'blocked' ? 'block' : 'warn'} key={step.key}>
            <span>{step.label}</span>
            <strong>{stepText[step.status] ?? step.status}</strong>
          </div>
        ))}
      </div>

      {workflow.next_action && (
        <div className="daily-check-action-list">
          <div className={`daily-check-action ${workflow.overall_status === 'blocked' ? 'block' : 'warn'}`}>
            <span>{workflow.next_action.action_type === 'wait' ? '等待' : '下一步'}</span>
            <strong>{workflow.next_action.title}</strong>
            <p>{workflow.next_action.detail}</p>
            {workflow.next_action.command && <small>{workflow.next_action.command}</small>}
            {workflow.next_action.expected_outputs.length > 0 && (
              <ul className="workflow-outputs">
                {workflow.next_action.expected_outputs.slice(0, 6).map(output => (
                  <li key={output}>{output}</li>
                ))}
              </ul>
            )}
            {workflow.next_action.command && (
              <button className="btn btn-ghost btn-xs" onClick={copyCommand}>
                {copied ? '已複製' : '複製指令'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
