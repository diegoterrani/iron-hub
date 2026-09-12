import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { BonusOffer, ScrapeUrlResponse } from '../../types'

export default function DiscoveryView() {
  const [offers, setOffers] = useState<BonusOffer[]>([])
  const [scrapeResult, setScrapeResult] = useState<ScrapeUrlResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [url, setUrl] = useState('')
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [scraping, setScraping] = useState(false)
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'executing' | 'done' | 'error'>('idle')

  useEffect(() => {
    api
      .bonuses()
      .then(setOffers)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const handleScrape = async () => {
    setScraping(true)
    setScrapeStatus('executing')
    setScrapeResult(null)
    try {
      const res = await api.runUrl(platform, url)
      setScrapeResult(res)
      setScrapeStatus(res.ok ? 'done' : 'error')
      const updated = await api.bonuses()
      setOffers(updated)
    } catch (e) {
      setScrapeStatus('error')
      setError(e instanceof Error ? e.message : 'Scrape failed')
    } finally {
      setScraping(false)
    }
  }

  const handleLive = async () => {
    setScraping(true)
    setScrapeStatus('executing')
    setScrapeResult(null)
    try {
      const res = await api.runLive(platform)
      setScrapeResult(res)
      setScrapeStatus(res.ok ? 'done' : 'error')
      const updated = await api.bonuses()
      setOffers(updated)
    } catch (e) {
      setScrapeStatus('error')
      setError(e instanceof Error ? e.message : 'Live scrape failed')
    } finally {
      setScraping(false)
    }
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading offers…</div>

  return (
    <div className="space-y-4">
      {/* Scrape status banner */}
      {scrapeStatus !== 'idle' && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 border rounded-[2px]"
          style={{
            background:
              scrapeStatus === 'done'
                ? '#00ff8810'
                : scrapeStatus === 'error'
                  ? '#ff3b4d10'
                  : '#ffb30010',
            borderColor:
              scrapeStatus === 'done'
                ? '#00ff8840'
                : scrapeStatus === 'error'
                  ? '#ff3b4d40'
                  : '#ffb30040',
          }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background:
                scrapeStatus === 'done' ? '#00ff88' : scrapeStatus === 'error' ? '#ff3b4d' : '#ffb300',
              boxShadow: scrapeStatus === 'executing' ? '0 0 6px #ffb30080' : 'none',
            }}
          />
          <span
            className="text-[12px] font-medium"
            style={{
              color:
                scrapeStatus === 'done' ? '#00ff88' : scrapeStatus === 'error' ? '#ff3b4d' : '#ffb300',
            }}
          >
            {scrapeStatus === 'executing'
              ? 'Scraping in progress…'
              : scrapeStatus === 'done'
                ? `Scrape complete — ${scrapeResult?.offers.length ?? 0} offer(s) found`
                : 'Scrape failed'}
          </span>
          {scrapeResult?.error && (
            <span className="text-[11px] font-mono text-[#ff3b4d] ml-auto truncate max-w-[300px]">
              {scrapeResult.error}
            </span>
          )}
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--cyan" />
          URL Scrape
        </div>
        <div className="panel-body flex items-end gap-3">
          <div className="flex-1">
            <span className="label">URL</span>
            <input
              className="input w-full"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/promos"
            />
          </div>
          <div>
            <span className="label">Platform</span>
            <select
              className="input"
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              <option value="pagol_bet_br">pagol.bet.br</option>
              <option value="4play_bet_br">4play.bet.br</option>
              <option value="4play">4play.game</option>
            </select>
          </div>
          <button className="btn btn--primary" onClick={handleScrape} disabled={scraping}>
            {scraping ? 'Scraping…' : 'Scrape URL'}
          </button>
          <button className="btn" onClick={handleLive} disabled={scraping}>
            Live
          </button>
        </div>
      </div>

      {scrapeResult && (
        <div className="panel">
          <div className="panel-header">
            <span
              className="status-dot"
              style={{ background: scrapeResult.ok ? '#00ff88' : '#ff3b4d' }}
            />
            Scrape Result
          </div>
          <div className="panel-body">
            {scrapeResult.error && (
              <div className="text-[11px] text-[#ff3b4d] font-mono">{scrapeResult.error}</div>
            )}
            <div className="text-[11px] text-[#6b7f94]">
              {scrapeResult.offers.length} offers found from{' '}
              <span className="font-mono text-[#00e5ff]">{scrapeResult.source_url}</span>
            </div>
          </div>
        </div>
      )}

      {error && <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>}

      {/* Category & Score explanation */}
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--dim" />
          How to Read Scores &amp; Categories
        </div>
        <div className="panel-body space-y-3">
          <div className="text-[11px] text-[#6b7f94]">
            The <span className="font-mono text-[#00ff88]">Score</span> (0–100) is a
            <strong> profitability heuristic</strong> — it estimates how much real value you can
            extract from a bonus after meeting wagering requirements. Higher = more extractable
            value per account.
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="border border-[#1e2d3d] rounded-[2px] p-3">
              <span
                className="mode-badge"
                style={{ background: '#00ff8818', color: '#00ff88' }}
              >
                excellent
              </span>
              <div className="text-[10px] text-[#6b7f94] mt-2">
                Score ≥ 70. High-value bonus with achievable wagering. Best candidates for abuse
                at scale — profit per account is meaningful.
              </div>
            </div>
            <div className="border border-[#1e2d3d] rounded-[2px] p-3">
              <span
                className="mode-badge"
                style={{ background: '#00e5ff18', color: '#00e5ff' }}
              >
                good
              </span>
              <div className="text-[10px] text-[#6b7f94] mt-2">
                Score 40–69. Decent value but wagering or cap limits reduce extractable profit.
                Worth pursuing with volume.
              </div>
            </div>
            <div className="border border-[#1e2d3d] rounded-[2px] p-3">
              <span
                className="mode-badge"
                style={{ background: '#ff3b4d18', color: '#ff3b4d' }}
              >
                avoid
              </span>
              <div className="text-[10px] text-[#6b7f94] mt-2">
                Score &lt; 40. Wagering too high, cap too low, or bonus too small to justify the
                effort. Low probability of profitable abuse.
              </div>
            </div>
          </div>
          <div className="text-[10px] text-[#4a5c6e]">
            Score factors: bonus amount vs. wagering requirement, max cashout cap, max bet limit,
            bonus type (deposit vs. free spin vs. no-deposit), and platform reliability.
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--dim" />
          Discovered Offers ({offers.length})
        </div>
        <div className="panel-body">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-[#6b7f94] border-b border-[#1e2d3d]">
                <th className="pb-2 pr-3">Title</th>
                <th className="pb-2 pr-3">Platform</th>
                <th className="pb-2 pr-3">Type</th>
                <th className="pb-2 pr-3">Amount</th>
                <th className="pb-2 pr-3">Score</th>
                <th className="pb-2">Category</th>
              </tr>
            </thead>
            <tbody>
              {offers.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-3 text-[#4a5c6e] italic">
                    No offers discovered yet. Scrape a URL or run live.
                  </td>
                </tr>
              )}
              {offers.map((o) => (
                <tr key={o.id} className="border-b border-[#1e2d3d30]">
                  <td className="py-2 pr-3 text-[#c8d6e5] max-w-[200px] truncate">{o.title}</td>
                  <td className="py-2 pr-3 font-mono text-[#00e5ff]">{o.platform}</td>
                  <td className="py-2 pr-3 text-[#6b7f94]">{o.bonus_type.replace(/_/g, ' ')}</td>
                  <td className="py-2 pr-3 font-mono">
                    {o.amount} {o.currency}
                  </td>
                  <td className="py-2 pr-3 font-mono text-[#00ff88]">{o.score}</td>
                  <td className="py-2">
                    <span
                      className="mode-badge"
                      style={{
                        background:
                          o.category === 'excellent'
                            ? '#00ff8818'
                            : o.category === 'good'
                              ? '#00e5ff18'
                              : o.category === 'avoid'
                                ? '#ff3b4d18'
                                : '#1e2d3d40',
                        color:
                          o.category === 'excellent'
                            ? '#00ff88'
                            : o.category === 'good'
                              ? '#00e5ff'
                              : o.category === 'avoid'
                                ? '#ff3b4d'
                                : '#6b7f94',
                      }}
                    >
                      {o.category}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
