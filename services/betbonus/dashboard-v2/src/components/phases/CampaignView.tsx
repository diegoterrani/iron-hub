import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../services/api'
import type {
  CampaignAccountStatus,
  CampaignConfigRequest,
  CampaignReport,
  CampaignStage,
  CampaignStatusResponse,
} from '../../types'
import { HOUSE_IDS, HOUSE_LABEL } from '../../lib/casino'

const STAGE_COLORS: Record<CampaignStage, string> = {
  pending: '#4a5c6e',
  registered: '#00e5ff',
  bonus_claimed: '#00e5ff',
  wagering: '#ffb300',
  wagered: '#00ff88',
  withdrawn: '#00ff88',
  failed: '#ff3b4d',
}

const STAGE_LABELS: Record<CampaignStage, string> = {
  pending: 'PENDING',
  registered: 'REGISTERED',
  bonus_claimed: 'BONUS CLAIMED',
  wagering: 'WAGERING',
  wagered: 'WAGERED',
  withdrawn: 'WITHDRAWN',
  failed: 'FAILED',
}

const DEFAULT_CONFIG: CampaignConfigRequest = {
  accounts: 10,
  platforms: ['pagol_bet_br'],
  stagger_minutes: 10,
  max_parallel: 4,
  retry_failed: true,
  max_retries: 2,
  wager_method: 'api',
  withdraw_split: true,
  dry_run: true,
}

function ReportRow({ acc }: { acc: CampaignAccountStatus }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr
        className="border-b border-[#1e2d3d40] cursor-pointer hover:bg-[#1a233060] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-1.5 pr-1 text-[#4a5c6e]">
          <span className="inline-block transition-transform duration-200" style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>▸</span>
        </td>
        <td className="py-1.5 pr-3 text-[#c8d6e5] font-mono">{acc.identity_name}</td>
        <td className="py-1.5 pr-3 text-[#00e5ff] font-mono">{acc.identity_email || '—'}</td>
        <td className="py-1.5 pr-3 text-[#6b7f94]">{acc.platform}</td>
        <td className="py-1.5 pr-3">
          <span className="px-1.5 py-0.5 text-[10px] font-mono border rounded-[2px]" style={{ color: STAGE_COLORS[acc.stage], borderColor: `${STAGE_COLORS[acc.stage]}40` }}>
            {STAGE_LABELS[acc.stage] || acc.stage}
          </span>
        </td>
        <td className="py-1.5 pr-3 text-right font-mono text-[#c8d6e5]">${acc.balance.toFixed(2)}</td>
        <td className="py-1.5 pr-3 text-right font-mono text-[#00e5ff]">${acc.bonus.toFixed(2)}</td>
        <td className="py-1.5 pr-3 text-right font-mono text-[#00ff88]">${acc.withdrawn.toFixed(2)}</td>
        <td className="py-1.5 text-[#ff3b4d] font-mono max-w-[200px] truncate" title={acc.error}>{acc.error || '—'}</td>
      </tr>
      {expanded && (
        <tr className="border-b border-[#1e2d3d40] bg-[#0d141c]">
          <td colSpan={9} className="px-4 py-3">
            <div className="grid grid-cols-4 gap-x-6 gap-y-1.5">
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Name</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{acc.identity_name || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Email</span>
                <span className="text-[11px] text-[#00e5ff] font-mono">{acc.identity_email || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Document (CPF)</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{acc.identity_cpf || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Password</span>
                <span className="text-[11px] text-[#ffb300] font-mono">{acc.identity_password || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Phone</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{acc.identity_phone || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Birth Date</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{acc.identity_birth_date || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">Address</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{acc.identity_address || '—'}</span>
              </div>
              <div>
                <span className="text-[10px] text-[#4a5c6e] uppercase block">City / State</span>
                <span className="text-[11px] text-[#c8d6e5] font-mono">{[acc.identity_city, acc.identity_state].filter(Boolean).join(' / ') || '—'}</span>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export default function CampaignView() {
  const [config, setConfig] = useState<CampaignConfigRequest>(DEFAULT_CONFIG)
  const [starting, setStarting] = useState(false)
  const [campaignId, setCampaignId] = useState<string | null>(null)
  const [status, setStatus] = useState<CampaignStatusResponse | null>(null)
  const [report, setReport] = useState<CampaignReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [canceling, setCanceling] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isRunning = status?.status === 'running' || status?.status === 'pending'
  const isFinished = status?.status === 'completed' || status?.status === 'failed' || status?.status === 'cancelled' || status?.status === 'error'

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (id: string) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const s = await api.getCampaignStatus(id)
          setStatus(s)
          if (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled' || s.status === 'error') {
            stopPolling()
            try {
              const r = await api.getCampaignReport(id)
              setReport(r.report)
            } catch { /* non-fatal */ }
          }
        } catch { /* transient */ }
      }, 3000)
    },
    [stopPolling],
  )

  useEffect(() => () => stopPolling(), [stopPolling])

  const handleStart = async () => {
    setStarting(true)
    setError(null)
    setReport(null)
    setStatus(null)
    try {
      const res = await api.runCampaign(config)
      setCampaignId(res.campaign_id)
      setStatus({
        ok: true,
        campaign_id: res.campaign_id,
        status: 'pending',
        progress: { total: config.accounts, completed: 0, failed: 0, in_progress: 0, pct: 0, stages: {}, total_extracted: 0, net_profit: 0, duration_s: 0 },
        started_at: null,
        finished_at: null,
        error: null,
      })
      startPolling(res.campaign_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start campaign')
    } finally {
      setStarting(false)
    }
  }

  const handleCancel = async () => {
    if (!campaignId) return
    setCanceling(true)
    try {
      await api.cancelCampaign(campaignId)
      const s = await api.getCampaignStatus(campaignId)
      setStatus(s)
      stopPolling()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to cancel campaign')
    } finally {
      setCanceling(false)
    }
  }

  const set = <K extends keyof CampaignConfigRequest>(key: K, val: CampaignConfigRequest[K]) =>
    setConfig((prev) => ({ ...prev, [key]: val }))

  const togglePlatform = (platform: string) => {
    setConfig((prev) => {
      const has = prev.platforms.includes(platform)
      return {
        ...prev,
        platforms: has ? prev.platforms.filter((p) => p !== platform) : [...prev.platforms, platform],
      }
    })
  }

  return (
    <div className="space-y-4">
      {status && isRunning && (
        <div className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]" style={{ background: '#00e5ff10', borderColor: '#00e5ff40' }}>
          <span className="w-2 h-2 rounded-full shrink-0 animate-pulse" style={{ background: '#00e5ff', boxShadow: '0 0 6px #00e5ff80' }} />
          <span className="text-[12px] font-medium text-[#00e5ff]">Campaign {status.campaign_id} — {status.status}</span>
          <span className="text-[11px] font-mono text-[#6b7f94] ml-auto">{status.progress.pct}%</span>
        </div>
      )}
      {status && isFinished && (
        <div className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]" style={{
          background: status.status === 'completed' ? '#00ff8810' : status.status === 'cancelled' ? '#ffb30010' : '#ff3b4d10',
          borderColor: status.status === 'completed' ? '#00ff8840' : status.status === 'cancelled' ? '#ffb30040' : '#ff3b4d40',
        }}>
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: status.status === 'completed' ? '#00ff88' : status.status === 'cancelled' ? '#ffb300' : '#ff3b4d' }} />
          <span className="text-[12px] font-medium" style={{ color: status.status === 'completed' ? '#00ff88' : status.status === 'cancelled' ? '#ffb300' : '#ff3b4d' }}>
            Campaign {status.campaign_id} — {status.status}
          </span>
          {status.error && <span className="text-[11px] font-mono text-[#ff3b4d] ml-auto truncate max-w-[300px]">{status.error}</span>}
        </div>
      )}
      {status && status.status === 'error' && status.error && (
        <div className="px-4 py-3 border rounded-[2px] text-[11px] font-mono text-[#ff3b4d] bg-[#ff3b4d08] border-[#ff3b4d30] whitespace-pre-wrap">{status.error}</div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot" style={{ background: isRunning ? '#ffb300' : '#00ff88' }} />
          Campaign Configuration
        </div>
        <div className="panel-body space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <div>
              <span className="label">Accounts</span>
              <input className="input w-full mt-1" type="number" min={1} max={100} value={config.accounts} onChange={(e) => set('accounts', Number(e.target.value))} disabled={isRunning} />
            </div>
            <div>
              <span className="label">Stagger (min)</span>
              <input className="input w-full mt-1" type="number" min={0} value={config.stagger_minutes} onChange={(e) => set('stagger_minutes', Number(e.target.value))} disabled={isRunning} />
            </div>
            <div>
              <span className="label">Max Parallel</span>
              <input className="input w-full mt-1" type="number" min={1} max={16} value={config.max_parallel} onChange={(e) => set('max_parallel', Number(e.target.value))} disabled={isRunning} />
            </div>
            <div>
              <span className="label">Max Retries</span>
              <input className="input w-full mt-1" type="number" min={0} max={5} value={config.max_retries ?? 2} onChange={(e) => set('max_retries', Number(e.target.value))} disabled={isRunning} />
            </div>
          </div>

          <div>
            <span className="label">Platforms</span>
            <div className="flex gap-2 mt-1.5">
              {HOUSE_IDS.map((id) => (
                <button key={id} onClick={() => togglePlatform(id)} disabled={isRunning}
                  className={`px-3 py-1.5 text-[11px] font-medium border rounded-[2px] transition-colors ${
                    config.platforms.includes(id)
                      ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff10]'
                      : 'border-[#1e2d3d] text-[#6b7f94] hover:border-[#3a4f64] hover:text-[#c8d6e5]'
                  }`}>
                  {HOUSE_LABEL[id] || id}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <span className="label">Wager Method</span>
              <select className="input w-full mt-1" value={config.wager_method} onChange={(e) => set('wager_method', e.target.value)} disabled={isRunning}>
                <option value="api">API</option>
                <option value="ws">WebSocket</option>
                <option value="browser">Browser</option>
              </select>
            </div>
            <div className="flex items-end gap-4">
              <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={config.retry_failed} onChange={(e) => set('retry_failed', e.target.checked)} disabled={isRunning} />
                Retry Failed
              </label>
              <label className="flex items-center gap-2 text-[11px] text-[#6b7f94]">
                <input type="checkbox" checked={config.withdraw_split} onChange={(e) => set('withdraw_split', e.target.checked)} disabled={isRunning} />
                Split Withdraw
              </label>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-[11px] text-[#ffb300]">
                <input type="checkbox" checked={config.dry_run} onChange={(e) => set('dry_run', e.target.checked)} disabled={isRunning} />
                Dry Run
              </label>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button className="btn btn--primary" onClick={handleStart} disabled={starting || isRunning || config.platforms.length === 0}>
              {starting ? 'Starting…' : isRunning ? 'RUNNING' : '▶ LAUNCH CAMPAIGN'}
            </button>
            {isRunning && (
              <button className="btn btn--danger" onClick={handleCancel} disabled={canceling}>
                {canceling ? 'Cancelling…' : '■ CANCEL'}
              </button>
            )}
            {campaignId && !isRunning && <span className="text-[11px] font-mono text-[#4a5c6e]">{campaignId}</span>}
          </div>
          {error && <div className="text-[11px] text-[#ff3b4d] font-mono">{error}</div>}
        </div>
      </div>

      {status && status.progress && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot" style={{ background: isRunning ? '#ffb300' : status.status === 'completed' ? '#00ff88' : '#ff3b4d' }} />
            Campaign Progress
          </div>
          <div className="panel-body space-y-3">
            <div className="h-2 bg-[#1e2d3d] rounded-sm overflow-hidden">
              <div className="h-full transition-all duration-500" style={{ width: `${status.progress.pct}%`, background: isRunning ? '#00e5ff' : status.status === 'completed' ? '#00ff88' : '#ff3b4d' }} />
            </div>

            <div className="grid grid-cols-4 gap-3 text-center">
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[18px] font-bold text-[#00ff88]">{status.progress.completed}</div>
                <div className="text-[10px] text-[#4a5c6e] uppercase">Completed</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[18px] font-bold text-[#ff3b4d]">{status.progress.failed}</div>
                <div className="text-[10px] text-[#4a5c6e] uppercase">Failed</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[18px] font-bold text-[#00e5ff]">{status.progress.in_progress}</div>
                <div className="text-[10px] text-[#4a5c6e] uppercase">In Progress</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[18px] font-bold text-[#c8d6e5]">{status.progress.total}</div>
                <div className="text-[10px] text-[#4a5c6e] uppercase">Total</div>
              </div>
            </div>

            {status.progress.stages && Object.keys(status.progress.stages).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {(Object.entries(status.progress.stages) as [CampaignStage, number][]).map(([stage, count]) => (
                  <span key={stage} className="px-2 py-0.5 text-[10px] font-mono border rounded-[2px]" style={{ color: STAGE_COLORS[stage] || '#4a5c6e', borderColor: `${STAGE_COLORS[stage] || '#4a5c6e'}40` }}>
                    {STAGE_LABELS[stage] || stage}: {count}
                  </span>
                ))}
              </div>
            )}

            <div className="grid grid-cols-3 gap-3">
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Extracted</div>
                <div className="text-[14px] font-bold text-[#00ff88]">${status.progress.total_extracted.toFixed(2)}</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Net Profit</div>
                <div className="text-[14px] font-bold" style={{ color: status.progress.net_profit >= 0 ? '#00ff88' : '#ff3b4d' }}>
                  {status.progress.net_profit >= 0 ? '+' : ''}${status.progress.net_profit.toFixed(2)}
                </div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Duration</div>
                <div className="text-[14px] font-bold text-[#c8d6e5]">{Math.floor(status.progress.duration_s / 60)}m {Math.round(status.progress.duration_s % 60)}s</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {report && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot" style={{ background: report.net_profit >= 0 ? '#00ff88' : '#ff3b4d' }} />
            Campaign Report
          </div>
          <div className="panel-body space-y-3">
            <div className="grid grid-cols-5 gap-3">
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Extracted</div>
                <div className="text-[14px] font-bold text-[#00ff88]">${report.total_extracted.toFixed(2)}</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Cost</div>
                <div className="text-[14px] font-bold text-[#ffb300]">${report.total_cost.toFixed(2)}</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Net Profit</div>
                <div className="text-[14px] font-bold" style={{ color: report.net_profit >= 0 ? '#00ff88' : '#ff3b4d' }}>
                  {report.net_profit >= 0 ? '+' : ''}${report.net_profit.toFixed(2)}
                </div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Success Rate</div>
                <div className="text-[14px] font-bold text-[#c8d6e5]">{(report.success_rate * 100).toFixed(1)}%</div>
              </div>
              <div className="p-2 bg-[#0d141c] border border-[#1e2d3d] rounded-[2px]">
                <div className="text-[10px] text-[#4a5c6e] uppercase">Duration</div>
                <div className="text-[14px] font-bold text-[#c8d6e5]">{Math.floor(report.duration_s / 60)}m {Math.round(report.duration_s % 60)}s</div>
              </div>
            </div>

            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-[#1e2d3d]">
                  <th className="text-left py-1.5 pr-1 text-[#4a5c6e] font-medium w-4"></th>
                  <th className="text-left py-1.5 pr-3 text-[#4a5c6e] font-medium">Identity</th>
                  <th className="text-left py-1.5 pr-3 text-[#4a5c6e] font-medium">Email</th>
                  <th className="text-left py-1.5 pr-3 text-[#4a5c6e] font-medium">Platform</th>
                  <th className="text-left py-1.5 pr-3 text-[#4a5c6e] font-medium">Stage</th>
                  <th className="text-right py-1.5 pr-3 text-[#4a5c6e] font-medium">Balance</th>
                  <th className="text-right py-1.5 pr-3 text-[#4a5c6e] font-medium">Bonus</th>
                  <th className="text-right py-1.5 pr-3 text-[#4a5c6e] font-medium">Withdrawn</th>
                  <th className="text-left py-1.5 text-[#4a5c6e] font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {report.accounts.map((acc) => (
                  <ReportRow key={acc.account_id} acc={acc} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
