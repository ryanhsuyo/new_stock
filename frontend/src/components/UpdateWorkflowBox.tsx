import { useState } from 'react'
import type { UpdateWorkflowStatus } from '../types'

interface UpdateWorkflowBoxProps {
  workflow: UpdateWorkflowStatus | null
  onDailyUpdate?: () => void
  busy?: boolean
  running?: boolean
}

export default function UpdateWorkflowBox({
  workflow,
  onDailyUpdate,
  busy = false,
  running = false,
}: UpdateWorkflowBoxProps) {
  const [copied, setCopied] = useState(false)
  const [manualCopied, setManualCopied] = useState(false)
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

  const manualUpdateAction = workflow?.checks?.manual_update_action as {
    copy_command?: string | null
    command?: string | null
    expected_outputs?: string[]
  } | undefined

  const copyText = async (command: string | null | undefined, onCopied: () => void) => {
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
      onCopied()
    } catch (error) {
      console.error('copy update workflow command failed', error)
    }
  }
  const copyCommand = async () => {
    const command = workflow?.next_action?.copy_command || workflow?.next_action?.command
    await copyText(command, () => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    })
  }
  const copyManualUpdateCommand = async () => {
    const command = manualUpdateAction?.copy_command || manualUpdateAction?.command
    await copyText(command, () => {
      setManualCopied(true)
      window.setTimeout(() => setManualCopied(false), 1600)
    })
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
        {onDailyUpdate && (
          <div className="daily-check-action-list">
            <div className="daily-check-action warn">
              <span>盤後資料</span>
              <strong>可以先觸發一鍵更新</strong>
              <p>等同後端 daily_update.py --months 1 的同源流程：更新 OHLCV、籌碼與策略輸出。</p>
              <button
                className="btn btn-primary btn-sm"
                onClick={onDailyUpdate}
                disabled={busy || running}
                title="觸發後端 update-now：backfill + chips + signals + daily_check"
              >
                {running ? '更新中…' : '盤後一鍵更新'}
              </button>
            </div>
          </div>
        )}
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
            {onDailyUpdate && workflow.next_action.action_type === 'update_data' && (
              <button
                className="btn btn-primary btn-xs"
                onClick={onDailyUpdate}
                disabled={busy || running}
                title="觸發後端 update-now：backfill + chips + signals + daily_check"
              >
                {running ? '更新中…' : '盤後一鍵更新'}
              </button>
            )}
          </div>
        </div>
      )}

      {onDailyUpdate && !workflow.next_action && (
        <div className="daily-check-action-list">
          <div className="daily-check-action ok">
            <span>盤後資料</span>
            <strong>需要時可手動刷新</strong>
            <p>按鈕會呼叫後端 update-now，執行 daily_update.py --months 1 同源流程，不在前端重算策略。</p>
            <button
              className="btn btn-ghost btn-xs"
              onClick={onDailyUpdate}
              disabled={busy || running}
              title="觸發後端 update-now：backfill + chips + signals + daily_check"
            >
              {running ? '更新中…' : '盤後一鍵更新'}
            </button>
            {manualUpdateAction?.command && (
              <>
                <small>{manualUpdateAction.command}</small>
                {manualUpdateAction.expected_outputs && manualUpdateAction.expected_outputs.length > 0 && (
                  <ul className="workflow-outputs">
                    {manualUpdateAction.expected_outputs.slice(0, 6).map(output => (
                      <li key={output}>{output}</li>
                    ))}
                  </ul>
                )}
                <button className="btn btn-ghost btn-xs" onClick={copyManualUpdateCommand}>
                  {manualCopied ? '已複製' : '複製手動指令'}
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
