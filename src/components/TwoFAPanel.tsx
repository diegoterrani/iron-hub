import { useCallback, useEffect, useState } from 'react';
import { KeyRound, ShieldCheck, X } from 'lucide-react';
import {
  twoFADisable,
  twoFAEnable,
  twoFASetup,
  twoFAStatus,
  type TwoFASetup,
} from '../auth/api';

type Props = {
  open: boolean;
  onClose: () => void;
  onStatusChange?: (enabled: boolean) => void;
};

export function TwoFAPanel({ open, onClose, onStatusChange }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [setup, setSetup] = useState<TwoFASetup | null>(null);
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const st = await twoFAStatus();
      setEnabled(st.enabled);
      onStatusChange?.(st.enabled);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao ler status 2FA');
    } finally {
      setLoading(false);
    }
  }, [onStatusChange]);

  useEffect(() => {
    if (open) {
      setSetup(null);
      setCode('');
      setPassword('');
      setOkMsg(null);
      void refresh();
    }
  }, [open, refresh]);

  if (!open) return null;

  async function startSetup() {
    setBusy(true);
    setError(null);
    setOkMsg(null);
    try {
      const res = await twoFASetup();
      setSetup(res);
      setOkMsg(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha no setup');
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnable() {
    const cleaned = code.replace(/\s+/g, '');
    if (!/^\d{6}$/.test(cleaned)) {
      setError('Informe o código de 6 dígitos do app');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await twoFAEnable(cleaned);
      if (!res.enabled) {
        throw new Error('Servidor não confirmou ativação');
      }
      setSetup(null);
      setCode('');
      setEnabled(true);
      onStatusChange?.(true);
      setOkMsg('2FA ATIVO. Faça logout e login de novo — deve pedir o código.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao ativar');
    } finally {
      setBusy(false);
    }
  }

  async function confirmDisable() {
    const cleaned = code.replace(/\s+/g, '');
    if (!password || !/^\d{6}$/.test(cleaned)) {
      setError('Informe senha e código 2FA atuais');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await twoFADisable(password, cleaned);
      setEnabled(false);
      onStatusChange?.(false);
      setCode('');
      setPassword('');
      setOkMsg('2FA desativado.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao desativar');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="modal-head">
          <div className="modal-title">
            <ShieldCheck size={16} strokeWidth={1.5} />
            <span>Autenticação 2FA (TOTP)</span>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Fechar">
            <X size={16} />
          </button>
        </div>

        {loading ? (
          <p className="muted">Carregando…</p>
        ) : (
          <>
            <p className="modal-status">
              Status:{' '}
              <strong className={enabled ? 'ok' : 'off'}>
                {enabled ? 'Ativo' : 'Desativado'}
              </strong>
            </p>

            {!enabled && !setup && (
              <>
                <ol className="twofa-steps">
                  <li>Gere o QR e escaneie no Authenticator</li>
                  <li>Digite o código de 6 dígitos e confirme</li>
                  <li>Só depois o 2FA fica obrigatório no login</li>
                </ol>
                <button type="button" className="login-submit" disabled={busy} onClick={() => void startSetup()}>
                  <KeyRound size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                  1. Gerar QR / secret
                </button>
              </>
            )}

            {setup && (
              <div className="twofa-setup">
                <p className="twofa-step-badge">Passo 2 de 2 — confirme o código</p>
                <img
                  className="twofa-qr"
                  alt="QR Code 2FA"
                  src={`data:image/png;base64,${setup.qr_png_base64}`}
                />
                <p className="muted">Escaneie o QR (ou digite o secret):</p>
                <code className="twofa-secret">{setup.secret}</code>
                <label className="login-field">
                  <span>Código de 6 dígitos do app</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/[^\d]/g, '').slice(0, 6))}
                    placeholder="000000"
                    disabled={busy}
                    autoFocus
                  />
                </label>
                <button type="button" className="login-submit" disabled={busy || code.length !== 6} onClick={() => void confirmEnable()}>
                  2. Confirmar e ativar 2FA
                </button>
                <p className="muted">Escanear o QR sozinho não ativa — é obrigatório confirmar o código.</p>
              </div>
            )}

            {enabled && (
              <div className="twofa-setup">
                <p className="muted">Para desativar, confirme senha + código atual do Authenticator.</p>
                <label className="login-field">
                  <span>Senha do Hub</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={busy}
                  />
                </label>
                <label className="login-field">
                  <span>Código 2FA</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/[^\d]/g, '').slice(0, 6))}
                    placeholder="000000"
                    disabled={busy}
                  />
                </label>
                <button type="button" className="logout-btn" disabled={busy} onClick={() => void confirmDisable()}>
                  Desativar 2FA
                </button>
              </div>
            )}

            {error && <div className="login-error">{error}</div>}
            {okMsg && <div className="login-ok">{okMsg}</div>}
          </>
        )}
      </div>
    </div>
  );
}
