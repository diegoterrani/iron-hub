import { useState } from 'react'
import { api } from '../../services/api'

type ArmResult = Awaited<ReturnType<typeof api.abuseBonusMultiplier>>

export default function ArmView() {
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [promocode, setPromocode] = useState('')
  const [gameId, setGameId] = useState('')
  const [stake, setStake] = useState('1.00')
  const [confirmRedeem, setConfirmRedeem] = useState(false)
  const [confirmRealBet, setConfirmRealBet] = useState(false)
  const [result, setResult] = useState<ArmResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const handleArm = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.abuseBonusMultiplier({
        platform,
        promocode: promocode || undefined,
        game_id: gameId ? Number(gameId) : undefined,
        stake_brl: Number(stake),
        confirm_redeem: confirmRedeem,
        confirm_real_bet: confirmRealBet,
        use_bonus_balance: true,
      })
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Arm failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--amber" />
          Bonus Multiplier — Arm
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
              <span className="label">Promocode</span>
              <input className="input w-full" value={promocode} onChange={(e) => setPromocode(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <span className="label">Game ID</span>
              <input className="input w-full" value={gameId} onChange={(e) => setGameId(e.target.value)} placeholder="optional" />
            </div>
            <div>
              <span className="label">Stake (BRL)</span>
              <input className="input w-full" value={stake} onChange={(e) => setStake(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
              <input
                type="checkbox"
                checked={confirmRedeem}
                onChange={(e) => setConfirmRedeem(e.target.checked)}
              />
              Confirm redeem
            </label>
            <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
              <input
                type="checkbox"
                checked={confirmRealBet}
                onChange={(e) => setConfirmRealBet(e.target.checked)}
              />
              Confirm real bet
            </label>
            <button className="btn btn--primary ml-auto" onClick={handleArm} disabled={running}>
              {running ? 'Arming…' : 'ARM BONUS'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}

      {result && (
        <div className="panel">
          <div className="panel-header">
            <span
              className="status-dot"
              style={{ background: result.ok ? '#00ff88' : '#ff3b4d' }}
            />
            Arm Result
          </div>
          <div className="panel-body space-y-3">
            {/* Key indicators */}
            <div className="grid grid-cols-4 gap-4">
              <div>
                <span className="label">Bet Armed</span>
                <span
                  className="text-[14px] font-mono"
                  style={{ color: result.bet_armed ? '#00ff88' : '#ff3b4d' }}
                >
                  {result.bet_armed ? 'YES' : 'NO'}
                </span>
              </div>
              <div>
                <span className="label">Stake</span>
                <span className="text-[14px] font-mono text-[#00ff88]">
                  R${result.stake_brl}
                </span>
              </div>
              <div>
                <span className="label">Auto-Bet</span>
                <span
                  className="text-[14px] font-mono"
                  style={{ color: result.auto_bet_implemented ? '#00ff88' : '#ffb300' }}
                >
                  {result.auto_bet_implemented ? 'READY' : 'NOT IMPL'}
                </span>
              </div>
              <div>
                <span className="label">Wallet Delta</span>
                <span className="text-[14px] font-mono text-[#c8d6e5]">
                  {result.wallet_start != null && result.wallet_end != null
                    ? `${result.wallet_start} → ${result.wallet_end}`
                    : '—'}
                </span>
              </div>
            </div>

            {/* Gates */}
            {result.gates && result.gates.length > 0 && (
              <div>
                <span className="label">Gates (requirements met to proceed)</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {result.gates.map((g: string) => (
                    <span key={g} className="mode-badge" style={{ background: '#00e5ff18', color: '#00e5ff' }}>
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Auto-bet note */}
            {result.auto_bet_note && (
              <div className="text-[11px] text-[#6b7f94]">
                <span className="text-[#ffb300]">Auto-bet:</span> {result.auto_bet_note}
              </div>
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

            {/* Steps */}
            {result.steps && result.steps.length > 0 && (
              <div>
                <span className="label">Execution Steps</span>
                <div className="space-y-1 mt-1">
                  {result.steps.map((s, i) => (
                    <div key={i} className="text-[11px] text-[#6b7f94] font-mono">
                      {i + 1}. {typeof s === 'string' ? s : JSON.stringify(s)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Poll info */}
            {result.poll && (
              <div className="text-[11px] text-[#4a5c6e]">
                <span className="label">Poll:</span>{' '}
                <span className="font-mono">{JSON.stringify(result.poll)}</span>
              </div>
            )}

            {/* What to do next */}
            <div className="border border-[#1e2d3d] rounded-[2px] p-3 mt-2">
              <span className="text-[11px] font-medium text-[#00e5ff]">What to do with this result</span>
              <div className="text-[10px] text-[#6b7f94] mt-1.5 space-y-1">
                {result.bet_armed ? (
                  <>
                    <div>
                      • The bonus is armed and the bet is placed. The wallet delta shows the balance
                      before/after the bet.
                    </div>
                    <div>
                      • If <span className="font-mono">auto_bet_implemented</span> is true, the
                      system will automatically cycle bets until wagering requirements are met.
                    </div>
                    <div>
                      • Next step: go to <span className="text-[#00ff88]">PROBE</span> to verify
                      contribution rates, then <span className="text-[#00ff88]">CASHOUT</span> to
                      withdraw the converted balance.
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      • The bet was not fully armed. Check the gates above for unmet requirements.
                      You may need to redeem a promocode first, or the platform may require a
                      specific game or stake range.
                    </div>
                    <div>
                      • Adjust parameters and retry, or check the findings for specific blockers.
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
