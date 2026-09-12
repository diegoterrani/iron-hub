import { createContext, useContext, type ReactNode } from 'react'
import type { PipelineState } from '../hooks/usePipeline'

const PipelineContext = createContext<PipelineState | null>(null)

export function PipelineProvider({
  pipeline,
  children,
}: {
  pipeline: PipelineState
  children: ReactNode
}) {
  return <PipelineContext.Provider value={pipeline}>{children}</PipelineContext.Provider>
}

export function usePipelineCtx(): PipelineState {
  const ctx = useContext(PipelineContext)
  if (!ctx) throw new Error('usePipelineCtx must be used within PipelineProvider')
  return ctx
}
