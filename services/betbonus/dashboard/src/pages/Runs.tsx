import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Toast } from '../components/Toast'
import type { ActivityEvent, IntegrityRunSummary } from '../types'

export function Runs() {
  const [runs, setRuns] = useState<IntegrityRunSummary[]>([])
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const load = async () => {
    const [r, a] = await Promise.all([api.integrityRuns(20), api.activity(40)])
    setRuns(r.runs || [])
    setEvents(a)
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
    const id = window.setInterval(() => {
      load().catch(() => undefined)
    }, 8000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Histórico de runs</h2>
          <p>Passos 3–4 no tempo: cada execução DRY/PROBE e o feed operacional. Auto-refresh 8s.</p>
        </div>
        <div className="actions">
          <button className="btn btn-ghost" onClick={() => load()}>
            Atualizar
          </button>
        </div>
      </div>

      <div className="panel">
        <h3>Histórico</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Modo</th>
                <th>Cenários</th>
                <th>AUTO</th>
                <th>SEMI</th>
                <th>UNSUP</th>
                <th>BLOCK</th>
                <th>Fim</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="muted">
                    Nenhum run persistido.
                  </td>
                </tr>
              ) : (
                runs.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <code>{row.id.slice(0, 8)}</code>
                    </td>
                    <td>{row.run_mode}</td>
                    <td>{row.scenario_count}</td>
                    <td>{row.mode_counts?.AUTOMATED ?? 0}</td>
                    <td>{row.mode_counts?.SEMI_AUTO ?? 0}</td>
                    <td>{row.mode_counts?.UNSUPPORTED ?? 0}</td>
                    <td>{row.mode_counts?.BLOCKED ?? 0}</td>
                    <td className="muted">
                      {row.finished_at ? new Date(row.finished_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <h3>Activity</h3>
        <div className="activity-list" style={{ maxHeight: 360 }}>
          {events.length === 0 && <div className="empty">Sem eventos.</div>}
          {events.map((event) => (
            <div className={`activity-item ${event.level}`} key={event.id}>
              <div className="dot" />
              <div>
                <div>{event.message}</div>
                <div className="meta">
                  {event.kind} · {new Date(event.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
