import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { IntegrityRunSummary } from '../../types'

interface LatestReports {
  ok: boolean
  integrity: {
    available: boolean
    markdown: string
    filename: string
    run_id: string | null
    label: string
    missing: string
  }
  promo: {
    available: boolean
    markdown: string
    filename: string
    run_id: string | null
    label: string
    missing: string
  }
}

export default function ReportView() {
  const [reports, setReports] = useState<LatestReports | null>(null)
  const [runs, setRuns] = useState<IntegrityRunSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showIntegrityMd, setShowIntegrityMd] = useState(false)
  const [showPromoMd, setShowPromoMd] = useState(false)

  useEffect(() => {
    Promise.all([api.latestReports(), api.integrityRuns()])
      .then(([r, runsRes]) => {
        setReports(r)
        setRuns(runsRes.runs)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load reports'))
      .finally(() => setLoading(false))
  }, [])

  const handleDownload = (runId: string) => {
    api.downloadIntegrityReport(runId).catch((e) => {
      setError(e instanceof Error ? e.message : 'Download failed')
    })
  }

  const handleDownloadPromo = () => {
    api.downloadAutoJourneyLatestMd().catch((e) => {
      setError(e instanceof Error ? e.message : 'Download failed')
    })
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading reports…</div>
  if (error) return <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>

  return (
    <div className="space-y-4">
      {reports && (
        <>
          <div className="panel">
            <div className="panel-header">
              <span
                className="status-dot"
                style={{ background: reports.integrity.available ? '#00ff88' : '#374151' }}
              />
              Integrity Report
            </div>
            <div className="panel-body">
              {reports.integrity.available ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-[#6b7f94]">{reports.integrity.label}</span>
                    <div className="flex gap-2">
                      <button className="btn" onClick={() => setShowIntegrityMd(!showIntegrityMd)}>
                        {showIntegrityMd ? 'Hide' : 'View'}
                      </button>
                      {reports.integrity.run_id && (
                        <button className="btn btn--primary" onClick={() => handleDownload(reports.integrity.run_id!)}>
                          Download
                        </button>
                      )}
                    </div>
                  </div>
                  {showIntegrityMd && (
                    <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto bg-[#0a0e12] p-3 rounded-[2px]">
                      {reports.integrity.markdown}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="text-[11px] text-[#4a5c6e] italic">{reports.integrity.missing}</div>
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <span
                className="status-dot"
                style={{ background: reports.promo.available ? '#00ff88' : '#374151' }}
              />
              Promo Journey Report
            </div>
            <div className="panel-body">
              {reports.promo.available ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-[#6b7f94]">{reports.promo.label}</span>
                    <div className="flex gap-2">
                      <button className="btn" onClick={() => setShowPromoMd(!showPromoMd)}>
                        {showPromoMd ? 'Hide' : 'View'}
                      </button>
                      <button className="btn btn--primary" onClick={handleDownloadPromo}>
                        Download
                      </button>
                    </div>
                  </div>
                  {showPromoMd && (
                    <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto bg-[#0a0e12] p-3 rounded-[2px]">
                      {reports.promo.markdown}
                    </pre>
                  )}
                </div>
              ) : (
                <div className="text-[11px] text-[#4a5c6e] italic">{reports.promo.missing}</div>
              )}
            </div>
          </div>
        </>
      )}

      {runs.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot status-dot--dim" />
            Integrity Run History
          </div>
          <div className="panel-body">
            <div className="space-y-2">
              {runs.map((run) => {
                const completed = !!run.finished_at
                const dotColor = completed ? '#00ff88' : '#00e5ff'
                return (
                  <div key={run.id} className="flex items-center justify-between border border-[#1e2d3d] rounded-[2px] px-3 py-2">
                    <div className="flex items-center gap-3">
                      <span className="status-dot" style={{ background: dotColor }} />
                      <span className="text-[11px] text-[#c8d6e5]">{run.run_mode}</span>
                      <span className="text-[10px] font-mono text-[#6b7f94]">
                        {run.houses.join(', ')}
                      </span>
                      <span className="text-[10px] font-mono text-[#4a5c6e]">
                        {run.axes.length} axes · {run.scenario_count} scenarios
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-mono text-[#6b7f94]">
                        {new Date(run.started_at).toLocaleString()}
                      </span>
                      <span
                        className="mode-badge"
                        style={{
                          background: completed ? '#00ff8818' : '#00e5ff18',
                          color: completed ? '#00ff88' : '#00e5ff',
                        }}
                      >
                        {completed ? 'completed' : 'running'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
