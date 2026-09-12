import { useCallback, useEffect, useRef, useState } from 'react'
import { PIPELINE_PHASES, type PipelinePhase } from '../lib/casino'
import { api } from '../services/api'
import type { OpsStatus } from '../types'

type PhaseStatus = 'pending' | 'active' | 'done' | 'error'

function initialPhaseStatus(): Record<PipelinePhase, PhaseStatus> {
  const init = {} as Record<PipelinePhase, PhaseStatus>
  PIPELINE_PHASES.forEach((p, i) => {
    init[p] = i === 0 ? 'active' : 'pending'
  })
  return init
}

export default function usePipeline() {
  const [currentPhase, setCurrentPhase] = useState<PipelinePhase>('Recon')
  const [phaseStatus, setPhaseStatus] = useState<Record<PipelinePhase, PhaseStatus>>(initialPhaseStatus)
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const status = await api.opsStatus()
      setOpsStatus(status)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch ops status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    pollRef.current = setInterval(refresh, 10000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [refresh])

  const setPhase = useCallback(
    (phase: PipelinePhase, status: PhaseStatus) => {
      setPhaseStatus((prev) => ({ ...prev, [phase]: status }))
      setCurrentPhase(phase)
    },
    [],
  )

  const advancePhase = useCallback(() => {
    const idx = PIPELINE_PHASES.indexOf(currentPhase)
    const next = idx < PIPELINE_PHASES.length - 1 ? PIPELINE_PHASES[idx + 1] : undefined
    if (next !== undefined) {
      setPhaseStatus((prev) => ({
        ...prev,
        [currentPhase]: 'done',
        [next]: 'active',
      }))
      setCurrentPhase(next)
    }
  }, [currentPhase])

  const resetPipeline = useCallback(() => {
    setPhaseStatus(initialPhaseStatus)
    setCurrentPhase('Recon')
  }, [])

  return {
    currentPhase,
    phaseStatus,
    opsStatus,
    loading,
    error,
    refresh,
    setPhase,
    advancePhase,
    resetPipeline,
  }
}

export type PipelineState = ReturnType<typeof usePipeline>
