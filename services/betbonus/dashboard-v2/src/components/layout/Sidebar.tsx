import { NavLink } from 'react-router-dom'
import { usePipelineCtx } from '../../context/PipelineContext'
import type { PipelinePhase } from '../../lib/casino'

const NAV_ITEMS = [
  { path: '/recon', label: 'Recon', icon: '⊙', phase: 'Recon' as PipelinePhase },
  { path: '/auth', label: 'Auth', icon: '⊘', phase: 'Auth' as PipelinePhase },
  { path: '/discovery', label: 'Discovery', icon: '⊕', phase: 'Discovery' as PipelinePhase },
  { path: '/acquire', label: 'Acquire', icon: '⊗', phase: 'Acquire' as PipelinePhase },
  { path: '/arm', label: 'Arm', icon: '⊚', phase: 'Arm' as PipelinePhase },
  { path: '/analyze', label: 'Analyze', icon: '◎', phase: 'Analyze' as PipelinePhase },
  { path: '/probe', label: 'Probe', icon: '⊛', phase: 'Probe' as PipelinePhase },
  { path: '/cashout', label: 'Cashout', icon: '⊡', phase: 'Cashout' as PipelinePhase },
  { path: '/report', label: 'Report', icon: '⊞', phase: 'Report' as PipelinePhase },
]

const STATUS_COLORS: Record<string, string> = {
  done: '#00ff88',
  active: '#00e5ff',
  error: '#ff3b4d',
  pending: '#1e2d3d',
}

export default function Sidebar() {
  const pipeline = usePipelineCtx()
  const { phaseStatus } = pipeline

  return (
    <nav className="w-[140px] border-r border-[#1e2d3d] bg-[#0a0e12] flex flex-col shrink-0">
      <div className="px-3 py-2 border-b border-[#1e2d3d]">
        <span className="text-[10px] font-semibold tracking-[0.1em] text-[#6b7f94] uppercase">
          Pipeline
        </span>
      </div>
      <div className="flex-1 py-1">
        {NAV_ITEMS.map((item, i) => {
          const status = phaseStatus[item.phase]
          const dotColor = STATUS_COLORS[status]
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-[7px] text-[12px] transition-colors ${
                  isActive
                    ? 'bg-[#1a2330] text-[#00e5ff] border-r-2 border-[#00e5ff]'
                    : 'text-[#6b7f94] hover:text-[#c8d6e5] hover:bg-[#121820]'
                }`
              }
            >
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{
                  background: dotColor,
                  boxShadow: status === 'active' ? `0 0 4px ${dotColor}80` : 'none',
                }}
              />
              <span className="text-[10px] opacity-60 w-3 text-center">{i + 1}</span>
              <span className="text-[11px] opacity-50">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
