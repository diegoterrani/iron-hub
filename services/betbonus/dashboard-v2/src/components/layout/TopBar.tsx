import type { PipelineState } from '../../hooks/usePipeline'
import { HOUSE_LABEL } from '../../lib/casino'

interface Props {
  pipeline: PipelineState
  onHistoryClick: () => void
}

export default function TopBar({ pipeline, onHistoryClick }: Props) {
  const { opsStatus, currentPhase, loading, error } = pipeline

  const houses = opsStatus?.houses ?? []
  const llm = opsStatus?.llm
  const health = opsStatus?.health

  return (
    <header className="flex items-center justify-between px-4 h-11 border-b border-[#1e2d3d] bg-[#0a0e12] shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-[13px] font-bold tracking-[0.12em] text-[#00e5ff]">
          BETBONUS
        </span>
        <span className="text-[10px] tracking-[0.08em] text-[#6b7f94] uppercase">
          Operator Console
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className="status-dot"
            style={{
              background: error ? '#ff3b4d' : loading ? '#ffb300' : '#00ff88',
            }}
          />
          <span className="text-[11px] text-[#6b7f94]">
            {error ? 'OFFLINE' : loading ? 'CONNECTING' : 'ONLINE'}
          </span>
        </div>

        {health && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6b7f94] uppercase">Mode</span>
            <span className="text-[11px] font-mono text-[#00e5ff]">{health.mode}</span>
          </div>
        )}

        {houses.map((h) => (
          <div key={h.id} className="flex items-center gap-1.5">
            <span
              className="status-dot"
              style={{
                background: h.session_ok === false ? '#ff3b4d' : h.has_token ? '#00ff88' : '#374151',
              }}
            />
            <span className="text-[11px] text-[#6b7f94]">{HOUSE_LABEL[h.id] || h.id}</span>
          </div>
        ))}

        {llm?.configured && (
          <div className="flex items-center gap-1.5">
            <span className="status-dot status-dot--cyan" />
            <span className="text-[11px] text-[#6b7f94]">
              LLM {llm.chat_model}
            </span>
          </div>
        )}

        <div className="flex items-center gap-1.5 ml-2 pl-3 border-l border-[#1e2d3d]">
          <span className="text-[10px] text-[#6b7f94] uppercase">Phase</span>
          <span className="text-[11px] font-mono text-[#00e5ff]">{currentPhase}</span>
        </div>

        <button className="btn text-[11px] !px-3 !py-1 ml-2" onClick={onHistoryClick}>
          📋 Histórico
        </button>
      </div>
    </header>
  )
}
