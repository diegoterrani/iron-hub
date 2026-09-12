import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { BonusOffer, LLMStatus } from '../../types'

type AnalyzeResult = Awaited<ReturnType<typeof api.abuseLlmAnalyze>>

export default function AnalyzeView() {
  const [offers, setOffers] = useState<BonusOffer[]>([])
  const [llm, setLlm] = useState<LLMStatus | null>(null)
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [aStatus, setAStatus] = useState<'idle' | 'executing' | 'done' | 'error'>('idle')

  useEffect(() => {
    Promise.all([api.bonuses(), api.llmStatus()])
      .then(([o, l]) => {
        setOffers(o)
        setLlm(l)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleAnalyze = async () => {
    setAnalyzing(true)
    setAStatus('executing')
    setError(null)
    setResult(null)
    try {
      const res = await api.abuseLlmAnalyze({
        offer_ids: [...selectedIds],
        platform,
      })
      setResult(res)
      setAStatus(res.ok ? 'done' : 'error')
    } catch (e) {
      setAStatus('error')
      setError(e instanceof Error ? e.message : 'LLM analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading…</div>

  return (
    <div className="space-y-4">
      {/* Analysis status banner */}
      {aStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              aStatus === 'done'
                ? '#00ff8810'
                : aStatus === 'error'
                  ? '#ff3b4d10'
                  : '#ffb30010',
            borderColor:
              aStatus === 'done'
                ? '#00ff8840'
                : aStatus === 'error'
                  ? '#ff3b4d40'
                  : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background:
                aStatus === 'done' ? '#00ff88' : aStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: aStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color:
                aStatus === 'done' ? '#00ff88' : aStatus === 'error' ? '#ff3b4d' : '#ffb300',
            }}
          >
            {aStatus === 'executing'
              ? 'LLM analysis running…'
              : aStatus === 'done'
                ? `Analysis complete — ${result?.count ?? 0} offer(s) analyzed`
                : 'Analysis failed'}
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
          <span className="status-dot" style={{ background: llm?.configured ? '#00e5ff' : '#374151' }} />
          LLM Analyzer
          {llm?.configured && (
            <span className="ml-auto text-[10px] text-[#4a5c6e] font-mono">
              {llm.chat_model}
            </span>
          )}
        </div>
        <div className="panel-body space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <select className="input w-auto" value={platform} onChange={(e) => setPlatform(e.target.value)}>
                <option value="pagol_bet_br">pagol.bet.br</option>
                <option value="4play_bet_br">4play.bet.br</option>
                <option value="4play">4play.game</option>
              </select>
              <span className="text-[11px] text-[#6b7f94]">
                {selectedIds.size} of {offers.length} offers selected
              </span>
            </div>
            <button
              className="btn btn--primary"
              onClick={handleAnalyze}
              disabled={analyzing || selectedIds.size === 0 || !llm?.configured}
            >
              {analyzing ? 'Analyzing…' : 'RUN LLM ANALYSIS'}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}

      {result && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot" style={{ background: result.ok ? '#00ff88' : '#ff3b4d' }} />
            Analysis Results
            <span className="ml-auto text-[10px] text-[#4a5c6e] font-mono">
              {result.model || result.source} · {result.count} item(s)
            </span>
          </div>
          <div className="panel-body space-y-3">
            {result.items.length > 0 && (
              <div className="space-y-2">
                <span className="label">Per-offer analysis</span>
                {result.items.map((item) => (
                  <div key={item.offer_id} className="border border-[#1e2d3d] rounded-[2px] px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-[#c8d6e5] font-medium">{item.title}</span>
                      {item.abuse_severity_heuristic && (
                        <span
                          className="mode-badge"
                          style={{
                            background:
                              item.abuse_severity_heuristic === 'critical'
                                ? '#ff3b4d18'
                                : item.abuse_severity_heuristic === 'high'
                                  ? '#ffaa0018'
                                  : '#00e5ff18',
                            color:
                              item.abuse_severity_heuristic === 'critical'
                                ? '#ff3b4d'
                                : item.abuse_severity_heuristic === 'high'
                                  ? '#ffaa00'
                                  : '#00e5ff',
                          }}
                        >
                          {item.abuse_severity_heuristic}
                        </span>
                      )}
                      {item.abuse_score_heuristic != null && (
                        <span className="text-[10px] font-mono text-[#6b7f94] ml-auto">
                          score {item.abuse_score_heuristic}
                        </span>
                      )}
                    </div>
                    {item.llm?.summary && (
                      <div className="text-[11px] text-[#c8d6e5] mt-1.5">{item.llm.summary}</div>
                    )}
                    {item.llm?.conversion_path && (
                      <div className="text-[10px] text-[#6b7f94] mt-1">{item.llm.conversion_path}</div>
                    )}
                    {item.llm?.abuse_vectors && item.llm.abuse_vectors.length > 0 && (
                      <div className="mt-2 space-y-1.5">
                        {item.llm.abuse_vectors.map((v) => (
                          <div key={v.id} className="border border-[#1e2d3d] rounded-[2px] px-2 py-1.5">
                            <div className="flex items-center gap-2">
                              <span
                                className="mode-badge"
                                style={{
                                  background:
                                    v.severity === 'critical'
                                      ? '#ff3b4d18'
                                      : v.severity === 'high'
                                        ? '#ffaa0018'
                                        : '#00e5ff18',
                                  color:
                                    v.severity === 'critical'
                                      ? '#ff3b4d'
                                      : v.severity === 'high'
                                        ? '#ffaa00'
                                        : '#00e5ff',
                                }}
                              >
                                {v.severity}
                              </span>
                              <span className="text-[11px] text-[#c8d6e5]">{v.title}</span>
                            </div>
                            {v.rationale && (
                              <div className="text-[10px] text-[#6b7f94] mt-1">{v.rationale}</div>
                            )}
                            {v.test_idea && (
                              <div className="text-[10px] text-[#4a5c6e] mt-1 font-mono">{v.test_idea}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {item.llm?.reason && (
                      <div className="text-[10px] text-[#ffaa00] mt-1.5">{item.llm.reason}</div>
                    )}
                    {item.llm?.parse_error && (
                      <div className="text-[10px] text-[#ff3b4d] mt-1.5">{item.llm.parse_error}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
            {result.errors.length > 0 && (
              <div className="space-y-1">
                <span className="label">Errors</span>
                {result.errors.map((e) => (
                  <div key={e.offer_id} className="text-[11px] text-[#ff3b4d] font-mono">
                    {e.title}: {e.error}
                    {e.truncated ? ' (truncated)' : ''}
                  </div>
                ))}
              </div>
            )}
            <details>
              <summary className="text-[10px] text-[#4a5c6e] cursor-pointer">Raw JSON</summary>
              <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap max-h-[400px] overflow-y-auto mt-2">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--dim" />
          Select Offers
        </div>
        <div className="panel-body">
          <div className="space-y-1">
            {offers.map((o) => (
              <label
                key={o.id}
                className="flex items-center gap-3 border border-[#1e2d3d] rounded-[2px] px-3 py-2 cursor-pointer hover:bg-[#1a2330] transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(o.id)}
                  onChange={() => toggleSelect(o.id)}
                />
                <span className="text-[11px] text-[#c8d6e5] flex-1 truncate">{o.title}</span>
                <span className="text-[10px] font-mono text-[#00e5ff]">{o.platform}</span>
                <span className="text-[10px] font-mono text-[#00ff88]">{o.score}</span>
              </label>
            ))}
            {offers.length === 0 && (
              <div className="text-[11px] text-[#4a5c6e] italic">No offers to analyze</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
