import { useState, type FormEvent } from 'react';
import { KeyRound, Lock, Shield, User } from 'lucide-react';

type LoginProps = {
  onLogin: (username: string, password: string) => Promise<'ok' | '2fa'>;
  onVerify2FA: (code: string) => Promise<void>;
  onCancel2FA: () => void;
  pending2FA: boolean;
  error: string | null;
};

export function Login({
  onLogin,
  onVerify2FA,
  onCancel2FA,
  pending2FA,
  error,
}: LoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handlePasswordSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    if (!username.trim() || !password) {
      setLocalError('Informe usuário e senha');
      return;
    }
    setSubmitting(true);
    try {
      await onLogin(username.trim(), password);
      setCode('');
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Falha na autenticação');
    } finally {
      setSubmitting(false);
    }
  };

  const handle2FASubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    const cleaned = code.replace(/\s+/g, '');
    if (!/^\d{6}$/.test(cleaned)) {
      setLocalError('Informe o código de 6 dígitos do Authenticator');
      return;
    }
    setSubmitting(true);
    try {
      await onVerify2FA(cleaned);
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Código 2FA inválido');
    } finally {
      setSubmitting(false);
    }
  };

  const displayError = localError || error;

  return (
    <div className="login-page">
      <div className="login-atmosphere" aria-hidden="true" />
      <div className="login-grid" aria-hidden="true" />

      <main className="login-shell">
        <div className="login-brand">
          <div className="login-brand-mark">
            <Shield size={22} strokeWidth={1.5} />
          </div>
          <h1>Iron Security</h1>
          <p>Command Hub — acesso autenticado</p>
        </div>

        {!pending2FA ? (
          <form className="login-card" onSubmit={handlePasswordSubmit} autoComplete="on">
            <div className="login-card-head">
              <Lock size={16} strokeWidth={1.5} />
              <span>Autenticação local</span>
            </div>

            <label className="login-field">
              <span>Usuário</span>
              <div className="login-input-wrap">
                <User size={14} strokeWidth={1.5} />
                <input
                  type="text"
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="iron"
                  disabled={submitting}
                  autoFocus
                />
              </div>
            </label>

            <label className="login-field">
              <span>Senha</span>
              <div className="login-input-wrap">
                <Lock size={14} strokeWidth={1.5} />
                <input
                  type="password"
                  name="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  disabled={submitting}
                />
              </div>
            </label>

            {displayError && <div className="login-error">{displayError}</div>}

            <button className="login-submit" type="submit" disabled={submitting}>
              {submitting ? 'Autenticando…' : 'Continuar'}
            </button>

            <p className="login-foot">
              Fluxo: Autenticação → Hub → Ferramenta. Portas internas não são expostas ao browser.
            </p>
          </form>
        ) : (
          <form className="login-card" onSubmit={handle2FASubmit} autoComplete="one-time-code">
            <div className="login-card-head">
              <KeyRound size={16} strokeWidth={1.5} />
              <span>Verificação 2FA</span>
            </div>

            <p className="login-2fa-hint">
              Abra o app Authenticator e informe o código de 6 dígitos.
            </p>

            <label className="login-field">
              <span>Código TOTP</span>
              <div className="login-input-wrap">
                <KeyRound size={14} strokeWidth={1.5} />
                <input
                  type="text"
                  name="totp"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/[^\d]/g, '').slice(0, 6))}
                  placeholder="000000"
                  disabled={submitting}
                  autoFocus
                  className="login-totp-input"
                />
              </div>
            </label>

            {displayError && <div className="login-error">{displayError}</div>}

            <button className="login-submit" type="submit" disabled={submitting}>
              {submitting ? 'Validando…' : 'Entrar no Hub'}
            </button>

            <button
              type="button"
              className="login-secondary"
              disabled={submitting}
              onClick={() => {
                setCode('');
                setLocalError(null);
                onCancel2FA();
              }}
            >
              Voltar
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
