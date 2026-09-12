import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { usePipelineCtx } from '../../context/PipelineContext'
import type { PipelinePhase } from '../../lib/casino'

const PATH_TO_PHASE: Record<string, PipelinePhase> = {
  '/recon': 'Recon',
  '/auth': 'Auth',
  '/discovery': 'Discovery',
  '/acquire': 'Acquire',
  '/arm': 'Arm',
  '/analyze': 'Analyze',
  '/probe': 'Probe',
  '/cashout': 'Cashout',
  '/report': 'Report',
}

export default function PhaseTracker() {
  const { pathname } = useLocation()
  const pipeline = usePipelineCtx()
  const { setPhase, phaseStatus } = pipeline

  useEffect(() => {
    const phase = PATH_TO_PHASE[pathname]
    if (!phase) return
    const current = phaseStatus[phase]
    if (current === 'pending' || current === 'error') {
      setPhase(phase, 'active')
    }
  }, [pathname, setPhase, phaseStatus])

  return null
}
