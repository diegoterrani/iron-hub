import { useCallback, useEffect, useState } from 'react'
import { api } from '../../services/api'
import { HOUSE_LABEL } from '../../lib/casino'

interface ReportEntry {
  version: number
  filename: string
  size_bytes: number
  modified_at: string
}

interface HouseGroup {
  house_name: string
  platform: string
  house_url: string
  session_id: string
  session_status: string
  started_at: string | null
  ended_at: string | null
  event_count: number
  last_message: string
  reports: ReportEntry[]
}

interface AllReports {
  houses: HouseGroup[]
  total_reports: number
}

interface Props {
  open: boolean
  onClose: () => void
  onNewSession: (platform: string) => void
  onContinueSession: (sessionId: string) => void
}

const STATUS_STYLES: Record<string, { bg: string; color: string; label: string }> = {
  active: { bg: '#00e5ff18', color: '#00e5ff', label: 'ACTIVE' },
  closed: { bg: '#00ff8818', color: '#00ff88', label: 'CLOSED' },
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function parseDateFromFilename(filename: string): string | null {
  const m = filename.match(/(\d{4}-\d{2}-\d{2})/)
  return m?.[1] ?? null
}

export default function HistoryModal({ open, onClose, onNewSession, onContinueSession }: Props) {
  const [data, setData] = useState<AllReports | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedHouse, setExpandedHouse] = useState<string | null>(null)
  const [viewingMd, setViewingMd] = useState<string | null>(null)
  const [viewingFilename, setViewingFilename] = useState<string | null>(null)
  const [viewingSessionId, setViewingSessionId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await api.listAllJourneyReports())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar histórico')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) { load(); setViewingMd(null); setViewingFilename(null); setViewingSessionId(null); setExpandedHouse(null) }
  }, [open, load])

  useEffect(() => {
    if (!open) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [open, onClose])

  if (!open) return null

  const handleDownload = async (sessionId: string, filename: string) => {
    try {
      const res = await fetch(`/api/journey/sessions/${sessionId}/report.md?filename=${encodeURIComponent(filename)}`, { credentials: 'same-origin' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = filename
      document.body.appendChild(a); a.click(); a.remove()
      URL.revokeObjectURL(url)
    } catch (e) { setError(e instanceof Error ? e.message : 'Download falhou') }
  }

  const handleViewMd = async (sessionId: string, filename: string) => {
    try {
      const res = await fetch(`/api/journey/sessions/${sessionId}/report.md?filename=${encodeURIComponent(filename)}`, { credentials: 'same-origin' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setViewingSessionId(sessionId)
      setViewingFilename(filename)
      setViewingMd(await res.text())
    } catch (e) { setError(e instanceof Error ? e.message : 'Falha ao carregar relatório') }
  }

  const handleCloseSession = async (sessionId: string) => {
    setBusy(true)
    try { await api.closeJourneySession(sessionId, 'Encerrado via History Modal'); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Falha ao encerrar sessão') }
    finally { setBusy(false) }
  }

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('Excluir esta sessão e todos os seus dados?')) return
    setBusy(true)
    try { await api.deleteJourneySession(sessionId); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Falha ao excluir sessão') }
    finally { setBusy(false) }
  }

  const handleRetest = (sessionId: string) => { onContinueSession(sessionId); onClose() }
  const handleNewForHouse = (platform: string) => { onNewSession(platform); onClose() }

  const grouped: Map<string, HouseGroup[]> = new Map()
  if (data) {
    for (const h of data.houses) {
      const key = h.house_name || h.platform
      if (!grouped.has(key)) grouped.set(key, [])
      grouped.get(key)!.push(h)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-[820px] max-w-[95vw] max-h-[85vh] flex flex-col bg-[#0a0e12] border border-[#1e2d3d] rounded-[2px] shadow-[0_0_40px_#00000080]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e2d3d] shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[13px] font-bold tracking-[0.12em] text-[#00e5ff]">HISTÓRICO</span>
            <span className="text-[10px] tracking-[0.08em] text-[#6b7f94] uppercase">Testes / Exploits</span>
            {data && (
              <span className="text-[10px] font-mono text-[#4a5c6e]">
                {data.houses.length} sessões · {data.total_reports} relatórios
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button className="btn" onClick={load} disabled={loading}>
              {loading ? 'Carregando…' : 'Atualizar'}
            </button>
            <button className="btn btn--primary" onClick={() => { onNewSession('4play'); onClose() }}>
              + Nova Sessão
            </button>
            <button className="btn text-[#6b7f94] hover:text-[#c8d6e5]" onClick={onClose} aria-label="Fechar">✕</button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {loading && !data && (
            <div className="p-8 text-center text-[#4a5c6e] font-mono text-[12px]">Carregando histórico…</div>
          )}
          {error && (
            <div className="p-4">
              <div className="bg-[#ff3b4d10] border border-[#ff3b4d30] rounded-[2px] px-3 py-2 text-[11px] text-[#ff3b4d] font-mono">{error}</div>
            </div>
          )}
          {data && !loading && data.houses.length === 0 && (
            <div className="p-8 text-center">
              <div className="text-[#4a5c6e] font-mono text-[12px] mb-3">Nenhuma sessão de teste registrada.</div>
              <button className="btn btn--primary" onClick={() => { onNewSession('4play'); onClose() }}>
                Iniciar Primeira Sessão
              </button>
            </div>
          )}
          {data && !loading && data.houses.length > 0 && (
            <div className="p-3 space-y-2">
              {[...grouped.entries()].map(([houseName, sessions]) => {
                const isExpanded = expandedHouse === houseName
                const totalReports = sessions.reduce((s, h) => s + h.reports.length, 0)
                const latestDate = sessions
                  .flatMap((h) => h.reports.map((r) => parseDateFromFilename(r.filename) || h.ended_at?.slice(0, 10) || h.started_at?.slice(0, 10) || ''))
                  .filter(Boolean)
                  .sort()
                  .pop()
                const hasActive = sessions.some((h) => h.session_status === 'active')
                const firstSession = sessions[0]!

                return (
                  <div key={houseName} className="border border-[#1e2d3d] rounded-[2px] overflow-hidden">
                    <button
                      className="w-full flex items-center justify-between px-3 py-2.5 bg-[#121820] hover:bg-[#1a2330] transition-colors text-left"
                      onClick={() => setExpandedHouse(isExpanded ? null : houseName)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="status-dot" style={{ background: hasActive ? '#00e5ff' : '#374151', boxShadow: hasActive ? '0 0 4px #00e5ff80' : 'none' }} />
                        <span className="text-[13px] font-semibold text-[#e8f0f8]">{HOUSE_LABEL[firstSession.platform] || houseName}</span>
                        <span className="text-[10px] font-mono text-[#4a5c6e]">{sessions.length} sessão(ões) · {totalReports} relatório(s)</span>
                        {latestDate && <span className="text-[10px] font-mono text-[#6b7f94]">Último: {latestDate}</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <button className="btn text-[10px] !px-2 !py-1" onClick={(e) => { e.stopPropagation(); handleNewForHouse(firstSession.platform) }}>+ Nova</button>
                        <span className={`text-[10px] transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▸</span>
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="border-t border-[#1e2d3d]">
                        {sessions.map((h) => {
                          const st = STATUS_STYLES[h.session_status] || { bg: '#37415118', color: '#6b7f94', label: h.session_status.toUpperCase() }
                          const sortedReports = [...h.reports].sort((a, b) => {
                            const da = parseDateFromFilename(a.filename) || a.modified_at
                            const db = parseDateFromFilename(b.filename) || b.modified_at
                            if (da !== db) return da < db ? 1 : -1
                            return b.version - a.version
                          })

                          return (
                            <div key={h.session_id} className="px-3 py-2.5 border-b border-[#1e2d3d40] last:border-b-0">
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2.5">
                                  <span className="mode-badge" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                                  <span className="text-[11px] font-mono text-[#6b7f94]">{h.session_id.slice(0, 8)}</span>
                                  <span className="text-[10px] text-[#4a5c6e]">{formatDate(h.started_at)}{h.ended_at && ` → ${formatDate(h.ended_at)}`}</span>
                                  <span className="text-[10px] text-[#4a5c6e]">{h.event_count} eventos</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                  {h.session_status === 'active' && (
                                    <>
                                      <button className="btn btn--success text-[10px] !px-2 !py-1" onClick={() => handleRetest(h.session_id)} disabled={busy}>Continuar</button>
                                      <button className="btn btn--danger text-[10px] !px-2 !py-1" onClick={() => handleCloseSession(h.session_id)} disabled={busy}>Encerrar</button>
                                    </>
                                  )}
                                  <button className="btn text-[10px] !px-2 !py-1" onClick={() => handleRetest(h.session_id)} disabled={busy}>Re-testar</button>
                                  <button className="btn btn--danger text-[10px] !px-2 !py-1" onClick={() => handleDeleteSession(h.session_id)} disabled={busy}>Excluir</button>
                                </div>
                              </div>

                              {h.last_message && (
                                <div className="text-[10px] text-[#4a5c6e] mb-2 truncate" title={h.last_message}>Último: {h.last_message}</div>
                              )}

                              {h.reports.length > 0 ? (
                                <div className="space-y-1 ml-2">
                                  {sortedReports.map((r) => {
                                    const rDate = parseDateFromFilename(r.filename)
                                    return (
                                      <div key={r.filename} className="flex items-center justify-between bg-[#0a0e12] border border-[#1e2d3d40] rounded-[2px] px-2.5 py-1.5">
                                        <div className="flex items-center gap-2.5">
                                          <span className="mode-badge" style={{ background: '#00e5ff12', color: '#00e5ff' }}>v{r.version}</span>
                                          <span className="text-[10px] font-mono text-[#6b7f94]">{rDate || r.modified_at.slice(0, 10)}</span>
                                          <span className="text-[10px] font-mono text-[#4a5c6e]">{formatSize(r.size_bytes)}</span>
                                          <span className="text-[10px] text-[#4a5c6e] hidden xl:inline truncate max-w-[200px]" title={r.filename}>{r.filename}</span>
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                          <button className="btn text-[9px] !px-2 !py-0.5" onClick={() => handleViewMd(h.session_id, r.filename)}>Ver</button>
                                          <button className="btn text-[9px] !px-2 !py-0.5" onClick={() => handleDownload(h.session_id, r.filename)}>⬇ Baixar</button>
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              ) : (
                                <div className="text-[10px] text-[#4a5c6e] italic ml-2">Sem relatórios gerados.</div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* MD viewer overlay */}
        {viewingMd !== null && (
          <div className="absolute inset-0 bg-[#0a0e12] flex flex-col z-10">
            <div className="flex items-center justify-between px-4 py-2 border-b border-[#1e2d3d] shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-[#6b7f94]">Relatório</span>
                {viewingFilename && (
                  <span className="text-[10px] font-mono text-[#4a5c6e] truncate max-w-[400px]">{viewingFilename}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {viewingFilename && viewingSessionId && (
                  <button className="btn text-[10px] !px-2 !py-1" onClick={() => handleDownload(viewingSessionId, viewingFilename)}>⬇ Baixar</button>
                )}
                <button className="btn text-[10px] !px-2 !py-1" onClick={() => { setViewingMd(null); setViewingFilename(null); setViewingSessionId(null) }}>Fechar ✕</button>
              </div>
            </div>
            <pre className="flex-1 overflow-y-auto p-4 text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap">
              {viewingMd}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}
