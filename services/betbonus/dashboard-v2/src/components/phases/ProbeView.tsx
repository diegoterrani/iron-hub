import { useState } from 'react'
import { api } from '../../services/api'

type ProbeResult = Awaited<ReturnType<typeof api.abuseGamesProbe>>

export default function ProbeView() {
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [limit, setLimit] = useState('20')
  const [includeBonus, setIncludeBonus] = useState(true)
  const [result, setResult] = useState<ProbeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [probing, setProbing] = useState(false)
  const [pStatus, setPStatus] = useState<'idle' | 'executing' | 'done' | 'error'>('idle')

  const handleProbe = async () => {
    setProbing(true)
    setPStatus('executing')
    setError(null)
    setResult(null)
    try {
      const res = await api.abuseGamesProbe({
        platform,
        limit: Number(limit),
        include_bonus_flag: includeBonus,
      })
      setResult(res)
      setPStatus('done')
    } catch (e) {
      setPStatus('error')
      setError(e instanceof Error ? e.message : 'Probe failed')
    } finally {
      setProbing(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Probe status banner */}
      {pStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              pStatus === 'done'
                ? '#00ff8810'
                : pStatus === 'error'
                  ? '#ff3b4d10'
                  : '#ffb30010',
            borderColor:
              pStatus === 'done'
                ? '#00ff8840'
                : pStatus === 'error'
                  ? '#ff3b4d40'
                  : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background:
                pStatus === 'done' ? '#00ff88' : pStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: pStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color:
                pStatus === 'done' ? '#00ff88' : pStatus === 'error' ? '#ff3b4d' : '#ffb300',
            }}
          >
            {pStatus === 'executing'
              ? 'Probing games…'
              : pStatus === 'done'
                ? `Probe complete — ${result?.probed ?? 0} game(s) tested`
                : 'Probe failed'}
          </span>
          {error && (
            <span className="text-[11px] font-mono text-[#ff3b4d] ml-auto truncate max-w-[300px]">
              {error}
            </span>
          )}
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--amber" />
          Game Probe — Contribution
        </div>
        <div className="panel-body space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <span className="label">Platform</span>
              <select className="input w-full" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option value="pagol_bet_br">pagol.bet.br</option>
                <option value="4play_bet_br">4play.bet.br</option>
                <option value="4play">4play.game</option>
              </select>
            </div>
            <div>
              <span className="label">Limit</span>
              <input className="input w-full" value={limit} onChange={(e) => setLimit(e.target.value)} />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={includeBonus} onChange={(e) => setIncludeBonus(e.target.checked)} />
                Include bonus flag
              </label>
            </div>
          </div>
          <button className="btn btn--primary" onClick={handleProbe} disabled={probing}>
            {probing ? 'Probing…' : 'RUN PROBE'}
          </button>
        </div>
      </div>

      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}

      {result && (
        <div className="panel">
          <div className="panel-header">
            <span
              className="status-dot"
              style={{
                background:
                  result.wallet_unchanged === false ? '#00ff88' : '#ffb300',
              }}
            />
            Probe Results
          </div>
          <div className="panel-body space-y-3">
            {/* Key indicators */}
            <div className="grid grid-cols-4 gap-4">
              <div>
                <span className="label">Games Probed</span>
                <span className="text-[14px] font-mono text-[#00e5ff]">
                  {result.probed}
                </span>
              </div>
              <div>
                <span className="label">Discovery Count</span>
                <span className="text-[14px] font-mono text-[#c8d6e5]">
                  {result.discovery_count ?? '—'}
                </span>
              </div>
              <div>
                <span className="label">Term Hits</span>
                <span className="text-[14px] font-mono text-[#c8d6e5]">
                  {result.term_hits ? Object.entries(result.term_hits).map(([k, v]) => `${k}:${v}`).join(' ') : '—'}
                </span>
              </div>
              <div>
                <span className="label">Wallet Unchanged</span>
                <span
                  className="text-[14px] font-mono"
                  style={{ color: result.wallet_unchanged ? '#ffb300' : '#00ff88' }}
                >
                  {result.wallet_unchanged ? 'YES' : 'NO'}
                </span>
              </div>
            </div>

            {/* Wallet delta */}
            {result.wallet_before != null && result.wallet_after != null && (
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <span className="label">Wallet Before</span>
                  <span className="text-[14px] font-mono text-[#c8d6e5]">
                    R${result.wallet_before.balance.toFixed(2)} + {result.wallet_before.bonus.toFixed(2)} bonus
                  </span>
                </div>
                <div>
                  <span className="label">Wallet After</span>
                  <span className="text-[14px] font-mono text-[#c8d6e5]">
                    R${result.wallet_after.balance.toFixed(2)} + {result.wallet_after.bonus.toFixed(2)} bonus
                  </span>
                </div>
                <div>
                  <span className="label">Delta</span>
                  {(() => {
                    const delta = result.wallet_after!.balance - result.wallet_before!.balance
                    return (
                      <span
                        className="text-[14px] font-mono"
                        style={{
                          color: delta > 0 ? '#00ff88' : delta < 0 ? '#ff3b4d' : '#6b7f94',
                        }}
                      >
                        {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                      </span>
                    )
                  })()}
                </div>
              </div>
            )}

            {/* Probe kind */}
            <div className="text-[11px] text-[#6b7f94]">
              <span className="label">Probe Type:</span>{' '}
              <span className="font-mono text-[#00e5ff]">{result.probe_kind}</span>
            </div>

            {/* Note */}
            {result.note && (
              <div className="text-[11px] text-[#6b7f94]">{result.note}</div>
            )}

            {/* Findings */}
            {result.findings && result.findings.length > 0 && (
              <div>
                <span className="label">Findings</span>
                <div className="space-y-1 mt-1">
                  {result.findings.map((f, i) => (
                    <div key={i} className="text-[11px] text-[#c8d6e5] font-mono">
                      • [{f.severity}] {f.title}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Per-probe results */}
            {result.probes && result.probes.length > 0 && (
              <div>
                <span className="label">Per-Game Results</span>
                <div className="mt-2 border border-[#1e2d3d] rounded-[2px] overflow-hidden">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="text-left text-[#6b7f94] border-b border-[#1e2d3d] bg-[#0d141c]">
                        <th className="px-3 py-2">Game</th>
                        <th className="px-3 py-2">Contribution</th>
                        <th className="px-3 py-2">Bonus Used</th>
                        <th className="px-3 py-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.probes.map((p: any, i: number) => (
                        <tr key={i} className="border-b border-[#1e2d3d30]">
                          <td className="px-3 py-2 text-[#c8d6e5] font-mono">
                            {p.game_id || p.game_name || `#${i + 1}`}
                          </td>
                          <td className="px-3 py-2 font-mono text-[#00ff88]">
                            {p.contribution != null ? `${(p.contribution * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td className="px-3 py-2 font-mono">
                            {p.bonus_used != null ? `R$${p.bonus_used}` : '—'}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className="mode-badge"
                              style={{
                                background: p.ok ? '#00ff8818' : '#ff3b4d18',
                                color: p.ok ? '#00ff88' : '#ff3b4d',
                              }}
                            >
                              {p.ok ? 'OK' : 'FAIL'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* What to do next */}
            <div className="border border-[#1e2d3d] rounded-[2px] p-3 mt-2">
              <span className="text-[11px] font-medium text-[#00e5ff]">What to do with this result</span>
              <div className="text-[10px] text-[#6b7f94] mt-1.5 space-y-1">
                {result.wallet_unchanged === false ? (
                  <>
                    <div>
                      • Wallet changed during probing — bonus is converting to real balance.
                      The delta shows the net effect of the probed games.
                    </div>
                    <div>
                      • Games with higher contribution rates are better for clearing wagering
                      requirements faster. Use these in the ARM phase for auto-bet cycling.
                    </div>
                    <div>
                      • Next: go to <span className="text-[#00ff88]">CASHOUT</span> to withdraw
                      the converted balance.
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      • Wallet was unchanged — the probed games did not convert bonus to real
                      balance. This may mean the bonus flag was not applied, the games have
                      0% contribution, or the wagering requirements are not yet met.
                    </div>
                    <div>
                      • Check the per-game results for contribution rates. If all are 0%, try
                      different games or verify the bonus is active.
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Raw JSON */}
            <details>
              <summary className="text-[10px] text-[#4a5c6e] cursor-pointer">Raw JSON</summary>
              <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto mt-2">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}
    </div>
  )
}
