import { useState } from 'react'
import { api } from '../api/client'
import { CategoryBadge } from '../components/CategoryBadge'
import { ScoreBar } from '../components/ScoreBar'
import { Toast } from '../components/Toast'
import type { BonusOffer } from '../types'

const SAMPLE = `Welcome Bonus — 100% up to $150. Wagering requirements: 25x.
Minimum deposit $10. Valid for 21 days. Max bet during bonus $5.
Only slots. Excluded: roulette, blackjack.`

export function Analyzer() {
  const [platform, setPlatform] = useState('manual')
  const [title, setTitle] = useState('')
  const [text, setText] = useState(SAMPLE)
  const [persist, setPersist] = useState(true)
  const [result, setResult] = useState<BonusOffer | null>(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const analyze = async () => {
    setBusy(true)
    try {
      const offer = await api.analyze({ platform, text, title, persist })
      setResult(offer)
      setToast({ message: `Score ${offer.score.toFixed(1)} (${offer.category})` })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const maxBreak = result
    ? Math.max(...Object.values(result.score_breakdown).map((v) => Math.abs(v)), 1)
    : 1

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Analyzer</h2>
          <p>Cole termos e condições — NLP extrai campos e o scoring classifica na hora.</p>
        </div>
        <button className="btn btn-ghost" onClick={() => setText(SAMPLE)}>
          Carregar exemplo
        </button>
      </div>

      <div className="two-col">
        <div className="panel">
          <div className="form-grid">
            <div className="form-row">
              <div className="field">
                <label>Platform</label>
                <input value={platform} onChange={(e) => setPlatform(e.target.value)} />
              </div>
              <div className="field">
                <label>Title (opcional)</label>
                <input value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Texto / T&Cs</label>
              <textarea value={text} onChange={(e) => setText(e.target.value)} />
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={persist}
                onChange={(e) => setPersist(e.target.checked)}
              />
              Persistir no store + notificar se score alto
            </label>
            <button className="btn btn-accent" disabled={busy || !text.trim()} onClick={analyze}>
              {busy ? 'Analisando…' : 'Analisar'}
            </button>
          </div>
        </div>

        <div className="panel">
          <h3>Resultado</h3>
          {!result ? (
            <div className="empty">Rode uma análise para ver extração e score.</div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 }}>
                <CategoryBadge category={result.category} />
                <ScoreBar score={result.score} />
              </div>
              <p>
                <strong>{result.title}</strong>
              </p>
              <p className="muted">
                Tipo {result.bonus_type} · {result.amount} {result.currency}
                {result.match_percent != null ? ` · ${result.match_percent}%` : ''}
                {result.free_spins != null ? ` · ${result.free_spins} spins` : ''}
              </p>
              <p className="muted">
                Wagering {result.wagering_multiple}x · Min {result.min_deposit} · Expiry{' '}
                {result.expiry_hours != null ? `${result.expiry_hours}h` : `${result.expiry_days}d`}
              </p>
              {result.game_restrictions.length > 0 && (
                <div className="chip-row" style={{ margin: '10px 0' }}>
                  {result.game_restrictions.map((r) => (
                    <span className="chip" key={r}>
                      {r}
                    </span>
                  ))}
                </div>
              )}
              <div className="breakdown" style={{ marginTop: 14 }}>
                {Object.entries(result.score_breakdown).map(([key, value]) => (
                  <div className="breakdown-row" key={key}>
                    <span>{key}</span>
                    <div className="track">
                      <i style={{ width: `${Math.max(0, (Math.abs(value) / maxBreak) * 100)}%` }} />
                    </div>
                    <strong>{value.toFixed(1)}</strong>
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
