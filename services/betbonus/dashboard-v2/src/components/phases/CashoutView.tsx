import { useState } from 'react'
import { api } from '../../services/api'
import type { WithdrawOracleResult } from '../../types'

interface AJStep {
  id: string
  title: string
  ok: boolean
  mode: string
  detail: string
  evidence?: Record<string, unknown>
}

interface AJDiagnosis {
  category?: string
  severity?: string
  summary?: string
  details?: string
  [key: string]: unknown
}

interface AJRemediation {
  summary?: string
  actions?: string[]
  [key: string]: unknown
}

interface AJResult {
  run_id: string
  session_id?: string
  platform: string
  automation_goal_met: boolean
  stuck_point: string | null
  steps: AJStep[]
  diagnosis: AJDiagnosis | null
  remediation: AJRemediation | null
  withdraw_result?: Record<string, unknown>
  report_filename?: string
  report_markdown?: string
  [key: string]: unknown
}

export default function CashoutView() {
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [amount, setAmount] = useState('100')
  const [method, setMethod] = useState<'pix' | 'tft' | 'dtr' | 'preflight'>('pix')
  const [confirmRealWithdraw, setConfirmRealWithdraw] = useState(false)
  const [convertBonus, setConvertBonus] = useState(true)
  const [gameId, setGameId] = useState('')
  const [result, setResult] = useState<WithdrawOracleResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [cStatus, setCStatus] = useState<'idle' | 'executing' | 'done' | 'error'>('idle')

  const [ajPlatform, setAjPlatform] = useState('4play')
  const [ajConfirmWithdraw, setAjConfirmWithdraw] = useState(true)
  const [ajConfirmBet, setAjConfirmBet] = useState(true)
  const [ajSprint, setAjSprint] = useState(true)
  const [ajExhaust, setAjExhaust] = useState(false)
  const [ajSettle, setAjSettle] = useState(true)
  const [ajRunning, setAjRunning] = useState(false)
  const [ajResult, setAjResult] = useState<AJResult | null>(null)
  const [ajError, setAjError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const [showLogs, setShowLogs] = useState(false)
  const [logs, setLogs] = useState<string[]>([])

  const handleCashout = async () => {
    setRunning(true)
    setCStatus('executing')
    setError(null)
    setResult(null)
    try {
      const res = await api.abuseWithdraw({
        platform,
        amount: Number(amount),
        method,
        confirm_real_withdraw: confirmRealWithdraw,
        convert_bonus: convertBonus,
        game_id: gameId ? Number(gameId) : undefined,
      })
      setResult(res)
      setCStatus(res.ok || res.attempted ? 'done' : 'error')
    } catch (e) {
      setCStatus('error')
      setError(e instanceof Error ? e.message : 'Cashout failed')
    } finally {
      setRunning(false)
    }
  }

  const fetchLogs = async (sessionId: string) => {
    try {
      const session = await api.getJourneySession(sessionId)
      const lines = session.events
        .map((ev) => {
          const ts = new Date(ev.created_at).toLocaleTimeString()
          const lvl = ev.level.toUpperCase().padEnd(5)
          return `[${ts}] ${lvl} [${ev.step || '-'}] ${ev.message}`
        })
        .reverse()
      setLogs(lines)
    } catch (e) {
      setLogs([`Failed to load logs: ${e instanceof Error ? e.message : 'unknown error'}`])
    }
  }

  const handleAutoJourney = async () => {
    setAjRunning(true)
    setAjError(null)
    setAjResult(null)
    setShowReport(false)
    setShowLogs(false)
    try {
      const res = await api.abuseAutoJourney({
        platform: ajPlatform,
        confirm_real_withdraw: ajConfirmWithdraw,
        confirm_real_bet: ajConfirmBet,
        sprint_mode: ajSprint,
        exhaust_mode: ajExhaust,
        settle_withdraw: ajSettle,
      })
      const aj = res as unknown as AJResult
      setAjResult(aj)
      if (aj.session_id) {
        fetchLogs(aj.session_id)
      }
    } catch (e) {
      setAjError(e instanceof Error ? e.message : 'Auto-journey failed')
    } finally {
      setAjRunning(false)
    }
  }

  const statusColor = (s: string) =>
    s === 'withdraw_ok' ? '#00ff88' : s === 'blocked' ? '#ff3b4d' : '#00e5ff'

  const convGates = result?.gates.filter(
    (g) => g.startsWith('bonus_convert') || g.startsWith('post_conversion'),
  ) ?? []
  const converted = convGates.some((g) => g.includes('converted=true'))
  const stepDot = (ok: boolean) => (ok ? '#00ff88' : '#ff3b4d')

  return (
    <div className="space-y-4">
      {cStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              cStatus === 'done' ? '#00ff8810' : cStatus === 'error' ? '#ff3b4d10' : '#ffb30010',
            borderColor:
              cStatus === 'done' ? '#00ff8840' : cStatus === 'error' ? '#ff3b4d40' : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background: cStatus === 'done' ? '#00ff88' : cStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: cStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color: cStatus === 'done' ? '#00ff88' : cStatus === 'error' ? '#ff3b4d' : '#ffb300',
            }}
          >
            {cStatus === 'executing'
              ? 'Executing cashout…'
              : cStatus === 'done'
                ? `Cashout complete — ${result?.status?.replace(/_/g, ' ') ?? ''}`
                : 'Cashout failed'}
          </span>
          {error && (
            <span className="text-[11px] font-mono text-[#ff3b4d] ml-auto truncate max-w-[300px]">
              {error}
            </span>
          )}
        </div>
      )}
      {/* Auto-Journey panel */}
      <div className="panel" style={{ borderColor: '#00e5ff30' }}>
        <div className="panel-header" style={{ borderBottom: '1px solid #00e5ff20' }}>
          <span className="status-dot" style={{ background: ajRunning ? '#ffb300' : '#00e5ff' }} />
          Auto-Journey — Full Pipeline (Recon → Cashout)
        </div>
        <div className="panel-body space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="label">Platform</span>
              <select className="input w-full" value={ajPlatform} onChange={(e) => setAjPlatform(e.target.value)}>
                <option value="4play">4play.game</option>
                <option value="4play_bet_br">4play.bet.br</option>
                <option value="pagol_bet_br">pagol.bet.br</option>
              </select>
            </div>
            <div className="flex items-end gap-3 flex-wrap">
              <label className="flex items-center gap-1.5 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={ajConfirmWithdraw} onChange={(e) => setAjConfirmWithdraw(e.target.checked)} />
                Real withdraw
              </label>
              <label className="flex items-center gap-1.5 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={ajConfirmBet} onChange={(e) => setAjConfirmBet(e.target.checked)} />
                Real bet
              </label>
              <label className="flex items-center gap-1.5 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={ajSprint} onChange={(e) => setAjSprint(e.target.checked)} />
                Sprint
              </label>
              <label className="flex items-center gap-1.5 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={ajExhaust} onChange={(e) => setAjExhaust(e.target.checked)} />
                Exhaust
              </label>
              <label className="flex items-center gap-1.5 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={ajSettle} onChange={(e) => setAjSettle(e.target.checked)} />
                Settle
              </label>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn btn--success" onClick={handleAutoJourney} disabled={ajRunning}>
              {ajRunning ? 'Running pipeline…' : 'EXECUTE AUTO-JOURNEY'}
            </button>
            <span className="text-[10px] text-[#4a5c6e]">
              Recon → Auth → Acquire → Arm → Probe → Wagering Check → Cashout → Report
            </span>
          </div>

          {ajError && <div className="text-[#ff3b4d] text-[12px] font-mono">{ajError}</div>}

          {ajResult && (
            <div className="border border-[#1e2d3d] rounded-[2px] p-3 space-y-3">
              <div
                className="flex items-center gap-3 px-3 py-2 border rounded-[2px]"
                style={{
                  background: ajResult.automation_goal_met ? '#00ff8810' : '#ff3b4d10',
                  borderColor: ajResult.automation_goal_met ? '#00ff8840' : '#ff3b4d40',
                }}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{
                    background: ajResult.automation_goal_met ? '#00ff88' : '#ff3b4d',
                    boxShadow: `0 0 8px ${ajResult.automation_goal_met ? '#00ff8860' : '#ff3b4d60'}`,
                  }}
                />
                <span
                  className="text-[13px] font-semibold"
                  style={{ color: ajResult.automation_goal_met ? '#00ff88' : '#ff3b4d' }}
                >
                  {ajResult.automation_goal_met ? 'PIPELINE COMPLETE' : 'PIPELINE BLOCKED'}
                </span>
                {ajResult.stuck_point && (
                  <span className="text-[11px] font-mono text-[#ffb300]">
                    stuck: {ajResult.stuck_point}
                  </span>
                )}
                <span className="text-[10px] text-[#4a5c6e] ml-auto font-mono">
                  {ajResult.run_id}
                </span>
              </div>

              <div>
                <span className="label">Pipeline Stages</span>
                <div className="mt-2 space-y-1.5">
                  {ajResult.steps.map((s, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 text-[12px] px-2 py-1.5 rounded-[2px]"
                      style={{
                        background: s.ok ? '#00ff8808' : '#ff3b4d08',
                        border: `1px solid ${s.ok ? '#00ff8818' : '#ff3b4d18'}`,
                      }}
                    >
                      <span
                        className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                        style={{ background: stepDot(s.ok), boxShadow: `0 0 4px ${stepDot(s.ok)}60` }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[#c8d6e5]">{s.id}</span>
                          <span className="text-[10px] text-[#4a5c6e]">{s.title}</span>
                          <span className="text-[10px] font-mono ml-auto" style={{ color: stepDot(s.ok) }}>
                            {s.ok ? 'PASS' : 'FAIL'}
                          </span>
                        </div>
                        {s.detail && (
                          <div className="text-[10px] text-[#6b7f94] mt-0.5 truncate" title={s.detail}>
                            {s.detail}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {ajResult.diagnosis && (
                <div className="border border-[#1e2d3d] rounded-[2px] p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-medium text-[#ffb300]">DIAGNOSIS</span>
                    {ajResult.diagnosis.category && (
                      <span className="mode-badge" style={{ background: '#ffb30018', color: '#ffb300' }}>
                        {ajResult.diagnosis.category}
                      </span>
                    )}
                    {ajResult.diagnosis.severity && (
                      <span
                        className="mode-badge"
                        style={{
                          background: ajResult.diagnosis.severity === 'critical' ? '#ff3b4d18' : '#00e5ff18',
                          color: ajResult.diagnosis.severity === 'critical' ? '#ff3b4d' : '#00e5ff',
                        }}
                      >
                        {ajResult.diagnosis.severity}
                      </span>
                    )}
                  </div>
                  {ajResult.diagnosis.summary && (
                    <div className="text-[11px] text-[#c8d6e5] mt-2">{ajResult.diagnosis.summary}</div>
                  )}
                  {ajResult.diagnosis.details && (
                    <div className="text-[10px] text-[#6b7f94] mt-1.5 whitespace-pre-wrap">
                      {ajResult.diagnosis.details}
                    </div>
                  )}
                </div>
              )}

              {ajResult.remediation && (
                <div className="border border-[#1e2d3d] rounded-[2px] p-3">
                  <span className="text-[11px] font-medium text-[#00e5ff]">REMEDIATION</span>
                  {ajResult.remediation.summary && (
                    <div className="text-[11px] text-[#c8d6e5] mt-1.5">{ajResult.remediation.summary}</div>
                  )}
                  {ajResult.remediation.actions && ajResult.remediation.actions.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {ajResult.remediation.actions.map((a, i) => (
                        <li key={i} className="text-[10px] text-[#6b7f94] flex items-start gap-1.5">
                          <span className="text-[#00e5ff] mt-px">→</span>
                          {a}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div className="flex items-center gap-2 pt-1">
                <button className="btn btn--primary" onClick={() => setShowReport(true)}>
                  VIEW REPORT
                </button>
                <button className="btn" onClick={() => setShowLogs(true)}>
                  VIEW LOGS
                </button>
                <details className="ml-auto">
                  <summary className="text-[10px] text-[#4a5c6e] cursor-pointer">Raw JSON</summary>
                  <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto mt-2">
                    {JSON.stringify(ajResult, null, 2)}
                  </pre>
                </details>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--green" />
          Cashout — Withdraw Oracle
        </div>
        <div className="panel-body space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <div>
              <span className="label">Platform</span>
              <select className="input w-full" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option value="pagol_bet_br">pagol.bet.br</option>
                <option value="4play_bet_br">4play.bet.br</option>
                <option value="4play">4play.game</option>
              </select>
            </div>
            <div>
              <span className="label">Amount (BRL)</span>
              <input className="input w-full" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div>
              <span className="label">Method</span>
              <select className="input w-full" value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
                <option value="pix">PIX</option>
                <option value="tft">TFT</option>
                <option value="dtr">DTR</option>
                <option value="preflight">Preflight Only</option>
              </select>
            </div>
            <div>
              <span className="label">Game ID (for conversion)</span>
              <input className="input w-full" value={gameId} onChange={(e) => setGameId(e.target.value)} placeholder="auto" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
              <input type="checkbox" checked={convertBonus} onChange={(e) => setConvertBonus(e.target.checked)} />
              Convert bonus → balance first
            </label>
            <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
              <input type="checkbox" checked={confirmRealWithdraw} onChange={(e) => setConfirmRealWithdraw(e.target.checked)} />
              Confirm real withdraw
            </label>
            <button className="btn btn--success ml-auto" onClick={handleCashout} disabled={running}>
              {running ? 'Cashing out…' : 'EXECUTE CASHOUT'}
            </button>
          </div>
          <div className="text-[10px] text-[#4a5c6e]">
            When bonus balance exists with no real balance, the system starts a game with
            useBonusBalance to convert bonus → real balance, then attempts the withdrawal.
          </div>
        </div>
      </div>

      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}

      {result && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot" style={{ background: statusColor(result.status) }} />
            Withdraw Oracle Result
          </div>
          <div className="panel-body space-y-3">
            <div className="grid grid-cols-4 gap-4">
              <div>
                <span className="label">Status</span>
                <span className="text-[14px] font-mono" style={{ color: statusColor(result.status) }}>
                  {result.status.replace(/_/g, ' ')}
                </span>
              </div>
              <div>
                <span className="label">Amount</span>
                <span className="text-[14px] font-mono text-[#00ff88]">
                  R${result.amount} {result.currency}
                </span>
              </div>
              <div>
                <span className="label">Method</span>
                <span className="text-[14px] font-mono text-[#c8d6e5]">{result.method}</span>
              </div>
              <div>
                <span className="label">Attempted</span>
                <span className="text-[14px] font-mono" style={{ color: result.attempted ? '#00ff88' : '#6b7f94' }}>
                  {result.attempted ? 'YES' : 'PREFLIGHT'}
                </span>
              </div>
            </div>
            {result.wallet_before && result.wallet_after && (
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <span className="label">Balance Before</span>
                  <span className="text-[13px] font-mono text-[#c8d6e5]">R${result.wallet_before.balance}</span>
                </div>
                <div>
                  <span className="label">Bonus Before</span>
                  <span className="text-[13px] font-mono text-[#ffb300]">R${result.wallet_before.bonus}</span>
                </div>
                <div>
                  <span className="label">Balance After</span>
                  <span className="text-[13px] font-mono text-[#c8d6e5]">R${result.wallet_after.balance}</span>
                </div>
                <div>
                  <span className="label">Bonus After</span>
                  <span className="text-[13px] font-mono text-[#ffb300]">R${result.wallet_after.bonus}</span>
                </div>
              </div>
            )}
            {convGates.length > 0 && (
              <div className="border border-[#1e2d3d] rounded-[2px] p-3">
                <span className="text-[11px] font-medium" style={{ color: converted ? '#00ff88' : '#ffb300' }}>
                  Bonus Conversion {converted ? '✓' : '—'}
                </span>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {convGates.map((g) => (
                    <span
                      key={g}
                      className="mode-badge"
                      style={{
                        background: g.includes('converted=true') ? '#00ff8818' : '#ffb30018',
                        color: g.includes('converted=true') ? '#00ff88' : '#ffb300',
                      }}
                    >
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {result.gates.length > 0 && (
              <div>
                <span className="label">Gates</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {result.gates.filter((g) => !g.startsWith('bonus_convert') && !g.startsWith('post_conversion')).map((g) => (
                    <span key={g} className="mode-badge" style={{ background: '#ff3b4d18', color: '#ff3b4d' }}>
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {result.message && <div className="text-[11px] text-[#6b7f94]">{result.message}</div>}
            <details>
              <summary className="text-[10px] text-[#4a5c6e] cursor-pointer">Raw JSON</summary>
              <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto mt-2">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}
      {/* Report Modal */}
      {showReport && ajResult && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: '#000000cc' }}
          onClick={() => setShowReport(false)}
        >
          <div
            className="panel w-full max-w-3xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-header flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="status-dot" style={{ background: '#00e5ff' }} />
                Journey Report — {ajResult.platform}
              </span>
              <button className="text-[#6b7f94] hover:text-white text-[16px] leading-none" onClick={() => setShowReport(false)}>
                ✕
              </button>
            </div>
            <div className="panel-body overflow-y-auto">
              {ajResult.report_markdown ? (
                <pre className="text-[12px] font-mono text-[#c8d6e5] whitespace-pre-wrap leading-relaxed">
                  {ajResult.report_markdown}
                </pre>
              ) : (
                <div className="text-[12px] text-[#6b7f94]">
                  No report generated for this run.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {showLogs && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: '#000000cc' }}
          onClick={() => setShowLogs(false)}
        >
          <div
            className="panel w-full max-w-3xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-header flex items-center justify-between">
              <span className="flex items-center gap-2">
                <span className="status-dot" style={{ background: '#ffb300' }} />
                Run Logs{ajResult ? ` — ${ajResult.run_id}` : ''}
              </span>
              <button className="text-[#6b7f94] hover:text-white text-[16px] leading-none" onClick={() => setShowLogs(false)}>
                ✕
              </button>
            </div>
            <div className="panel-body overflow-y-auto">
              <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap leading-relaxed">
                {logs.length > 0 ? logs.join('\n') : 'No logs available.'}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
