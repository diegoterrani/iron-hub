import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Toast } from '../components/Toast'
import type { ActivityEvent } from '../types'

export function Activity() {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const load = async () => {
    setEvents(await api.activity(100))
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
    const id = window.setInterval(() => {
      load().catch(() => undefined)
    }, 5000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Activity</h2>
          <p>Feed operacional do pipeline, análises e limpezas. Auto-refresh a cada 5s.</p>
        </div>
        <div className="actions">
          <button className="btn btn-ghost" onClick={() => load()}>
            Atualizar
          </button>
          <button
            className="btn btn-danger"
            onClick={async () => {
              await api.clearActivity()
              await load()
              setToast({ message: 'Activity limpa' })
            }}
          >
            Limpar feed
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="activity-list" style={{ maxHeight: 'none' }}>
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
