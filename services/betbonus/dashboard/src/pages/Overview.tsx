import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { CategoryBadge } from '../components/CategoryBadge'
import { ScoreBar } from '../components/ScoreBar'
import { Toast } from '../components/Toast'
import type { ActivityEvent, BonusOffer, Stats } from '../types'

export function Overview() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [top, setTop] = useState<BonusOffer[]>([])
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const refresh = async () => {
    const [s, b, a] = await Promise.all([api.stats(), api.bonuses({ limit: 5 }), api.activity(8)])
    setStats(s)
    setTop(b)
    setActivity(a)
  }

  useEffect(() => {
    refresh().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const runDemo = async () => {
    setBusy(true)
    try {
      const offers = await api.runFixture(['bet365', 'betway', '888'])
      setToast({ message: `Pipeline demo: ${offers.length} offers processados` })
      await refresh()
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Overview</h2>
          <p>Painel operacional do BetBonus AI — métricas, pipeline e alertas recentes.</p>
        </div>
        <div className="actions">
          <Link className="btn btn-ghost" to="/pipeline">
            Abrir pipeline
          </Link>
          <button className="btn btn-accent" disabled={busy} onClick={runDemo}>
            {busy ? 'Rodando…' : 'Rodar demo'}
          </button>
        </div>
      </div>

      <div className="grid-stats">
        <div className="stat stat--info">
          <div className="label">Bonuses</div>
          <div className="value">{stats?.total ?? '—'}</div>
        </div>
        <div className="stat stat--medium">
          <div className="label">Avg score</div>
          <div className="value">{stats ? stats.avg_score.toFixed(1) : '—'}</div>
        </div>
        <div className="stat stat--low">
          <div className="label">Top score</div>
          <div className="value">{stats ? stats.top_score.toFixed(1) : '—'}</div>
        </div>
        <div className="stat stat--high">
          <div className="label">Notify ready</div>
          <div className="value">{stats?.notify_ready ?? '—'}</div>
        </div>
      </div>

      <div className="panel">
        <h3>Pipeline</h3>
        <div className="pipeline-track">
          {(stats?.pipeline ?? ['Scrape', 'Parse', 'NLP', 'Score', 'Classify', 'Store', 'Notify']).map(
            (step) => (
              <span className="pipeline-step" key={step}>
                {step}
              </span>
            ),
          )}
        </div>
      </div>

      <div className="two-col" style={{ marginTop: 14 }}>
        <div className="panel">
          <h3>Top bonuses</h3>
          {top.length === 0 ? (
            <div className="empty">Nenhum bônus ainda. Rode a demo ou o pipeline.</div>
          ) : (
            <div className="top-list">
              {top.map((offer) => (
                <div className="top-item" key={offer.id}>
                  <div>
                    <strong>{offer.title}</strong>
                    <div className="muted">
                      {offer.platform} · {offer.amount} {offer.currency} · {offer.wagering_multiple}x
                    </div>
                    <div style={{ marginTop: 6 }}>
                      <CategoryBadge category={offer.category} />
                    </div>
                  </div>
                  <ScoreBar score={offer.score} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <h3>Activity</h3>
          <div className="activity-list">
            {activity.length === 0 && <div className="empty">Sem eventos recentes.</div>}
            {activity.map((event) => (
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
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
