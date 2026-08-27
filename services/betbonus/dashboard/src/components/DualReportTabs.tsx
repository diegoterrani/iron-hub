import { useEffect, useState } from 'react'

export type ReportBundle = {
  available: boolean
  markdown: string
  filename: string
  run_id?: string | null
  label: string
  missing?: string
}

type TabId = 'integrity' | 'promo'

type Props = {
  integrity: ReportBundle
  promo: ReportBundle
  defaultTab?: TabId
  compact?: boolean
}

function downloadMd(markdown: string, filename: string) {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const EMPTY: ReportBundle = {
  available: false,
  markdown: '',
  filename: '',
  label: '',
  missing: 'Relatório indisponível.',
}

export function DualReportTabs({
  integrity,
  promo,
  defaultTab = 'integrity',
  compact = false,
}: Props) {
  const left = integrity.markdown ? integrity : { ...EMPTY, ...integrity }
  const right = promo.markdown ? promo : { ...EMPTY, ...promo }
  const [tab, setTab] = useState<TabId>(defaultTab)
  useEffect(() => {
    setTab(defaultTab)
  }, [defaultTab])
  const current = tab === 'integrity' ? left : right

  const downloadCurrent = () => {
    if (!current.available) return
    downloadMd(current.markdown, current.filename)
  }

  const downloadBoth = () => {
    if (left.available) downloadMd(left.markdown, left.filename)
    if (right.available) downloadMd(right.markdown, right.filename)
  }

  return (
    <div className="dual-reports">
      <div className="dual-reports-tabs" role="tablist" aria-label="Relatórios da jornada">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'integrity'}
          className={tab === 'integrity' ? 'active' : ''}
          onClick={() => setTab('integrity')}
        >
          Jornada de teste / Matriz
          <small>{left.available ? left.run_id?.slice(0, 8) || 'ok' : 'vazio'}</small>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'promo'}
          className={tab === 'promo' ? 'active' : ''}
          onClick={() => setTab('promo')}
        >
          Jornada promo
          <small>{right.available ? 'ok' : 'vazio'}</small>
        </button>
      </div>

      {current.available ? (
        <pre className={`game-report ${compact ? 'game-report--compact' : 'game-report--dual'}`}>
          {current.markdown}
        </pre>
      ) : (
        <div className="journey-callout warn">{current.missing || 'Relatório indisponível.'}</div>
      )}

      <div className="iron-modal-foot dual-reports-foot">
        <span className="muted">
          {current.available ? current.filename : current.label || 'Sem arquivo'}
        </span>
        <div className="actions">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!current.available}
            onClick={downloadCurrent}
          >
            Baixar este .md
          </button>
          <button type="button" className="btn btn-accent" disabled={!left.available && !right.available} onClick={downloadBoth}>
            Baixar os dois
          </button>
        </div>
      </div>
    </div>
  )
}
