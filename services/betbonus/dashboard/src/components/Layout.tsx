import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { OpsStatus } from '../types'

const opsLinks = [
  { to: '/', label: 'Jornada de teste', end: true },
  { to: '/matriz', label: 'Matriz' },
]

const execLinks = [
  { to: '/agentes', label: 'Agentes' },
  { to: '/runs', label: 'Runs' },
]

const adminLinks = [
  { to: '/admin', label: 'Casas / LLM' },
]

const legadoLinks = [
  { to: '/journey', label: 'Jornada promo' },
  { to: '/wallet', label: 'Carteira' },
  { to: '/bonuses', label: 'Bonuses' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/logs', label: 'Logs' },
  { to: '/activity', label: 'Activity' },
]

export function Layout() {
  const [ops, setOps] = useState<OpsStatus | null>(null)

  useEffect(() => {
    api.opsStatus().then(setOps).catch(() => undefined)
    const id = window.setInterval(() => {
      api.opsStatus().then(setOps).catch(() => undefined)
    }, 15000)
    return () => window.clearInterval(id)
  }, [])

  const authed = ops?.houses.filter((h) => h.session_ok ?? h.has_token).length ?? 0
  const llmOn = Boolean(ops?.llm.configured)

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-mark" aria-hidden>
            <span />
          </div>
          <div>
            <strong>Casino Integrity</strong>
            <span>Iron Security · SOC iGaming</span>
          </div>
        </div>
        <div className="topbar-meta">
          <span className={`pill ${authed === 3 ? 'pill--ok' : authed ? 'pill--warn' : 'pill--off'}`}>
            Casas {authed}/3
          </span>
          <span className={`pill ${llmOn ? 'pill--ok' : 'pill--off'}`}>
            LLM {llmOn ? 'ON' : 'OFF'}
          </span>
          <span className="pill pill--info">{ops?.safety.default_mode || 'PROBE'}</span>
          <a className="btn btn-ghost topbar-hub" href="/console/">
            Iron Hub
          </a>
        </div>
      </header>

      <aside className="sidebar">
        <div className="brand">
          <h1>Agentes Cassino</h1>
          <p>Teste · cobertura · sessões</p>
        </div>

        <div>
          <div className="nav-group-label">Jornada</div>
          <nav className="nav">
            {opsLinks.map((link) => (
              <NavLink key={link.to} to={link.to} end={link.end}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="nav-group-label">Execução</div>
          <nav className="nav">
            {execLinks.map((link) => (
              <NavLink key={link.to} to={link.to}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="nav-group-label">Administração</div>
          <nav className="nav">
            {adminLinks.map((link) => (
              <NavLink key={link.to} to={link.to}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div>
          <div className="nav-group-label">Legado promo</div>
          <nav className="nav">
            {legadoLinks.map((link) => (
              <NavLink key={link.to} to={link.to}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-foot">
          3 casas Lucky Gaming · sem RNG · cap R${ops?.safety.max_lab_stake_brl ?? 5}
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
