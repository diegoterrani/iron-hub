import { Component, useState, type ReactNode } from 'react'
import TopBar from './components/layout/TopBar'
import PipelineIndicator from './components/pipeline/PipelineIndicator'
import Sidebar from './components/layout/Sidebar'
import ExecutionDeck from './components/exec/ExecutionDeck'
import IntelligenceFeed from './components/feed/IntelligenceFeed'
import ControlDeck from './components/control/ControlDeck'
import HistoryModal from './components/history/HistoryModal'
import usePipeline from './hooks/usePipeline'
import { PipelineProvider } from './context/PipelineContext'
import { api } from './services/api'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="h-screen flex items-center justify-center bg-[#0a0e14] p-8">
          <div className="max-w-lg w-full border border-[#ff3b4d40] rounded-[4px] p-6">
            <div className="text-[13px] font-semibold text-[#ff3b4d] mb-3">UI Error</div>
            <pre className="text-[11px] font-mono text-[#c8d6e5] whitespace-pre-wrap mb-4">{this.state.error.message}</pre>
            <button className="btn btn--primary" onClick={() => { this.setState({ error: null }) }}>Retry</button>
            <button className="btn ml-2" onClick={() => window.location.reload()}>Reload</button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const pipeline = usePipeline()
  const [historyOpen, setHistoryOpen] = useState(false)

  const handleNewSession = async (platform: string) => {
    try {
      await api.startJourneySession({ platform, close_previous: true })
    } catch { /* session start failure is non-fatal */ }
  }

  const handleContinueSession = (_sessionId: string) => {
    // Navigate to recon for the active session — the session is already active
    window.location.hash = '#/recon'
  }

  return (
    <ErrorBoundary>
      <PipelineProvider pipeline={pipeline}>
        <div className="h-screen flex flex-col overflow-hidden">
          <TopBar pipeline={pipeline} onHistoryClick={() => setHistoryOpen(true)} />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar onOpenReports={() => setHistoryOpen(true)} />
            <div className="flex-1 flex flex-col overflow-hidden">
              <PipelineIndicator pipeline={pipeline} />
              <div className="flex-1 flex overflow-hidden">
                <ExecutionDeck />
                <div className="w-[340px] border-l border-[#1e2d3d] flex flex-col">
                  <IntelligenceFeed />
                  <ControlDeck />
                </div>
              </div>
            </div>
          </div>
          <HistoryModal
            open={historyOpen}
            onClose={() => setHistoryOpen(false)}
            onNewSession={handleNewSession}
            onContinueSession={handleContinueSession}
          />
        </div>
      </PipelineProvider>
    </ErrorBoundary>
  )
}
