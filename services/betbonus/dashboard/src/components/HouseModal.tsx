import { useEffect, useMemo, useState } from 'react'

export type HouseDraft = {
  id: string
  name: string
  platform: string
  url: string
  blurb: string
  scoutMode: 'live' | 'url' | 'html'
  auth: 'token|login' | 'token' | 'optional'
}

type Props = {
  open: boolean
  initial?: Partial<HouseDraft>
  onClose: () => void
  onSave: (house: HouseDraft) => void
}

function slugify(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40)
}

function guessScoutMode(platform: string, url: string): HouseDraft['scoutMode'] {
  if (
    platform === '4play' ||
    platform === '4play_bet_br' ||
    platform === 'pagol' ||
    platform === 'pagol_bet_br' ||
    /4play\.game/i.test(url) ||
    /4play\.bet\.br/i.test(url) ||
    /pagol\.bet\.br/i.test(url)
  ) {
    return 'live'
  }
  if (url.trim()) return 'url'
  return 'html'
}

const LIVE_PLATFORMS = new Set(['4play', '4play_bet_br', 'pagol', 'pagol_bet_br'])

export function HouseModal({ open, initial, onClose, onSave }: Props) {
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('')
  const [platformTouched, setPlatformTouched] = useState(false)
  const [url, setUrl] = useState('')
  const [blurb, setBlurb] = useState('Casa redteam · teste de campanha')
  const [scoutMode, setScoutMode] = useState<HouseDraft['scoutMode']>('url')
  const [auth, setAuth] = useState<HouseDraft['auth']>('optional')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    const n = initial?.name || ''
    const p = initial?.platform || (n ? slugify(n) : '')
    const u = initial?.url || ''
    setName(n)
    setPlatform(p)
    setPlatformTouched(Boolean(initial?.platform))
    setUrl(u)
    setBlurb(initial?.blurb || 'Casa redteam · teste de campanha')
    setScoutMode(initial?.scoutMode || guessScoutMode(p, u))
    setAuth(initial?.auth || (p === '4play' ? 'token|login' : 'optional'))
    setError('')
  }, [open, initial])

  const previewId = useMemo(() => platform || slugify(name) || 'nova_casa', [platform, name])

  if (!open) return null

  const submit = () => {
    const cleanName = name.trim()
    const cleanPlatform = (platform.trim() || slugify(cleanName)).replace(/\s+/g, '_')
    const cleanUrl = url.trim()
    if (!cleanName) {
      setError('Informe o nome da casa')
      return
    }
    if (!cleanPlatform) {
      setError('Informe o platform id')
      return
    }
    if (scoutMode !== 'html' && !cleanUrl) {
      setError('Informe a URL de promoções (ou use modo HTML)')
      return
    }
    if (scoutMode === 'live' && !LIVE_PLATFORMS.has(cleanPlatform)) {
      setError('Scout live API hoje: 4play ou pagol_bet_br — use URL/HTML para outras casas')
      return
    }
    onSave({
      id: initial?.id || cleanPlatform,
      name: cleanName,
      platform: cleanPlatform,
      url: cleanUrl,
      blurb: blurb.trim() || 'Casa redteam',
      scoutMode,
      auth,
    })
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="house-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <h3 id="house-modal-title">Nova casa de teste</h3>
            <p className="muted">Cadastre uma casa do Iron Red Team para a jornada de abuso.</p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>

        <div className="form-grid">
          <div className="field">
            <label>Nome da casa</label>
            <input
              autoFocus
              placeholder="Ex.: LuckyBet CR"
              value={name}
              onChange={(e) => {
                const next = e.target.value
                setName(next)
                if (!platformTouched) setPlatform(slugify(next))
              }}
            />
          </div>

          <div className="form-row">
            <div className="field">
              <label>Platform id</label>
              <input
                placeholder="ex.: luckybet_cr"
                value={platform}
                onChange={(e) => {
                  setPlatformTouched(true)
                  setPlatform(slugify(e.target.value) || e.target.value)
                }}
              />
              <small className="muted">Usado em credentials, ledger e findings · `{previewId}`</small>
            </div>
            <div className="field">
              <label>Auth</label>
              <select value={auth} onChange={(e) => setAuth(e.target.value as HouseDraft['auth'])}>
                <option value="optional">Opcional (só promo pública)</option>
                <option value="token">Bearer token</option>
                <option value="token|login">Token ou login</option>
              </select>
            </div>
          </div>

          <div className="field">
            <label>URL de promoções / bônus</label>
            <input
              placeholder="https://casa.exemplo/promotions"
              value={url}
              onChange={(e) => {
                const next = e.target.value
                setUrl(next)
                if (scoutMode !== 'html') {
                  setScoutMode(guessScoutMode(platform || slugify(name), next))
                }
              }}
            />
          </div>

          <div className="field">
            <label>Modo Scout</label>
            <div className="segmented">
              {(
                [
                  ['url', 'URL scrape'],
                  ['live', 'Live API'],
                  ['html', 'HTML / upload'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={scoutMode === id ? 'active' : ''}
                  onClick={() => setScoutMode(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <small className="muted">
              Live API = adapter nativo (4Play). URL = fetch HTML. HTML = colar/upload no Scout.
            </small>
          </div>

          <div className="field">
            <label>Nota / contexto redteam</label>
            <input
              placeholder="Staging · campanha welcome mar/2026"
              value={blurb}
              onChange={(e) => setBlurb(e.target.value)}
            />
          </div>

          {error && <div className="journey-callout critical">{error}</div>}

          <div className="actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancelar
            </button>
            <button type="button" className="btn btn-accent" onClick={submit}>
              Salvar casa e usar
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
