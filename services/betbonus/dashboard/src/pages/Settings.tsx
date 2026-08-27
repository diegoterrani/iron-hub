import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Toast } from '../components/Toast'

type Cred = {
  platform: string
  email: string
  label: string
  has_token: boolean
  token_preview: string
  updated_at: string
}

export function Settings() {
  const [creds, setCreds] = useState<Cred[]>([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)
  const [session, setSession] = useState<string>('')

  const refresh = async () => {
    setCreds(await api.credentials())
  }

  useEffect(() => {
    refresh().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const fourplay = creds.find((c) => c.platform === '4play')

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Auth / Tokens</h2>
          <p>
            Entre com user/senha da 4Play ou cole o Bearer token para liberar{' '}
            <code>GET /bonus</code> (bônus da conta).
          </p>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <h3>4Play.game — Login</h3>
          <p className="muted">
            Chama <code>POST /api/v1/auth/login</code> e salva só o token em{' '}
            <code>data/credentials.json</code> (mode 600).
          </p>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seu@email.com"
                autoComplete="username"
              />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <button
              className="btn btn-accent"
              disabled={busy || !email || !password}
              onClick={async () => {
                setBusy(true)
                try {
                  const res = await api.loginPlatform('4play', { email, password })
                  setPassword('')
                  setSession(JSON.stringify(res.session, null, 2))
                  setToast({ message: 'Login OK — token salvo' })
                  await refresh()
                } catch (e) {
                  setToast({ message: (e as Error).message, error: true })
                } finally {
                  setBusy(false)
                }
              }}
            >
              {busy ? 'Entrando…' : 'Login e salvar token'}
            </button>
          </div>
        </div>

        <div className="panel">
          <h3>Ou cole o token do browser</h3>
          <p className="muted">
            Em 4play.game logado → DevTools → Application → Local Storage → chave{' '}
            <strong>token</strong>.
          </p>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <div className="field">
              <label>Bearer token</label>
              <textarea
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="eyJhbGciOi…"
                style={{ minHeight: 110 }}
              />
            </div>
            <div className="actions">
              <button
                className="btn btn-primary"
                disabled={busy || !token.trim()}
                onClick={async () => {
                  setBusy(true)
                  try {
                    await api.saveToken('4play', { token: token.trim(), email })
                    setToken('')
                    setToast({ message: 'Token salvo' })
                    await refresh()
                  } catch (e) {
                    setToast({ message: (e as Error).message, error: true })
                  } finally {
                    setBusy(false)
                  }
                }}
              >
                Salvar token
              </button>
              <button
                className="btn btn-ghost"
                disabled={busy || !fourplay?.has_token}
                onClick={async () => {
                  setBusy(true)
                  try {
                    const res = await api.validateCredentials('4play')
                    setSession(JSON.stringify(res.session, null, 2))
                    setToast({ message: 'Token válido' })
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
                disabled={busy || !fourplay?.has_token}
                onClick={async () => {
                  await api.deleteCredentials('4play')
                  setSession('')
                  setToast({ message: 'Token removido' })
                  await refresh()
                }}
              >
                Remover
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <h3>Status</h3>
        {fourplay?.has_token ? (
          <p>
            <span className="badge good">conectado</span> {fourplay.email || '4play'} · preview{' '}
            <code>{fourplay.token_preview}</code> · atualizado{' '}
            {new Date(fourplay.updated_at).toLocaleString()}
          </p>
        ) : (
          <p className="muted">Nenhum token 4Play salvo — scrape live só pega promoções públicas.</p>
        )}
        <p className="muted" style={{ marginTop: 10 }}>
          Depois de autenticar: Pipeline → <strong>Testar 4Play.game</strong> para capturar promoções
          públicas + bônus da conta (`/bonus`).
        </p>
        {session && <pre className="session-pre">{session}</pre>}
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
