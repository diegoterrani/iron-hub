import type { PipelineState } from '../../hooks/usePipeline'
import { PIPELINE_PHASES } from '../../lib/casino'

interface Props {
  pipeline: PipelineState
}

export default function PipelineIndicator({ pipeline }: Props) {
  const { phaseStatus } = pipeline

  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b border-[#1e2d3d] bg-[#0a0e12] shrink-0">
      {PIPELINE_PHASES.map((phase, i) => {
        const status = phaseStatus[phase]
        const bg =
          status === 'done'
            ? '#00ff88'
            : status === 'active'
              ? '#00e5ff'
              : status === 'error'
                ? '#ff3b4d'
                : '#1e2d3d'
        return (
          <div key={phase} className="flex items-center gap-1">
            {i > 0 && <div className="w-4 h-px bg-[#1e2d3d]" />}
            <div className="flex items-center gap-1.5">
              <div
                className="w-2 h-2 rounded-[1px] transition-all"
                style={{
                  background: bg,
                  boxShadow: status === 'active' ? `0 0 6px ${bg}80` : 'none',
                }}
              />
              <span
                className="text-[10px] tracking-[0.06em] uppercase"
                style={{
                  color: status === 'active' ? '#00e5ff' : status === 'done' ? '#00ff88' : '#4a5c6e',
                }}
              >
                {phase}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
