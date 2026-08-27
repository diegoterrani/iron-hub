import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Activity } from './pages/Activity'
import { Admin } from './pages/Admin'
import { Agents } from './pages/Agents'
import { Analyzer } from './pages/Analyzer'
import { Bonuses } from './pages/Bonuses'
import { Integrity } from './pages/Integrity'
import { Journey } from './pages/Journey'
import { JourneyLogs } from './pages/JourneyLogs'
import { OpsConsole } from './pages/OpsConsole'
import { Pipeline } from './pages/Pipeline'
import { Runs } from './pages/Runs'
import { Settings } from './pages/Settings'
import { Wallet } from './pages/Wallet'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OpsConsole />} />
        <Route path="matriz" element={<Integrity />} />
        <Route path="agentes" element={<Agents />} />
        <Route path="runs" element={<Runs />} />
        <Route path="admin" element={<Admin />} />
        <Route path="journey" element={<Journey />} />
        <Route path="wallet" element={<Wallet />} />
        <Route path="bonuses" element={<Bonuses />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="analyzer" element={<Analyzer />} />
        <Route path="logs" element={<JourneyLogs />} />
        <Route path="settings" element={<Settings />} />
        <Route path="activity" element={<Activity />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
