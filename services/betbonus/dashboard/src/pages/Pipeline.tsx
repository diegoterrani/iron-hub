import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { CategoryBadge } from '../components/CategoryBadge'
import { ScoreBar } from '../components/ScoreBar'
import { Toast } from '../components/Toast'
import type { BonusOffer, PlatformInfo } from '../types'

export function Pipeline() {
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [selected, setSelected] = useState<string[]>(['bet365', 'betway', '888'])
  const [platform, setPlatform] = useState('generic')
  const [html, setHtml] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [results, setResults] = useState<BonusOffer[]>([])
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  useEffect(() => {
    api.platforms().then((p) => {
      setPlatforms(p)
      if (p[0]) setPlatform(p[0].id)
    })
  }, [])

  const togglePlatform = (id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const wrap = async (fn: () => Promise<BonusOffer[]>, okMsg: string) => {
    setBusy(true)
    try {
      const offers = await fn()
      setResults(offers)
      setToast({ message: okMsg.replace('{n}', String(offers.length)) })
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
          <h2>Pipeline</h2>
          <p>Execute scrape → NLP → score → store. Use fixtures, HTML colado, upload, URL ou live API.</p>
        </div>
        <button
          className="btn btn-accent"
          disabled={busy}
          onClick={async () => {
            setBusy(true)
            try {
              const res = await api.runLive('4play')
              setResults(res.offers)
              if (!res.ok) setToast({ message: res.error || 'Falha no scrape 4Play', error: true })
              else setToast({ message: `4Play.game: ${res.offers.length} promoções` })
            } catch (e) {
              setToast({ message: (e as Error).message, error: true })
            } finally {
              setBusy(false)
            }
          }}
        >
          {busy ? 'Scraping…' : 'Testar 4Play.game'}
        </button>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <h3>Live — 4Play.game</h3>
        <p className="muted">
          Público: <code>/site/promotions</code>. Com token em <strong>Auth / Tokens</strong>: também{' '}
          <code>/bonus</code> (bônus da conta).
        </p>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>1. Demo com fixtures</h3>
          <p className="muted">Roda `sample_promos.html` nas plataformas selecionadas.</p>
          <div className="chip-row" style={{ margin: '12px 0' }}>
            {platforms.map((p) => (
              <button
                key={p.id}
                className={`chip ${selected.includes(p.id) ? 'chip--active' : ''}`}
                onClick={() => togglePlatform(p.id)}
                type="button"
              >
                {p.id}
              </button>
            ))}
          </div>
          <button
            className="btn btn-accent"
            disabled={busy || selected.length === 0}
            onClick={() =>
              wrap(() => api.runFixture(selected), 'Fixture processada: {n} offers')
            }
          >
            Rodar fixture
          </button>
        </div>

        <div className="panel">
          <h3>2. Upload HTML</h3>
          <div className="form-grid">
            <div className="field">
              <label>Platform</label>
              <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {platforms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id} ({p.scraper})
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Arquivo</label>
              <input
                type="file"
                accept=".html,.htm,.txt"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <button
              className="btn btn-primary"
              disabled={busy || !file}
              onClick={() =>
                file &&
                wrap(() => api.upload(platform, file), 'Upload processado: {n} offers')
              }
            >
              Enviar e processar
            </button>
          </div>
        </div>
      </div>

      <div className="two-col" style={{ marginTop: 14 }}>
        <div className="panel">
          <h3>3. Colar HTML</h3>
          <div className="form-grid">
            <div className="field">
              <label>Platform</label>
              <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {platforms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>HTML</label>
              <textarea
                value={html}
                onChange={(e) => setHtml(e.target.value)}
                placeholder="<div class='promo-card'>100% up to $100 · 25x wagering...</div>"
              />
            </div>
            <button
              className="btn btn-primary"
              disabled={busy || !html.trim()}
              onClick={() =>
                wrap(() => api.runHtml(platform, html), 'HTML processado: {n} offers')
              }
            >
              Processar HTML
            </button>
          </div>
        </div>

        <div className="panel">
          <h3>4. URL live (best-effort)</h3>
          <p className="muted">Sites grandes podem bloquear scrapers. Prefira HTML dump.</p>
          <div className="form-grid">
            <div className="field">
              <label>Platform</label>
              <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {platforms.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>URL</label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/promotions/"
              />
            </div>
            <button
              className="btn btn-ghost"
              disabled={busy || !url.trim()}
              onClick={async () => {
                setBusy(true)
                try {
                  const res = await api.runUrl(platform, url)
                  setResults(res.offers)
                  if (!res.ok) {
                    setToast({ message: res.error || 'Falha no scrape', error: true })
                  } else {
                    setToast({ message: `${res.offers.length} offers da URL` })
                  }
                } catch (e) {
                  setToast({ message: (e as Error).message, error: true })
                } finally {
                  setBusy(false)
                }
              }}
            >
              Scrapear URL
            </button>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <h3>Resultado da última execução</h3>
        {results.length === 0 ? (
          <div className="empty">Ainda sem resultados nesta sessão.</div>
        ) : (
          <div className="top-list">
            {results.map((offer) => (
              <div className="top-item" key={offer.id}>
                <div>
                  <strong>{offer.title}</strong>
                  <div className="muted">
                    {offer.platform} · {offer.bonus_type} · {offer.wagering_multiple}x
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

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
