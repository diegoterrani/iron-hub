import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { OpsStatus } from '../../types'
import { HOUSE_LABEL } from '../../lib/casino'

export default function ControlDeck() {
  const [ops, setOps] = useState<OpsStatus | null>(null)
  const [killing, setKilling] = useState(false)

  useEffect(() => {
    api.opsStatus().then(setOps).catch(() => {})
    const id = setInterval(() => api.opsStatus().then(setOps).catch(() => {}), 15000)
    return () => clearInterval(id)
  }, [])

  const safety = ops?.safety
  const killSwitch = safety?.kill_switch ?? {}

  return (
    <div className="shrink-0 border-t border-[#1e2d3d]">
      <div className="panel-header">
        <span className="status-dot" style={{ background: '#ffb300' }} />
        Control Deck
      </div>
      <div className="panel-body space-y-3">
        {safety && (
          <div className="flex items-center justify-between">
            <div>
              <span className="label">Default Mode</span>
              <span className="text-[12px] font-mono text-[#00e5ff]">{safety.default_mode}</span>
            </div>
            <div>
              <span className="label">Max Stake</span>
              <span className="text-[12px] font-mono text-[#c8d6e5]">
                R${safety.max_lab_stake_brl}
              </span>
            </div>
          </div>
        )}

        {Object.keys(killSwitch).length > 0 && (
          <div>
            <span className="label">Kill Switches</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {Object.entries(killSwitch).map(([key, enabled]) => (
                <span
                  key={key}
                  className="mode-badge"
                  style={{
                    background: enabled ? '#ff3b4d18' : '#1e2d3d40',
                    color: enabled ? '#ff3b4d' : '#4a5c6e',
                    border: `1px solid ${enabled ? '#ff3b4d40' : '#1e2d3d'}`,
                  }}
                >
                  {key}
                </span>
              ))}
            </div>
          </div>
        )}

        {ops?.houses && (
          <div>
            <span className="label">Houses</span>
            <div className="space-y-1 mt-1">
              {ops.houses.map((h) => (
                <div key={h.id} className="flex items-center justify-between">
                  <span className="text-[11px] text-[#6b7f94]">{HOUSE_LABEL[h.id] || h.id}</span>
                  <span
                    className="status-dot"
                    style={{
                      background:
                        h.session_ok === false ? '#ff3b4d' : h.has_token ? '#00ff88' : '#374151',
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <button className="btn btn--danger flex-1" disabled={killing} onClick={() => setKilling(true)}>
            KILL ALL
          </button>
          <button className="btn flex-1" onClick={() => api.opsStatus().then(setOps)}>
            REFRESH
          </button>
        </div>
      </div>
    </div>
  )
}
