import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { OpsStatus } from '../../types'
import { HOUSE_LABEL } from '../../lib/casino'

interface CredRow {
  platform: string
  email: string
  document: string
  label: string
  has_token: boolean
  token_preview: string
  updated_at: string
}

export default function AuthView() {
  const [creds, setCreds] = useState<CredRow[]>([])
  const [ops, setOps] = useState<OpsStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.credentials(), api.opsStatus()])
      .then(([c, o]) => {
        setCreds(c)
        setOps(o)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [document, setDocument] = useState('')
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [loginMsg, setLoginMsg] = useState<string | null>(null)
  const [loggingIn, setLoggingIn] = useState(false)

  const handleLogin = async () => {
    setLoggingIn(true)
    setLoginMsg(null)
    try {
      await api.loginPlatform(platform, { email, password, document })
      setLoginMsg('Login successful')
      const [c] = await Promise.all([api.credentials(), api.opsStatus().then(setOps)])
      setCreds(c)
    } catch (e) {
      setLoginMsg(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoggingIn(false)
    }
  }

  if (loading)
    return <div className="text-[#4a5c6e] text-[12px] font-mono">Loading credentials…</div>
  if (error) return <div className="text-[#ff3b4d] text-[12px] font-mono">{error}</div>

  return (
    <div className="space-y-4">
      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--green" />
          Stored Credentials
        </div>
        <div className="panel-body">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-[#6b7f94] border-b border-[#1e2d3d]">
                <th className="pb-2 pr-4">Platform</th>
                <th className="pb-2 pr-4">Email</th>
                <th className="pb-2 pr-4">Document</th>
                <th className="pb-2 pr-4">Token</th>
                <th className="pb-2 pr-4">Preview</th>
                <th className="pb-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {creds.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-3 text-[#4a5c6e] italic">
                    No credentials stored
                  </td>
                </tr>
              )}
              {creds.map((c) => (
                <tr key={c.platform} className="border-b border-[#1e2d3d30]">
                  <td className="py-2 pr-4 font-mono text-[#00e5ff]">{c.platform}</td>
                  <td className="py-2 pr-4">{c.email}</td>
                  <td className="py-2 pr-4 font-mono text-[#4a5c6e]">{c.document || '—'}</td>
                  <td className="py-2 pr-4">
                    <span
                      className="status-dot"
                      style={{ background: c.has_token ? '#00ff88' : '#374151' }}
                    />
                  </td>
                  <td className="py-2 pr-4 font-mono text-[#4a5c6e]">{c.token_preview}</td>
                  <td className="py-2 text-[#4a5c6e]">
                    {new Date(c.updated_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="status-dot status-dot--cyan" />
          Platform Login
        </div>
        <div className="panel-body space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <div>
              <span className="label">Platform</span>
              <select
                className="input w-full"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
              >
                {Object.entries(HOUSE_LABEL).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <span className="label">Email</span>
              <input
                className="input w-full"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
              />
            </div>
            <div>
              <span className="label">Document (CPF)</span>
              <input
                className="input w-full"
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                placeholder="000.000.000-00"
              />
            </div>
            <div>
              <span className="label">Password</span>
              <input
                className="input w-full"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn btn--primary" onClick={handleLogin} disabled={loggingIn}>
              {loggingIn ? 'Authenticating…' : 'Login'}
            </button>
            {loginMsg && (
              <span className="text-[11px] font-mono text-[#00ff88]">{loginMsg}</span>
            )}
          </div>
        </div>
      </div>

      {ops?.houses && (
        <div className="panel">
          <div className="panel-header">
            <span className="status-dot status-dot--dim" />
            Session Status
          </div>
          <div className="panel-body">
            <div className="grid grid-cols-3 gap-3">
              {ops.houses.map((h) => (
                <div key={h.id} className="border border-[#1e2d3d] rounded-[2px] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-[#c8d6e5]">
                      {HOUSE_LABEL[h.id] || h.id}
                    </span>
                    <span
                      className="status-dot"
                      style={{
                        background:
                          h.session_ok === false ? '#ff3b4d' : h.has_token ? '#00ff88' : '#374151',
                      }}
                    />
                  </div>
                  <div className="text-[10px] text-[#6b7f94] mt-2">
                    {h.email || 'no email'}
                  </div>
                  {h.session_note && (
                    <div className="text-[10px] text-[#ffb300] mt-1">{h.session_note}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
