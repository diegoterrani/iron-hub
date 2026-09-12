import TopBar from './components/layout/TopBar'
import PipelineIndicator from './components/pipeline/PipelineIndicator'
import Sidebar from './components/layout/Sidebar'
import ExecutionDeck from './components/exec/ExecutionDeck'
import IntelligenceFeed from './components/feed/IntelligenceFeed'
import ControlDeck from './components/control/ControlDeck'
import usePipeline from './hooks/usePipeline'
import { PipelineProvider } from './context/PipelineContext'

export default function App() {
  const pipeline = usePipeline()

  return (
    <PipelineProvider pipeline={pipeline}>
      <div className="h-screen flex flex-col overflow-hidden">
        <TopBar pipeline={pipeline} />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
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
      </div>
    </PipelineProvider>
  )
}
