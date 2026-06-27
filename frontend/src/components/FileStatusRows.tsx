import type { FileInfo } from '../types'

function StatusDot({ exists }: { exists: boolean }) {
  return (
    <span style={{ color: exists ? '#2e7d32' : '#bbb', fontSize: 16, marginRight: 6 }}>
      {exists ? '●' : '○'}
    </span>
  )
}

export function StatusRow({
  label,
  info,
  optional,
  extra,
}: {
  label: string
  info: FileInfo
  optional?: boolean
  extra?: string
}) {
  const fmtTime = (s?: string) => s ? s.slice(0, 16).replace('T', ' ') : ''

  return (
    <tr>
      <td style={{ width: 24, verticalAlign: 'middle' }}>
        <StatusDot exists={info.exists} />
      </td>
      <td style={{ fontWeight: 600, paddingRight: 20, whiteSpace: 'nowrap' }}>
        {label}
      </td>
      <td style={{ fontSize: 13, color: '#555' }}>
        {info.exists ? (
          <>
            {info.as_of && <span style={{ marginRight: 16 }}>as_of: <strong>{info.as_of}</strong></span>}
            {info.generated_at && <span style={{ marginRight: 16, color: '#666' }}>產生: {fmtTime(info.generated_at)}</span>}
            {info.row_count != null && <span style={{ marginRight: 16, color: '#666' }}>筆數: {info.row_count.toLocaleString()}</span>}
            {info.last_modified && <span style={{ color: '#888' }}>檔案: {fmtTime(info.last_modified)}</span>}
            {info.status_label && (
              <span style={{ marginLeft: 16, color: info.update_required ? '#b45309' : '#2e7d32', fontWeight: 700 }}>
                {info.status_label}
              </span>
            )}
            {info.parse_error && (
              <span
                style={{ marginLeft: 16, color: '#b71c1c', fontWeight: 700 }}
                title={info.parse_error}
              >
                解析失敗
              </span>
            )}
            {extra && <span style={{ marginLeft: 16, color: '#92400e', fontWeight: 700 }}>{extra}</span>}
          </>
        ) : (
          <span style={{ color: '#aaa' }}>{optional ? '不存在（選填）' : '不存在'}</span>
        )}
      </td>
    </tr>
  )
}
