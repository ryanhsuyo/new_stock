import type { SignalsStatus } from '../types'

export default function ParseErrorAlert({ status }: { status: SignalsStatus | null }) {
  const files = status ? [
    { label: 'summary.json', info: status.out_files.summary_json },
    { label: 'universe_report.csv', info: status.out_files.universe_report_csv },
    { label: 'daily_brief.json', info: status.out_files.daily_brief_json },
  ].filter(item => item.info.parse_error) : []

  if (!files.length) return null

  return (
    <div className="alert alert-error" role="alert" style={{ marginBottom: 20 }}>
      <div className="alert-title">輸出檔案解析失敗</div>
      <div className="alert-meta">請重新產生訊號；若仍失敗，檢查後端寫檔流程或手動修改的 JSON / CSV 格式。</div>
      <div className="parse-error-list">
        {files.map(file => (
          <div key={file.label}>
            <strong>{file.label}</strong>
            <code>{file.info.parse_error}</code>
          </div>
        ))}
      </div>
    </div>
  )
}
