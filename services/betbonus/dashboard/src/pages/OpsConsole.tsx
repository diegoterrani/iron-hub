import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { CoverageLegend } from '../components/CoverageLegend'
import { GameSessionModal } from '../components/GameSessionModal'
import { DualReportsModal } from '../components/DualReportsModal'
import { Toast } from '../components/Toast'
import { AXIS_LABEL, HOUSE_IDS, HOUSE_LABEL, modeClass } from '../lib/casino'
import type { IntegrityCatalog, OpsHouseStatus, OpsStatus } from '../types'

type StepId = 'auth' | 'houses' | 'run' | 'result'
type RunMode = 'DRY' | 'PROBE'

const STEPS: Array<{ id: StepId; n: number; title: string; hint: string }> = [
  { id: 'auth', n: 1, title: 'Autenticar', hint: 'Sessão viva no Admin' },
  { id: 'houses', n: 2, title: 'Escolher casas', hint: 'Quem entra no run' },
  { id: 'run', n: 3, title: 'Executar', hint: 'DRY e depois PROBE' },
  { id: 'result', n: 4, title: 'Ler cobertura', hint: 'Matriz do último run' },
]

const AXIS_FLOW = [
  'session',
  'wallet',
  'catalog',
  'slots',
  'crash',
  'table',
  'timer',
  'promo',
  'jackpot',
  'withdraw',
] as const

function scrollToStep(id: StepId) {
  document.getElementById(`passo-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function houseOf(ops: OpsStatus | null, id: string): OpsHouseStatus | undefined {
  return ops?.houses.find((h) => h.id === id)
}

export function OpsConsole() {
  const [ops, setOps] = useState<OpsStatus | null>(null)
  const [catalog, setCatalog] = useState<IntegrityCatalog | null>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<RunMode>('PROBE')
  const [selectedHouses, setSelectedHouses] = useState<string[]>([...HOUSE_IDS])
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)
  const [focus, setFocus] = useState<StepId | null>(null)
  const [gameModal, setGameModal] = useState(false)
  const [reportsModal, setReportsModal] = useState(false)

  const load = async () => {
    const [status, cat] = await Promise.all([api.opsStatus(), api.integrityCatalog()])
    setOps(status)
    setCatalog(cat)
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const toggleHouse = (id: string) => {
    setSelectedHouses((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const liveHouses = selectedHouses.filter((id) => houseOf(ops, id)?.session_ok)
  const staleHouses = selectedHouses.filter((id) => {
    const h = houseOf(ops, id)
    return Boolean(h?.has_token) && !h?.session_ok
  })
  const emptyHouses = selectedHouses.filter((id) => !houseOf(ops, id)?.has_token)
  const probeBlocked = mode === 'PROBE' && liveHouses.length === 0
  const housesReady = selectedHouses.length > 0
  const hasRun = Boolean(ops?.latest_run)

  const done: Record<StepId, boolean> = {
    auth: mode === 'DRY' || liveHouses.length > 0,
    houses: housesReady,
    run: hasRun,
    result: hasRun,
  }

  const current: StepId = !done.auth ? 'auth' : !done.houses ? 'houses' : !done.run ? 'run' : 'result'
  const active = focus ?? current

  const now = useMemo(() => {
    if (current === 'auth') {
      const dead = [...staleHouses, ...emptyHouses].map((id) => HOUSE_LABEL[id]).join(', ')
      return {
        tone: 'warn' as const,
        title: 'Passo 1 — autenticar contas de lab',
        body: `PROBE só fala com a casa se a sessão estiver viva. Sem isso o eixo sai BLOCKED. Pendente: ${dead || 'nenhuma casa selecionada'}. Cole o token no Admin ou tire a casa do run.`,
        to: '/admin',
        cta: 'Abrir sessões',
      }
    }
    if (current === 'houses') {
      return {
        tone: 'warn' as const,
        title: 'Passo 2 — escolher casas',
        body: 'Nenhuma casa selecionada. Clique nos cards abaixo para incluir no run.',
        to: undefined,
        cta: undefined,
      }
    }
    if (current === 'run') {
      return {
        tone: 'ok' as const,
        title: 'Passo 3 — executar o teste',
        body:
          mode === 'DRY'
            ? 'DRY valida o catálogo e os modelos offline (crash/mesa). Não chama a API da casa e não precisa de token. Depois troque para PROBE.'
            : `PROBE chama sessão, wallet, catálogo e launch nas casas selecionadas — sem spin no provider. Sessão viva: ${liveHouses.map((id) => HOUSE_LABEL[id]).join(', ') || 'nenhuma'}.`,
        to: undefined,
        cta: undefined,
      }
    }
    const blocked = catalog?.coverage?.mode_counts?.BLOCKED ?? 0
    const next = catalog?.planner?.next_scenario_id
    return {
      tone: blocked ? ('warn' as const) : ('ok' as const),
      title: 'Passo 4 — ler a cobertura',
      body: next
        ? `Último run ${ops?.latest_run?.run_mode}. Próximo agente sugerido: ${next}. AUTOMATED = API ok; SEMI AUTO = falta jogar no provider; BLOCKED = sessão/casa recusou.`
        : `Último run ${ops?.latest_run?.run_mode}. Leia a matriz: cada célula é o pior resultado daquele eixo na casa.`,
      to: '/agentes',
      cta: next ? 'Rodar próximo agente' : 'Agentes pontuais',
    }
  }, [catalog?.coverage?.mode_counts?.BLOCKED, catalog?.planner?.next_scenario_id, current, emptyHouses, liveHouses, mode, ops?.latest_run?.run_mode, staleHouses])

  const run = async () => {
    if (!housesReady || probeBlocked) return
    setBusy(true)
    try {
      const payload = await api.integrityRun({
        houses: selectedHouses,
        run_mode: mode,
        confirm_real_bet: false,
        persist: true,
        plan: true,
        require_auth: mode === 'PROBE',
      })
      const labels = selectedHouses.map((h) => HOUSE_LABEL[h] || h).join(', ')
      setToast({ message: `Run ${mode} · ${labels}: ${payload.results?.length || 0} cenários` })
      setFocus('result')
      await load()
      scrollToStep('result')
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const counts = catalog?.coverage?.mode_counts || {}
  const cells = catalog?.coverage?.cells || {}
  const matrixHouses = catalog?.houses || [...HOUSE_IDS]
  const axes = catalog?.axes || [...AXIS_FLOW]

  const go = (id: StepId) => {
    setFocus(id)
    scrollToStep(id)
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Jornada de teste</h2>
          <p>
            Integridade do cassino nas 3 casas Lucky: autenticar conta de lab, escolher quem entra,
            executar DRY e depois PROBE, ler a matriz. Sem spin de RNG e sem saque real.
          </p>
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={() => setReportsModal(true)}>
            Ver relatórios
          </button>
        </div>
      </div>

      <div className="test-rail" aria-label="Etapas da jornada de teste">
        {STEPS.map((step) => {
          const state = step.id === active ? 'active' : done[step.id] ? 'done' : ''
          return (
            <button
              key={step.id}
              type="button"
              className={`journey-step ${state}`}
              onClick={() => go(step.id)}
            >
              <span className="journey-index">{step.n}</span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.hint}</small>
              </span>
            </button>
          )
        })}
      </div>

      <div className={`journey-callout ${now.tone} test-now`}>
        <div>
          <strong>{now.title}</strong>
          <p>{now.body}</p>
        </div>
        <div className="actions">
          <button
            type="button"
            className="btn btn-accent"
            onClick={() => {
              setFocus('result')
              scrollToStep('result')
              setReportsModal(true)
            }}
          >
            Ver relatórios
          </button>
          {now.to && now.cta ? (
            <Link className="btn btn-ghost" to={now.to}>
              {now.cta}
            </Link>
          ) : null}
        </div>
      </div>

      <section id="passo-auth" className="test-section">
        <div className="test-section-head">
          <h3>1 · Autenticar</h3>
          <p>Conta de teste com sessão viva. Token salvo e expirado não conta — o PROBE sai BLOCKED.</p>
        </div>
        <div className="test-auth-row">
          {HOUSE_IDS.map((id) => {
            const h = houseOf(ops, id)
            const klass = h?.session_ok ? 'ok' : h?.has_token ? 'warn' : 'off'
            return (
              <div key={id} className={`test-auth-pill test-auth-pill--${klass}`}>
                <span>{HOUSE_LABEL[id]}</span>
                <strong>
                  {h?.session_ok ? 'sessão viva' : h?.has_token ? 'token expirado' : 'sem token'}
                </strong>
              </div>
            )
          })}
          <Link className="btn btn-ghost" to="/admin">
            Colar token no Admin
          </Link>
        </div>
      </section>

      <section id="passo-houses" className="test-section">
        <div className="test-section-head">
          <h3>2 · Escolher casas</h3>
          <p>
            Clique para incluir ou tirar do run. {selectedHouses.length}/3 no teste
            {mode === 'PROBE' && liveHouses.length
              ? ` · ${liveHouses.length} com sessão viva`
              : ''}
            .
          </p>
        </div>
        <div className="ops-houses">
          {HOUSE_IDS.map((id) => {
            const h = houseOf(ops, id)
            const on = selectedHouses.includes(id)
            const sessionClass = h?.session_ok
              ? 'ops-house--on'
              : h?.has_token
                ? 'ops-house--stale'
                : 'ops-house--off'
            return (
              <button
                key={id}
                type="button"
                className={`ops-house ${sessionClass} ${on ? 'ops-house--selected' : 'ops-house--idle'}`}
                title={h?.session_note || HOUSE_LABEL[id]}
                aria-pressed={on}
                disabled={busy}
                onClick={() => toggleHouse(id)}
              >
                <div className="ops-house-id">{HOUSE_LABEL[id]}</div>
                <div className="ops-house-st">
                  {on ? 'entra no run' : 'fora do run'}
                  {' · '}
                  {h?.session_ok ? 'pronta' : h?.has_token ? 'expirada' : 'sem sessão'}
                </div>
              </button>
            )
          })}
        </div>
      </section>

      <section id="passo-run" className="test-section">
        <div className="test-section-head">
          <h3>3 · Executar</h3>
          <p>
            Ordem recomendada: DRY (catálogo + sims) → PROBE autenticado (API da casa). O run percorre
            os eixos abaixo, nesta ordem.
          </p>
        </div>
        <ol className="axis-flow">
          {AXIS_FLOW.map((axis, i) => (
            <li key={axis}>
              <span>{String(i + 1).padStart(2, '0')}</span>
              {AXIS_LABEL[axis]}
            </li>
          ))}
        </ol>
        <div className="mode-cards">
          <button
            type="button"
            className={`mode-card ${mode === 'DRY' ? 'mode-card--on' : ''}`}
            disabled={busy}
            onClick={() => setMode('DRY')}
          >
            <strong>DRY</strong>
            <span>Não chama a casa. Serve para validar o harness e os modelos de crash/mesa.</span>
          </button>
          <button
            type="button"
            className={`mode-card ${mode === 'PROBE' ? 'mode-card--on' : ''}`}
            disabled={busy}
            onClick={() => setMode('PROBE')}
          >
            <strong>PROBE</strong>
            <span>
              Chama sessão, wallet, catálogo e launch. Exige sessão viva. Sem spin e sem saque.
            </span>
          </button>
        </div>
        <div className="test-run-actions">
          <button className="btn btn-ghost" disabled={busy} onClick={() => load()}>
            Atualizar status
          </button>
          <button className="btn btn-primary" disabled={busy} onClick={() => setGameModal(true)}>
            Testar um jogo
          </button>
          <button
            className="btn btn-accent"
            disabled={busy || !housesReady || probeBlocked}
            onClick={run}
            title={
              probeBlocked
                ? 'Nenhuma casa selecionada tem sessão viva — autenticar ou usar DRY'
                : undefined
            }
          >
            {busy
              ? 'Executando…'
              : probeBlocked
                ? 'PROBE bloqueado — autenticar'
                : `Executar ${mode} (${selectedHouses.length} casa${selectedHouses.length === 1 ? '' : 's'})`}
          </button>
        </div>
        {probeBlocked ? (
          <p className="muted integrity-footnote">
            Selecione uma casa com sessão viva ou cole o token no{' '}
            <Link to="/admin">Admin</Link>. DRY continua disponível sem sessão.
          </p>
        ) : null}
      </section>

      <section id="passo-result" className="test-section">
        <div className="test-section-head">
          <div>
            <h3>4 · Ler cobertura</h3>
            <p>
              {ops?.latest_run
                ? `Último run ${ops.latest_run.run_mode} · ${ops.latest_run.scenario_count} cenários · ${ops.latest_run.id.slice(0, 8)}`
                : 'Ainda não há run persistido — execute o passo 3.'}
            </p>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => setReportsModal(true)}>
            Ver relatórios
          </button>
        </div>

        <div className="grid-stats">
          <div className="stat stat--info">
            <div className="label">Agentes no catálogo</div>
            <div className="value">{ops?.scenario_count ?? catalog?.scenarios.length ?? '—'}</div>
          </div>
          <div className="stat stat--low">
            <div className="label">AUTOMATED</div>
            <div className="value">{counts.AUTOMATED ?? 0}</div>
          </div>
          <div className="stat stat--medium">
            <div className="label">SEMI / UNSUP</div>
            <div className="value">{(counts.SEMI_AUTO ?? 0) + (counts.UNSUPPORTED ?? 0)}</div>
          </div>
          <div className="stat stat--high">
            <div className="label">BLOCKED</div>
            <div className="value">{counts.BLOCKED ?? 0}</div>
          </div>
        </div>

        <div className="panel integrity-panel">
          <div className="panel-head-row">
            <h3>Cobertura ao vivo</h3>
            <button type="button" className="btn btn-primary" onClick={() => setReportsModal(true)}>
              Ver relatórios
            </button>
          </div>
          <div className="integrity-scroll">
            <table className="integrity-matrix">
              <thead>
                <tr>
                  <th>Casa</th>
                  {axes.map((axis) => (
                    <th key={axis}>{AXIS_LABEL[axis] || axis}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixHouses.map((house) => (
                  <tr key={house}>
                    <th scope="row">{HOUSE_LABEL[house] || house}</th>
                    {axes.map((axis) => {
                      const cell = cells[house]?.[axis]
                      const modeVal = cell?.mode || 'SKIPPED'
                      return (
                        <td key={axis}>
                          <span className={modeClass(modeVal)} title={cell?.title || modeVal}>
                            {modeVal.replace('_', ' ')}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <CoverageLegend />
        </div>
      </section>

      {gameModal && (
        <GameSessionModal
          open={gameModal}
          houses={ops?.houses || []}
          onClose={() => setGameModal(false)}
          onDone={() => {
            load().catch(() => undefined)
            scrollToStep('result')
          }}
        />
      )}
      <DualReportsModal open={reportsModal} onClose={() => setReportsModal(false)} />
      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
