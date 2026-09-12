import { useState } from 'react'
import { api } from '../../services/api'
import type { WithdrawOracleResult } from '../../types'

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

  const statusColor = (s: string) =>
    s === 'withdraw_ok' ? '#00ff88' : s === 'blocked' ? '#ff3b4d' : '#00e5ff'

  // Extract bonus conversion gates from result
  const convGates = result?.gates.filter((g) => g.startsWith('bonus_convert') || g.startsWith('post_conversion')) ?? []
  const converted = convGates.some((g) => g.includes('converted=true'))

  return (
    <div className="space-y-4">
      {/* Cashout status banner */}
      {cStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              cStatus === 'done'
                ? '#00ff8810'
                : cStatus === 'error'
                  ? '#ff3b4d10'
                  : '#ffb30010',
            borderColor:
              cStatus === 'done'
                ? '#00ff8840'
                : cStatus === 'error'
                  ? '#ff3b4d40'
                  : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background:
                cStatus === 'done' ? '#00ff88' : cStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: cStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color:
                cStatus === 'done' ? '#00ff88' : cStatus === 'error' ? '#ff3b4d' : '#ffb300',
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
              <input
                type="checkbox"
                checked={convertBonus}
                onChange={(e) => setConvertBonus(e.target.checked)}
              />
              Convert bonus → balance first
            </label>
            <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
              <input
                type="checkbox"
                checked={confirmRealWithdraw}
                onChange={(e) => setConfirmRealWithdraw(e.target.checked)}
              />
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
            {/* Key indicators */}
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

            {/* Wallet before/after */}
            {result.wallet_before && result.wallet_after && (
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <span className="label">Balance Before</span>
                  <span className="text-[13px] font-mono text-[#c8d6e5]">
                    R${result.wallet_before.balance}
                  </span>
                </div>
                <div>
                  <span className="label">Bonus Before</span>
                  <span className="text-[13px] font-mono text-[#ffb300]">
                    R${result.wallet_before.bonus}
                  </span>
                </div>
                <div>
                  <span className="label">Balance After</span>
                  <span className="text-[13px] font-mono text-[#c8d6e5]">
                    R${result.wallet_after.balance}
                  </span>
                </div>
                <div>
                  <span className="label">Bonus After</span>
                  <span className="text-[13px] font-mono text-[#ffb300]">
                    R${result.wallet_after.bonus}
                  </span>
                </div>
              </div>
            )}

            {/* Bonus conversion section */}
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

            {/* Gates */}
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

            {/* Message */}
            {result.message && (
              <div className="text-[11px] text-[#6b7f94]">{result.message}</div>
            )}

            {/* What to do next */}
            <div className="border border-[#1e2d3d] rounded-[2px] p-3">
              <span className="text-[11px] font-medium text-[#00e5ff]">What to do with this result</span>
              <div className="text-[10px] text-[#6b7f94] mt-1.5 space-y-1">
                {result.status === 'withdraw_ok' ? (
                  <>
                    <div>
                      • Withdrawal succeeded. The real balance has been sent via {result.method}.
                      Check the platform's withdrawal history to confirm the PIX transfer.
                    </div>
                  </>
                ) : converted ? (
                  <>
                    <div>
                      • Bonus was converted to real balance, but the withdrawal was blocked.
                      Check the gates for the specific blocker (min amount, open withdrawal, method).
                    </div>
                    <div>
                      • If below min withdraw, you may need to convert more bonus or use a different
                      game with higher contribution to accumulate enough real balance.
                    </div>
                  </>
                ) : !result.attempted ? (
                  <>
                    <div>
                      • No withdrawal was attempted. Check the gates for blockers.
                      If bonus exists but wasn't converted, the game start may have failed.
                    </div>
                    <div>
                      • Try a different game ID, or verify the bonus is active in the PROBE phase.
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      • Withdrawal was attempted but denied. The code and message above explain
                      why (insufficient balance, method disabled, etc.).
                    </div>
                    <div>
                      • For auto-withdrawal to work, the balance must exceed the minimum and the
                      method must be enabled on the account.
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
