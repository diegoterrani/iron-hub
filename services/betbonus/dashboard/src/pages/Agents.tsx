import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { Toast } from '../components/Toast'
import { AXIS_LABEL, HOUSE_IDS, HOUSE_LABEL } from '../lib/casino'
import type { IntegrityCatalog } from '../types'

export function Agents() {
  const [catalog, setCatalog] = useState<IntegrityCatalog | null>(null)
  const [houses, setHouses] = useState<string[]>([...HOUSE_IDS])
  const [axis, setAxis] = useState<string>('all')
  const [selected, setSelected] = useState<string[]>([])
  const [mode, setMode] = useState<'DRY' | 'PROBE'>('PROBE')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  useEffect(() => {
    api
      .integrityCatalog()
      .then(setCatalog)
      .catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const scenarios = useMemo(() => {
    const rows = catalog?.scenarios || []
    if (axis === 'all') return rows
    return rows.filter((s) => s.axis === axis)
  }, [catalog, axis])

  const toggle = (id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const toggleHouse = (id: string) => {
    setHouses((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const runSelected = async () => {
    if (!selected.length || !houses.length) return
    setBusy(true)
    try {
      const payload = await api.integrityRun({
        houses,
        scenario_ids: selected,
        run_mode: mode,
        persist: true,
        plan: true,
        require_auth: mode === 'PROBE',
      })
      setToast({ message: `Executados ${payload.results?.length || 0} passos` })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runOne = async (id: string) => {
    setBusy(true)
    try {
      const payload = await api.integrityRun({
        houses,
        scenario_ids: [id],
        run_mode: mode,
        persist: true,
        plan: false,
        require_auth: mode === 'PROBE',
      })
      setToast({ message: `${id}: ${payload.results?.length || 0} casas` })
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
          <h2>Execução pontual</h2>
          <p>
            Depois do PROBE completo na jornada, use esta página para re-rodar um eixo ou um agente.
            Escolha as casas, o modo, e execute.
          </p>
        </div>
        <div className="actions">
          <select value={mode} onChange={(e) => setMode(e.target.value as 'DRY' | 'PROBE')} disabled={busy}>
            <option value="DRY">DRY</option>
            <option value="PROBE">PROBE</option>
          </select>
          <button
            className="btn btn-accent"
            disabled={busy || !selected.length || !houses.length}
            onClick={runSelected}
          >
            {busy ? 'Rodando…' : `Rodar ${selected.length || 0} selecionados`}
          </button>
        </div>
      </div>

      <div className="agent-filters">
        <div className="field">
          <label>Casas</label>
          <div className="chip-row">
            {HOUSE_IDS.map((id) => (
              <button
                key={id}
                type="button"
                className={`chip ${houses.includes(id) ? 'chip--on' : ''}`}
                onClick={() => toggleHouse(id)}
              >
                {HOUSE_LABEL[id]}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Eixo</label>
          <select value={axis} onChange={(e) => setAxis(e.target.value)}>
            <option value="all">Todos</option>
            {(catalog?.axes || []).map((a) => (
              <option key={a} value={a}>
                {AXIS_LABEL[a] || a}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th />
                <th>Eixo</th>
                <th>Agente</th>
                <th>Modo</th>
                <th>Casas</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {scenarios.map((s) => (
                <tr key={s.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.includes(s.id)}
                      onChange={() => toggle(s.id)}
                    />
                  </td>
                  <td>{AXIS_LABEL[s.axis] || s.axis}</td>
                  <td>
                    <code>{s.id}</code>
                    <div className="muted">{s.title}</div>
                  </td>
                  <td>{s.mode}</td>
                  <td className="muted">{s.houses.map((h) => HOUSE_LABEL[h] || h).join(', ')}</td>
                  <td>
                    <button className="btn btn-primary" disabled={busy || !houses.length} onClick={() => runOne(s.id)}>
                      Executar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
