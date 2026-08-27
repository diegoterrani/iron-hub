import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { CoverageLegend } from '../components/CoverageLegend'
import { DualReportsModal } from '../components/DualReportsModal'
import { Toast } from '../components/Toast'
import { AXIS_LABEL, HOUSE_IDS, HOUSE_LABEL, modeClass } from '../lib/casino'
import type { IntegrityCatalog, IntegrityResult } from '../types'

export function Integrity() {
  const [data, setData] = useState<IntegrityCatalog | null>(null)
  const [results, setResults] = useState<IntegrityResult[]>([])
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'DRY' | 'PROBE'>('PROBE')
  const [selectedHouses, setSelectedHouses] = useState<string[]>([...HOUSE_IDS])
  const [houseFilter, setHouseFilter] = useState<string>('all')
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)
  const [reportsModal, setReportsModal] = useState(false)

  const load = async () => {
    const cat = await api.integrityCatalog()
    setData(cat)
    setResults(cat.results || [])
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const counts = data?.coverage?.mode_counts || {}
  const cells = data?.coverage?.cells || {}
  const houses = data?.houses || []
  const axes = data?.axes || []

  const filteredResults = useMemo(() => {
    if (houseFilter === 'all') return results
    return results.filter((r) => r.platform === houseFilter)
  }, [results, houseFilter])

  const run = async () => {
    if (!selectedHouses.length) return
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
      setResults(payload.results || [])
      setData((prev) =>
        prev
          ? {
              ...prev,
              coverage: payload.coverage,
              latest_run_id: payload.id,
              run_mode: payload.run_mode,
              finished_at: payload.finished_at,
              planner: payload.planner,
              notes: payload.notes,
              results: payload.results,
            }
          : prev,
      )
      setToast({
        message: `Run ${mode}: ${payload.results?.length || 0} cenários`,
      })
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
          <h2>Matriz de cobertura</h2>
          <p>
            Passo 4 da jornada em detalhe. Rode DRY e depois PROBE nas casas escolhidas; a matriz
            mostra o pior resultado por eixo. Sem manipulação de RNG.
          </p>
        </div>
        <div className="actions">
          <select value={mode} onChange={(e) => setMode(e.target.value as 'DRY' | 'PROBE')} disabled={busy}>
            <option value="DRY">DRY</option>
            <option value="PROBE">PROBE</option>
          </select>
          <button className="btn btn-ghost" disabled={busy} onClick={() => load()}>
            Atualizar
          </button>
          <button className="btn btn-primary" type="button" onClick={() => setReportsModal(true)}>
            Ver relatórios
          </button>
          <button className="btn btn-accent" disabled={busy || !selectedHouses.length} onClick={run}>
            {busy ? 'Rodando…' : `Rodar ${mode}`}
          </button>
        </div>
      </div>

      <div className="probe-house-pick">
        <label>Casas do {mode}</label>
        <div className="chip-row">
          {HOUSE_IDS.map((id) => (
            <button
              key={id}
              type="button"
              className={`chip ${selectedHouses.includes(id) ? 'chip--on' : ''}`}
              disabled={busy}
              onClick={() =>
                setSelectedHouses((prev) =>
                  prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
                )
              }
            >
              {HOUSE_LABEL[id]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid-stats">
        <div className="stat stat--low">
          <div className="label">AUTOMATED</div>
          <div className="value">{counts.AUTOMATED ?? 0}</div>
        </div>
        <div className="stat stat--medium">
          <div className="label">SEMI_AUTO</div>
          <div className="value">{counts.SEMI_AUTO ?? 0}</div>
        </div>
        <div className="stat stat--info">
          <div className="label">UNSUPPORTED</div>
          <div className="value">{counts.UNSUPPORTED ?? 0}</div>
        </div>
        <div className="stat stat--high">
          <div className="label">BLOCKED</div>
          <div className="value">{counts.BLOCKED ?? 0}</div>
        </div>
      </div>

      {data?.planner?.next_scenario_id && (
        <div className="journey-callout warn">
          Próximo: <code>{data.planner.next_scenario_id}</code>
          {data.planner.house ? ` · ${HOUSE_LABEL[data.planner.house] || data.planner.house}` : ''}
          {data.planner.rationale ? ` — ${data.planner.rationale}` : ''}
          <span className="muted"> · {data.planner.source || 'planner'}</span>
        </div>
      )}

      <div className="panel integrity-panel">
        <h3>Matriz 3 casas × eixos do cassino</h3>
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
              {houses.map((house) => (
                <tr key={house}>
                  <th scope="row">{HOUSE_LABEL[house] || house}</th>
                  {axes.map((axis) => {
                    const cell = cells[house]?.[axis]
                    const modeVal = cell?.mode || 'SKIPPED'
                    return (
                      <td key={axis}>
                        <button
                          type="button"
                          className={modeClass(modeVal)}
                          title={cell?.title || modeVal}
                          onClick={() => setHouseFilter(house)}
                        >
                          {modeVal.replace('_', ' ')}
                          {cell?.count ? <small>{cell.count}</small> : null}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <CoverageLegend />
        <p className="muted integrity-footnote">
          {data?.coverage?.note ||
            'Cobertura = eixos do produto cassino, não conversão de bônus. Play no provider = SEMI.'}
          {data?.latest_run_id ? ` · run ${data.latest_run_id.slice(0, 8)}` : ''}
          {data?.safety ? ` · cap R$${data.safety.max_lab_stake_brl}` : ''}
        </p>
      </div>

      <div className="panel">
        <div className="panel-head-row">
          <h3>Cenários</h3>
          <select value={houseFilter} onChange={(e) => setHouseFilter(e.target.value)}>
            <option value="all">Todas as casas</option>
            {houses.map((h) => (
              <option key={h} value={h}>
                {HOUSE_LABEL[h] || h}
              </option>
            ))}
          </select>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Eixo</th>
                <th>Casa</th>
                <th>Cenário</th>
                <th>Modo</th>
                <th>Sev</th>
                <th>Nota</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    Sem run ainda — execute PROBE (launch Salsa, sem spin no provider) ou DRY.
                  </td>
                </tr>
              ) : (
                filteredResults.map((row) => (
                  <tr key={row.id}>
                    <td>{AXIS_LABEL[row.axis] || row.axis}</td>
                    <td>{HOUSE_LABEL[row.platform] || row.platform}</td>
                    <td>
                      <code>{row.scenario_id}</code>
                    </td>
                    <td>
                      <span className={modeClass(row.mode)}>{row.mode}</span>
                    </td>
                    <td>
                      <span className={`badge ${row.severity}`}>{row.severity}</span>
                    </td>
                    <td className="muted">{row.vulnerability || row.note}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
      <DualReportsModal open={reportsModal} onClose={() => setReportsModal(false)} />
    </>
  )
}
