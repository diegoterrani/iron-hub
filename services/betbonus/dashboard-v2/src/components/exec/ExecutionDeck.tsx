import { Routes, Route, Navigate } from 'react-router-dom'
import PhaseTracker from './PhaseTracker'
import ReconView from '../phases/ReconView'
import AuthView from '../phases/AuthView'
import DiscoveryView from '../phases/DiscoveryView'
import AcquireView from '../phases/AcquireView'
import ArmView from '../phases/ArmView'
import AnalyzeView from '../phases/AnalyzeView'
import ProbeView from '../phases/ProbeView'
import CashoutView from '../phases/CashoutView'
import ReportView from '../phases/ReportView'
import CampaignView from '../phases/CampaignView'

export default function ExecutionDeck() {
  return (
    <div className="flex-1 overflow-y-auto p-4">
      <PhaseTracker />
      <Routes>
        <Route path="/" element={<Navigate to="/recon" replace />} />
        <Route path="/recon" element={<ReconView />} />
        <Route path="/auth" element={<AuthView />} />
        <Route path="/discovery" element={<DiscoveryView />} />
        <Route path="/acquire" element={<AcquireView />} />
        <Route path="/arm" element={<ArmView />} />
        <Route path="/analyze" element={<AnalyzeView />} />
        <Route path="/probe" element={<ProbeView />} />
        <Route path="/cashout" element={<CashoutView />} />
        <Route path="/report" element={<ReportView />} />
        <Route path="/campaign" element={<CampaignView />} />
        <Route path="*" element={<Navigate to="/recon" replace />} />
      </Routes>
    </div>
  )
}
