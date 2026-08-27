import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { DualReportTabs, type ReportBundle } from './DualReportTabs'
import { HOUSE_IDS, HOUSE_LABEL, modeClass } from '../lib/casino'
import type { CatalogGame, IntegrityResult, OpsHouseStatus } from '../types'

type Props = {
  open: boolean
  houses: OpsHouseStatus[]
  onClose: () => void
  onDone?: () => void
}

type Stage = 'pick' | 'running' | 'report'

const EMPTY_REPORT: ReportBundle = {
  available: false,
  markdown: '',
  filename: '',
  label: '',
}

export function GameSessionModal({ open, houses, onClose, onDone }: Props) {
  const live = houses.filter((h) => h.session_ok).map((h) => h.id)
  const defaultHouse = live[0] || HOUSE_IDS[0]
  const [house, setHouse] = useState(defaultHouse)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [games, setGames] = useState<CatalogGame[]>([])
  const [selected, setSelected] = useState<CatalogGame | null>(null)
  const [stage, setStage] = useState<Stage>('pick')
  const [busyList, setBusyList] = useState(false)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [results, setResults] = useState<IntegrityResult[]>([])
  const [integrityReport, setIntegrityReport] = useState<ReportBundle>(EMPTY_REPORT)
  const [promoReport, setPromoReport] = useState<ReportBundle>(EMPTY_REPORT)
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [playLab, setPlayLab] = useState(true)

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(query.trim()), 350)
    return () => window.clearTimeout(t)
  }, [query])

  useEffect(() => {
    if (!open) return
    setStage('pick')
    setSelected(null)
    setError('')
    setIntegrityReport(EMPTY_REPORT)
    setPromoReport(EMPTY_REPORT)
    setResults([])
    setHouse(live[0] || HOUSE_IDS[0])
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open || stage !== 'pick') return
    let cancelled = false
    setBusyList(true)
    setError('')
    api
      .integrityGames(house, debounced)
      .then((payload) => {
        if (cancelled) return
        setGames(payload.games || [])
        setNote(payload.note || '')
      })
      .catch((e: Error) => {
        if (cancelled) return
        setGames([])
        setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setBusyList(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, house, debounced, stage])

  const filtered = useMemo(() => games, [games])
  const sessionOk = Boolean(houses.find((h) => h.id === house)?.session_ok)

  const runSession = async () => {
    if (!selected?.game_id) return
    setStage('running')
    setError('')
    try {
      const payload = await api.integrityRun({
        houses: [house],
        run_mode: playLab ? 'CONFIRM_STAKE' : 'PROBE',
        persist: true,
        plan: true,
        require_auth: true,
        confirm_real_bet: playLab,
        target_game: {
          game_id: selected.game_id,
          name: selected.name || '',
          provider: selected.provider || '',
          slug: selected.slug || '',
          aggregator: selected.aggregator || '',
          category_hint: selected.category_hint || '',
          house,
        },
      })
      setResults(payload.results || [])
      setCounts(payload.coverage?.mode_counts || {})
      const thisIntegrity: ReportBundle = {
        available: Boolean(payload.report_markdown),
        markdown: payload.report_markdown || '',
        filename: payload.report_filename || `casino-integrity-${payload.id.slice(0, 8)}.md`,
        run_id: payload.id,
        label: 'Jornada de teste / Matriz',
        missing: 'Run de jogo sem markdown.',
      }
      setIntegrityReport(thisIntegrity)
      try {
        const latest = await api.latestReports()
        setPromoReport(latest.promo)
        if (!thisIntegrity.available) setIntegrityReport(latest.integrity)
      } catch {
        setPromoReport({
          available: false,
          markdown: '',
          filename: 'betbonus-auto-journey-latest.md',
          label: 'Jornada promo',
          missing: 'Não foi possível carregar o relatório da Jornada promo.',
        })
      }
      setStage('report')
      onDone?.()
    } catch (e) {
      setError((e as Error).message)
      setStage('pick')
    }
  }

  if (!open) return null

  return (
    <div className="iron-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="game-session-title">
      <div className="iron-modal">
        <div className="iron-modal-head">
          <div>
            <h3 id="game-session-title">Sessão de jogo</h3>
            <p className="muted">
              Catálogo da casa → um título → jornada completa. O lab mapeia o iframe do
              provedor (hosts/paths sem token). Com «Jogar 1 spin» clica no canvas do iframe
              (teto R$5). Sem protocolo de spin e sem saque.
            </p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>

        {stage === 'pick' && (
          <>
            <div className="iron-modal-filters">
              <div className="field">
                <label>Casa</label>
                <select value={house} onChange={(e) => setHouse(e.target.value)}>
                  {HOUSE_IDS.map((id) => {
                    const st = houses.find((h) => h.id === id)
                    return (
                      <option key={id} value={id}>
                        {HOUSE_LABEL[id]}
                        {st?.session_ok ? ' · sessão viva' : ' · sem sessão'}
                      </option>
                    )
                  })}
                </select>
              </div>
              <div className="field">
                <label>Buscar</label>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={
                    house === '4play'
                      ? 'olympus, aviator, jetx…'
                      : house === 'pagol_bet_br'
                        ? 'Nome ou id (≥3 letras na PAGOL)'
                        : 'Filtrar por id'
                  }
                />
              </div>
            </div>
            {!sessionOk && (
              <div className="journey-callout warn">Esta casa não tem sessão viva — o PROBE sai BLOCKED.</div>
            )}
            {error && <div className="journey-callout critical">{error}</div>}
            <div className="game-list">
              {busyList && <div className="muted">Carregando catálogo…</div>}
              {!busyList && filtered.length === 0 && (
                <div className="muted">{note || 'Nenhum jogo. Tente outro termo ou autentique a casa.'}</div>
              )}
              {filtered.map((g) => {
                const on = String(selected?.game_id) === String(g.game_id)
                return (
                  <button
                    key={String(g.game_id)}
                    type="button"
                    className={`game-row ${on ? 'game-row--on' : ''}`}
                    onClick={() => setSelected(g)}
                  >
                    <strong>{g.name || `ID ${g.game_id}`}</strong>
                    <span>
                      {g.provider || 'provider ?'}
                      {g.slug ? ` · ${g.slug}` : ''} · id {g.game_id}
                    </span>
                  </button>
                )
              })}
            </div>
            <label className="play-lab-toggle">
              <input
                type="checkbox"
                checked={playLab}
                onChange={(e) => setPlayLab(e.target.checked)}
              />
              <span>
                Jogar 1 spin na conta lab (CONFIRM_STAKE, teto R$5). O clique vai no iframe/canvas
                do provedor, não na página Salsa. O teto alerta se o stake default do cliente
                passar de R$5 — não é limiter do Pragmatic/Patagonia.
              </span>
            </label>
            <div className="iron-modal-foot">
              <span className="muted">
                {selected
                  ? `Alvo: ${selected.name || selected.game_id}`
                  : `${filtered.length} jogos · escolha um`}
              </span>
              <button
                type="button"
                className="btn btn-accent"
                disabled={!selected || !sessionOk}
                onClick={runSession}
              >
                Rodar jornada neste jogo
              </button>
            </div>
          </>
        )}

        {stage === 'running' && (
          <div className="journey-callout">
            Executando {playLab ? 'CONFIRM_STAKE (1 spin lab)' : 'PROBE'} em{' '}
            <strong>{HOUSE_LABEL[house]}</strong> com alvo{' '}
            <strong>{selected?.name || selected?.game_id}</strong>. Pode levar ~70s
            (iframe do provedor).
          </div>
        )}

        {stage === 'report' && (
          <>
            <div className="game-report-stats">
              <span className={modeClass('AUTOMATED')}>AUTO {counts.AUTOMATED ?? 0}</span>
              <span className={modeClass('SEMI_AUTO')}>SEMI {counts.SEMI_AUTO ?? 0}</span>
              <span className={modeClass('UNSUPPORTED')}>UNSUP {counts.UNSUPPORTED ?? 0}</span>
              <span className={modeClass('BLOCKED')}>BLOCK {counts.BLOCKED ?? 0}</span>
            </div>
            <div className="game-result-list">
              {results.map((row) => (
                <div key={row.id} className="game-result-row">
                  <span className={modeClass(row.mode)}>{row.mode.replace('_', ' ')}</span>
                  <div>
                    <code>{row.scenario_id}</code>
                    <div className="muted">{row.vulnerability || row.note}</div>
                  </div>
                </div>
              ))}
            </div>
            <DualReportTabs integrity={integrityReport} promo={promoReport} defaultTab="integrity" compact />
            <div className="iron-modal-foot">
              <button type="button" className="btn btn-ghost" onClick={() => setStage('pick')}>
                Outro jogo
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
