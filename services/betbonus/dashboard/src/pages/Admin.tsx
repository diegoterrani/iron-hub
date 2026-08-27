import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Toast } from '../components/Toast'
import { HOUSE_IDS, HOUSE_LABEL } from '../lib/casino'
import type { OpsHouseStatus } from '../types'

const PLATFORMS = HOUSE_IDS.map((id) => ({
  id,
  label: HOUSE_LABEL[id],
  needsRefresh: id === '4play_bet_br',
  canLogin: id === '4play',
}))

export function Admin() {
  const [houses, setHouses] = useState<OpsHouseStatus[]>([])
  const [token, setToken] = useState<Record<string, string>>({})
  const [refresh, setRefresh] = useState<Record<string, string>>({})
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [llm, setLlm] = useState<{
    configured: boolean
    chat_model: string
    name?: string
    models?: Array<{ id: string; name: string; description: string }>
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const load = async () => {
    const [ops, status] = await Promise.all([api.opsStatus(), api.llmStatus()])
    setHouses(ops.houses)
    setLlm(status)
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const save = async (platform: string) => {
    setBusy(true)
    try {
      await api.saveToken(platform, {
        token: (token[platform] || '').trim(),
        refresh_token: (refresh[platform] || '').trim() || undefined,
      })
      setToken((t) => ({ ...t, [platform]: '' }))
      setRefresh((t) => ({ ...t, [platform]: '' }))
      setToast({ message: `Token ${HOUSE_LABEL[platform]} salvo` })
      await load()
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Administração</h2>
          <p>
            Passo 1 da jornada de teste: cole o token da conta de lab. Sem sessão viva o PROBE da
            casa sai BLOCKED. Tokens nunca vão para o relatório.
          </p>
        </div>
        <div className="actions">
          <Link className="btn btn-ghost" to="/">
            Voltar à jornada
          </Link>
        </div>
      </div>

      <div className="admin-grid">
        {PLATFORMS.map((p) => {
          const st = houses.find((h) => h.id === p.id)
          return (
            <div className="panel" key={p.id}>
              <h3>{p.label}</h3>
              <p className="muted">
                {st?.session_ok ? (
                  <span className="badge good">sessão viva</span>
                ) : st?.has_token ? (
                  <span className="badge warn">token expirado</span>
                ) : (
                  <span className="badge critical">sem sessão</span>
                )}{' '}
                {st?.updated_at ? new Date(st.updated_at).toLocaleString() : ''}
                {st?.session_note && !st.session_ok ? (
                  <span className="muted"> — {st.session_note}</span>
                ) : null}
              </p>
              <div className="form-grid" style={{ marginTop: 12 }}>
                <div className="field">
                  <label>Bearer / token</label>
                  <textarea
                    value={token[p.id] || ''}
                    onChange={(e) => setToken((t) => ({ ...t, [p.id]: e.target.value }))}
                    placeholder="colar token (sem prefixo Bearer se a API já espera cru)"
                  />
                </div>
                {p.needsRefresh && (
                  <div className="field">
                    <label>refreshToken</label>
                    <textarea
                      value={refresh[p.id] || ''}
                      onChange={(e) => setRefresh((t) => ({ ...t, [p.id]: e.target.value }))}
                      placeholder="localStorage.refreshToken"
                    />
                  </div>
                )}
                <div className="actions">
                  <button
                    className="btn btn-primary"
                    disabled={busy || !(token[p.id] || '').trim()}
                    onClick={() => save(p.id)}
                  >
                    Salvar
                  </button>
                  <button
                    className="btn btn-ghost"
                    disabled={busy || !st?.has_token}
                    onClick={async () => {
                      setBusy(true)
                      try {
                        await api.validateCredentials(p.id)
                        setToast({ message: `${p.label} válido` })
                      } catch (e) {
                        setToast({ message: (e as Error).message, error: true })
                      } finally {
                        setBusy(false)
                      }
                    }}
                  >
                    Validar
                  </button>
                  <button
                    className="btn btn-danger"
                    disabled={busy || !st?.has_token}
                    onClick={async () => {
                      await api.deleteCredentials(p.id)
                      setToast({ message: 'Removido' })
                      await load()
                    }}
                  >
                    Remover
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <h3>LLM planner</h3>
        <p className="muted">
          {llm?.configured ? (
            <>
              <span className="badge good">ON</span> {llm.name || llm.chat_model}
            </>
          ) : (
            <span className="badge critical">OFF</span>
          )}
        </p>
        <div className="actions" style={{ marginTop: 12 }}>
          {(llm?.models || []).map((m) => (
            <button
              key={m.id}
              className={`btn ${llm?.chat_model === m.id ? 'btn-accent' : 'btn-ghost'}`}
              disabled={busy}
              onClick={async () => {
                setBusy(true)
                try {
                  const next = await api.llmSetModel(m.id)
                  setLlm((prev) => ({
                    configured: next.configured,
                    chat_model: next.chat_model,
                    name: next.name,
                    models: next.models || prev?.models,
                  }))
                  setToast({ message: `Modelo ${next.name || next.chat_model}` })
                } catch (e) {
                  setToast({ message: (e as Error).message, error: true })
                } finally {
                  setBusy(false)
                }
              }}
            >
              {m.name}
            </button>
          ))}
          <button
            className="btn btn-ghost"
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              try {
                const ping = await api.llmPing()
                setToast({ message: ping.ok ? `ping ${ping.reply}` : ping.error || 'falhou', error: !ping.ok })
              } catch (e) {
                setToast({ message: (e as Error).message, error: true })
              } finally {
                setBusy(false)
              }
            }}
          >
            Ping
          </button>
        </div>
      </div>

      {PLATFORMS.some((p) => p.canLogin) && (
        <div className="panel" style={{ marginTop: 14 }}>
          <h3>Login 4play.game</h3>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <div className="field">
              <label>Email</label>
              <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <button
              className="btn btn-accent"
              disabled={busy || !email || !password}
              onClick={async () => {
                setBusy(true)
                try {
                  await api.loginPlatform('4play', { email, password })
                  setPassword('')
                  setToast({ message: 'Login 4play.game OK' })
                  await load()
                } catch (e) {
                  setToast({ message: (e as Error).message, error: true })
                } finally {
                  setBusy(false)
                }
              }}
            >
              Login
            </button>
          </div>
        </div>
      )}

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
