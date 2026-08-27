import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Toast } from '../components/Toast'
import type { JourneyLogEvent, JourneySession, JourneySessionSummary } from '../types'

export function JourneyLogs() {
  const [sessions, setSessions] = useState<JourneySessionSummary[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [detail, setDetail] = useState<JourneySession | null>(null)
  const [stepFilter, setStepFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const loadSessions = async () => {
    const rows = await api.journeySessions(80)
    setSessions(rows)
    if (!selectedId && rows[0]) setSelectedId(rows[0].id)
  }

  const loadDetail = async (id: string) => {
    if (!id) {
      setDetail(null)
      return
    }
    setDetail(await api.getJourneySession(id))
  }

  useEffect(() => {
    loadSessions().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  useEffect(() => {
    if (!selectedId) return
    loadDetail(selectedId).catch((e: Error) => setToast({ message: e.message, error: true }))
    const timer = window.setInterval(() => {
      loadDetail(selectedId).catch(() => undefined)
      loadSessions().catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(timer)
  }, [selectedId])

  const events = useMemo(() => {
    const rows = detail?.events || []
    if (stepFilter === 'all') return rows
    return rows.filter((e) => e.step === stepFilter)
  }, [detail, stepFilter])

  const steps = useMemo(() => {
    const set = new Set((detail?.events || []).map((e) => e.step).filter(Boolean))
    return ['all', ...Array.from(set)]
  }, [detail])

  const exportJson = () => {
    if (!detail) return
    const blob = new Blob([JSON.stringify(detail, null, 2)], { type: 'application/json' })
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = `betbonus-journey-${detail.id.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(href)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Sessões de log</h2>
          <p>
            Detalhamento completo da jornada Casa → Scout → Auth → Discovery → Ledger → Abuse.
            Persistido em <code>data/journey_sessions.json</code>.
          </p>
        </div>
        <div className="actions">
          <Link className="btn btn-ghost" to="/">
            Ir à Jornada
          </Link>
          <button
            className="btn btn-ghost"
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              try {
                await loadSessions()
                if (selectedId) await loadDetail(selectedId)
              } finally {
                setBusy(false)
              }
            }}
          >
            Atualizar
          </button>
          <button className="btn btn-ghost" disabled={!detail} onClick={exportJson}>
            Exportar JSON
          </button>
          <button
            className="btn btn-danger"
            disabled={busy}
            onClick={async () => {
              if (!confirm('Apagar todas as sessões de log?')) return
              setBusy(true)
              try {
                await api.clearJourneySessions()
                setSelectedId('')
                setDetail(null)
                await loadSessions()
                setToast({ message: 'Sessões limpas' })
              } catch (e) {
                setToast({ message: (e as Error).message, error: true })
              } finally {
                setBusy(false)
              }
            }}
          >
            Limpar todas
          </button>
        </div>
      </div>

      <div className="logs-layout">
        <div className="panel logs-sessions">
          <h3>Sessões</h3>
          {sessions.length === 0 && <div className="empty">Nenhuma sessão ainda.</div>}
          <div className="session-list">
            {sessions.map((s) => (
              <button
                key={s.id}
                type="button"
                className={`session-item ${selectedId === s.id ? 'active' : ''}`}
                onClick={() => setSelectedId(s.id)}
              >
                <div className="session-item-top">
                  <strong>{s.house_name || s.platform || s.label}</strong>
                  <span className={`badge ${s.status === 'active' ? 'good' : ''}`}>{s.status}</span>
                </div>
                <div className="muted">
                  {s.event_count} eventos · {new Date(s.started_at).toLocaleString()}
                </div>
                <div className="muted truncate">{s.last_message}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="panel logs-detail">
          {!detail ? (
            <div className="empty">Selecione uma sessão para ver o detalhamento.</div>
          ) : (
            <>
              <div className="page-head" style={{ border: 0, marginBottom: 8, paddingBottom: 0 }}>
                <div>
                  <h3>{detail.label}</h3>
                  <p className="muted">
                    {detail.platform} · {detail.scout_mode || '—'} · {detail.event_count} eventos ·{' '}
                    <code>{detail.id.slice(0, 8)}</code>
                  </p>
                </div>
                <div className="actions">
                  <select value={stepFilter} onChange={(e) => setStepFilter(e.target.value)}>
                    {steps.map((s) => (
                      <option key={s} value={s}>
                        {s === 'all' ? 'Todas as etapas' : s}
                      </option>
                    ))}
                  </select>
                  {detail.status === 'active' && (
                    <button
                      className="btn btn-ghost"
                      onClick={async () => {
                        await api.closeJourneySession(detail.id, 'Encerrada pela tela de logs')
                        await loadDetail(detail.id)
                        await loadSessions()
                      }}
                    >
                      Encerrar
                    </button>
                  )}
                  <button
                    className="btn btn-danger"
                    onClick={async () => {
                      if (!confirm('Apagar esta sessão?')) return
                      await api.deleteJourneySession(detail.id)
                      setSelectedId('')
                      setDetail(null)
                      await loadSessions()
                    }}
                  >
                    Apagar
                  </button>
                </div>
              </div>

              <div className="journey-callout" style={{ marginBottom: 12 }}>
                URL: {detail.house_url || '—'}
                <br />
                Início: {new Date(detail.started_at).toLocaleString()}
                {detail.ended_at ? ` · Fim: ${new Date(detail.ended_at).toLocaleString()}` : ''}
              </div>

              <div className="activity-list" style={{ maxHeight: 'none' }}>
                {events.length === 0 && <div className="empty">Sem eventos neste filtro.</div>}
                {events.map((event: JourneyLogEvent) => (
                  <div className={`activity-item ${event.level}`} key={event.id}>
                    <div className="dot" />
                    <div style={{ width: '100%' }}>
                      <div>
                        <strong>[{event.step || 'system'}]</strong> {event.message}
                      </div>
                      <div className="meta">
                        {event.kind} · {event.level} ·{' '}
                        {new Date(event.created_at).toLocaleString()}
                      </div>
                      {event.detail && Object.keys(event.detail).length > 0 && (
                        <pre className="log-detail-json">
                          {JSON.stringify(event.detail, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
