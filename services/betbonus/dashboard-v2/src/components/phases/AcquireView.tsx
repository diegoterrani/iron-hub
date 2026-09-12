import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { BonusOffer, ConversionSnapshot } from '../../types'

export default function AcquireView() {
  const [offers, setOffers] = useState<BonusOffer[]>([])
  const [snapshot, setSnapshot] = useState<ConversionSnapshot | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .bonuses()
      .then(setOffers)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const checkConversion = async (platform: string) => {
    try {
      const snap = await api.abuseSnapshot(platform)
      setSnapshot(snap)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Conversion check failed')
    }
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading offers…</div>

  const platforms = [...new Set(offers.map((o) => o.platform))]

  return (
    <div className="space-y-4">
      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--green" />
          Acquisition Status
        </div>
        <div className="panel-body">
          <div className="flex gap-3">
            {platforms.map((p) => (
              <button
                key={p}
                className="btn"
                onClick={() => checkConversion(p)}
              >
                Check {p}
              </button>
            ))}
            {platforms.length === 0 && (
              <span className="text-[11px] text-[#4a5c6e] italic">
                No offers to check. Run Discovery first.
              </span>
            )}
          </div>
        </div>
      </div>

      {snapshot && (
        <div className="panel">
          <div className="panel-header">
            <span
              className="status-dot"
              style={{
                background:
                  snapshot.status === 'withdrawable' || snapshot.status === 'withdraw_ok'
                    ? '#00ff88'
                    : snapshot.status === 'blocked'
                      ? '#ff3b4d'
                      : '#00e5ff',
              }}
            />
            Conversion — {snapshot.platform}
          </div>
          <div className="panel-body">
            <div className="grid grid-cols-4 gap-4">
              <div>
                <span className="label">Status</span>
                <span className="text-[14px] font-mono text-[#00e5ff]">
                  {snapshot.status.replace(/_/g, ' ')}
                </span>
              </div>
              <div>
                <span className="label">Balance</span>
                <span className="text-[14px] font-mono text-[#00ff88]">
                  {snapshot.wallet.balance}
                </span>
              </div>
              <div>
                <span className="label">Bonus</span>
                <span className="text-[14px] font-mono text-[#ffb300]">
                  {snapshot.wallet.bonus}
                </span>
              </div>
              <div>
                <span className="label">Rollover</span>
                <span className="text-[14px] font-mono text-[#c8d6e5]">
                  {snapshot.wallet.rollover}
                </span>
              </div>
            </div>
            {snapshot.gates.length > 0 && (
              <div className="mt-3">
                <span className="label">Gates</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {snapshot.gates.map((g) => (
                    <span
                      key={g}
                      className="mode-badge"
                      style={{ background: '#ff3b4d18', color: '#ff3b4d', border: '1px solid #ff3b4d30' }}
                    >
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {snapshot.notes && (
              <div className="mt-2 text-[11px] text-[#6b7f94]">{snapshot.notes}</div>
            )}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--dim" />
          Available Offers ({offers.length})
        </div>
        <div className="panel-body">
          <div className="space-y-2">
            {offers.map((o) => (
              <div
                key={o.id}
                className="flex items-center justify-between border border-[#1e2d3d] rounded-[2px] px-3 py-2 cursor-pointer hover:bg-[#1a2330] transition-colors"
                onClick={() => setSelected(o.id === selected ? null : o.id)}
              >
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-[#c8d6e5] max-w-[300px] truncate">
                    {o.title}
                  </span>
                  <span className="text-[10px] font-mono text-[#00e5ff]">{o.platform}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono text-[#00ff88]">
                    {o.amount} {o.currency}
                  </span>
                  <span className="text-[11px] font-mono text-[#6b7f94]">
                    {o.wagering_multiple}x
                  </span>
                  <span
                    className="mode-badge"
                    style={{
                      background: o.category === 'excellent' ? '#00ff8818' : '#1e2d3d40',
                      color: o.category === 'excellent' ? '#00ff88' : '#6b7f94',
                    }}
                  >
                    {o.score}
                  </span>
                </div>
              </div>
            ))}
            {offers.length === 0 && (
              <div className="text-[11px] text-[#4a5c6e] italic">No offers available</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
