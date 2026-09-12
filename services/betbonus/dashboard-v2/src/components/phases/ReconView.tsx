import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { PlatformInfo, Stats } from '../../types'
import { HOUSE_LABEL } from '../../lib/casino'

interface JourneyPreset {
  id: string
  name: string
  url: string
  platform: string
  auth: string
  notes: string
}

export default function ReconView() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Journey state
  const [presets, setPresets] = useState<JourneyPreset[]>([])
  const [jPlatform, setJPlatform] = useState('4play')
  const [jHouseName, setJHouseName] = useState('')
  const [jHouseUrl, setJHouseUrl] = useState('')
  const [jLabel, setJLabel] = useState('')
  const [jScoutMode, setJScoutMode] = useState('')
  const [starting, setStarting] = useState(false)
  const [jStatus, setJStatus] = useState<'idle' | 'executing' | 'done' | 'error'>('idle')
  const [jResult, setJResult] = useState<string | null>(null)
  const [jError, setJError] = useState<string | null>(null)
  const [showCustom, setShowCustom] = useState(false)

  useEffect(() => {
    Promise.all([api.stats(), api.platforms(), api.journeyPresets()])
      .then(([s, p, j]) => {
        setStats(s)
        setPlatforms(p)
        setPresets(j)
        const first = j[0]
        if (first) {
          setJPlatform(first.platform)
          setJHouseName(first.name)
          setJHouseUrl(first.url)
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const selectPreset = (preset: JourneyPreset) => {
    setJPlatform(preset.platform)
    setJHouseName(preset.name)
    setJHouseUrl(preset.url)
    setJLabel('')
    setJScoutMode('')
    setShowCustom(false)
    setJResult(null)
    setJError(null)
  }

  const handleStartJourney = async () => {
    setStarting(true)
    setJStatus('executing')
    setJError(null)
    setJResult(null)
    try {
      const res = await api.startJourneySession({
        platform: jPlatform,
        house_name: jHouseName,
        house_url: jHouseUrl,
        scout_mode: jScoutMode,
        label: jLabel,
        close_previous: true,
      })
      setJStatus('done')
      setJResult(
        `Session ${res.session.id.slice(0, 8)} started · ${res.session.house_name || res.session.platform}`,
      )
    } catch (e) {
      setJStatus('error')
      setJError(e instanceof Error ? e.message : 'Failed to start journey')
    } finally {
      setStarting(false)
    }
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading recon data…</div>
  if (error) return <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>

  return (
    <div className="space-y-4">
      {/* Journey status banner */}
      {jStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              jStatus === 'done'
                ? '#00ff8810'
                : jStatus === 'error'
                  ? '#ff3b4d10'
                  : '#ffb30010',
            borderColor:
              jStatus === 'done'
                ? '#00ff8840'
                : jStatus === 'error'
                  ? '#ff3b4d40'
                  : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background:
                jStatus === 'done' ? '#00ff88' : jStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: jStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color:
                jStatus === 'done' ? '#00ff88' : jStatus === 'error' ? '#ff3b4d' : '#ffb300',
            }}
          >
            {jStatus === 'executing'
              ? 'Journey starting…'
              : jStatus === 'done'
                ? 'Journey started successfully'
                : 'Journey start failed'}
          </span>
          {jResult && (
            <span className="text-[11px] font-mono text-[#6b7f94] ml-auto">{jResult}</span>
          )}
        </div>
      )}

      {/* Start New Journey */}
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot" style={{ background: starting ? '#ffb300' : '#00ff88' }} />
          Start New Journey
        </div>
        <div className="panel-body space-y-3">
          <div className="flex gap-2 flex-wrap">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => selectPreset(p)}
                className={`px-3 py-1.5 text-[11px] font-medium border rounded-[2px] transition-colors ${
                  jPlatform === p.platform && !showCustom
                    ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff10]'
                    : 'border-[#1e2d3d] text-[#6b7f94] hover:border-[#3a4f64] hover:text-[#c8d6e5]'
                }`}
              >
                {p.name}
              </button>
            ))}
            <button
              onClick={() => setShowCustom((v) => !v)}
              className={`px-3 py-1.5 text-[11px] font-medium border rounded-[2px] transition-colors ${
                showCustom
                  ? 'border-[#00e5ff] text-[#00e5ff] bg-[#00e5ff10]'
                  : 'border-[#1e2d3d] text-[#6b7f94] hover:border-[#3a4f64] hover:text-[#c8d6e5]'
              }`}
            >
              Custom
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="label">House Name</span>
              <input
                className="input w-full mt-1"
                value={jHouseName}
                onChange={(e) => setJHouseName(e.target.value)}
                placeholder="e.g. 4PLAY.GAME"
                disabled={!showCustom}
              />
            </div>
            <div>
              <span className="label">House URL</span>
              <input
                className="input w-full mt-1"
                value={jHouseUrl}
                onChange={(e) => setJHouseUrl(e.target.value)}
                placeholder="https://…"
                disabled={!showCustom}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <span className="label">Platform</span>
              <select
                className="input w-full mt-1"
                value={jPlatform}
                onChange={(e) => setJPlatform(e.target.value)}
                disabled={!showCustom}
              >
                <option value="pagol_bet_br">pagol_bet_br</option>
                <option value="4play_bet_br">4play_bet_br</option>
                <option value="4play">4play</option>
              </select>
            </div>
            <div>
              <span className="label">Scout Mode</span>
              <input
                className="input w-full mt-1"
                value={jScoutMode}
                onChange={(e) => setJScoutMode(e.target.value)}
                placeholder="optional"
              />
            </div>
            <div>
              <span className="label">Label</span>
              <input
                className="input w-full mt-1"
                value={jLabel}
                onChange={(e) => setJLabel(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              className="btn btn--primary"
              onClick={handleStartJourney}
              disabled={starting || !jHouseName.trim()}
            >
              {starting ? 'Starting…' : '▶ START JOURNEY'}
            </button>
            {jResult && <span className="text-[11px] font-mono text-[#00ff88]">{jResult}</span>}
          </div>
          {jError && <div className="text-[11px] text-[#ff3b4d] font-mono">{jError}</div>}
        </div>
      </div>

      {/* Recon stats */}
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--cyan" />
          Recon — Platform Overview
        </div>
        <div className="panel-body">
          {stats && (
            <div className="grid grid-cols-4 gap-4">
              <div>
                <span className="label">Total Offers</span>
                <span className="text-[20px] font-mono text-[#00e5ff]">{stats.total}</span>
              </div>
              <div>
                <span className="label">Avg Score</span>
                <span className="text-[20px] font-mono text-[#00ff88]">{stats.avg_score}</span>
              </div>
              <div>
                <span className="label">Top Score</span>
                <span className="text-[20px] font-mono text-[#ffb300]">{stats.top_score}</span>
              </div>
              <div>
                <span className="label">Notify Ready</span>
                <span className="text-[20px] font-mono text-[#c8d6e5]">{stats.notify_ready}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Platforms */}
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--dim" />
          Platforms
        </div>
        <div className="panel-body">
          <div className="grid grid-cols-3 gap-3">
            {platforms.map((p) => (
              <div key={p.id} className="border border-[#1e2d3d] rounded-[2px] p-3">
                <div className="text-[12px] font-medium text-[#c8d6e5]">{p.name}</div>
                <div className="text-[10px] text-[#6b7f94] font-mono mt-1">{p.id}</div>
                <div className="text-[10px] text-[#4a5c6e] mt-2">
                  Scraper: <span className="font-mono">{p.scraper}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Distribution */}
      {stats && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot status-dot--dim" />
            Distribution
          </div>
          <div className="panel-body grid grid-cols-3 gap-4">
            <div>
              <span className="label">By Category</span>
              <div className="space-y-1 mt-1">
                {Object.entries(stats.by_category).map(([cat, count]) => (
                  <div key={cat} className="flex justify-between text-[11px]">
                    <span className="text-[#6b7f94] capitalize">{cat}</span>
                    <span className="font-mono text-[#c8d6e5]">{count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <span className="label">By Platform</span>
              <div className="space-y-1 mt-1">
                {Object.entries(stats.by_platform).map(([plat, count]) => (
                  <div key={plat} className="flex justify-between text-[11px]">
                    <span className="text-[#6b7f94]">{HOUSE_LABEL[plat] || plat}</span>
                    <span className="font-mono text-[#c8d6e5]">{count}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <span className="label">By Type</span>
              <div className="space-y-1 mt-1">
                {Object.entries(stats.by_type).map(([type, count]) => (
                  <div key={type} className="flex justify-between text-[11px]">
                    <span className="text-[#6b7f94]">{type.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-[#c8d6e5]">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
