import { useEffect, useRef, useState } from 'react'
import { api } from '../../services/api'
import type { ActivityEvent } from '../../types'

export default function IntelligenceFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const data = await api.activity(60)
        if (!cancelled) {
          setEvents(data)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Feed error')
      }
    }
    load()
    const id = setInterval(load, 8000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events])

  return (
    <div className="flex-1 flex flex-col min-h-0 border-b border-[#1e2d3d]">
      <div className="panel-header shrink-0">
        <span className="status-dot status-dot--cyan" />
        Intelligence Feed
        <span className="ml-auto text-[10px] text-[#4a5c6e]">{events.length} events</span>
      </div>
      <div ref={containerRef} className="flex-1 overflow-y-auto px-3 py-2">
        {error && (
          <div className="text-[11px] text-[#ff3b4d] font-mono">{error}</div>
        )}
        {!error && events.length === 0 && (
          <div className="text-[11px] text-[#4a5c6e] italic">Awaiting activity…</div>
        )}
        {events.map((ev) => (
          <div key={ev.id} className="log-line">
            <span className="log-timestamp">
              {new Date(ev.created_at).toLocaleTimeString('en-US', { hour12: false })}
            </span>
            <span
              className="log-step"
              style={{
                color:
                  ev.level === 'error'
                    ? '#ff3b4d'
                    : ev.level === 'warn'
                      ? '#ffb300'
                      : ev.level === 'success'
                        ? '#00ff88'
                        : '#00e5ff',
              }}
            >
              {ev.kind}
            </span>
            <span
              className="log-msg"
              style={{
                color:
                  ev.level === 'error'
                    ? '#ff3b4d'
                    : ev.level === 'warn'
                      ? '#ffb300'
                      : ev.level === 'success'
                        ? '#00ff88'
                        : '#c8d6e5',
              }}
            >
              {ev.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
