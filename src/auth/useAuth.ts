import { useCallback, useEffect, useState } from 'react';
import {
  fetchMe,
  login as apiLogin,
  login2FA as apiLogin2FA,
  logout as apiLogout,
} from './api';

export type AuthState = {
  loading: boolean;
  user: string | null;
  error: string | null;
  pending2FA: string | null;
  login: (username: string, password: string) => Promise<'ok' | '2fa'>;
  verify2FA: (code: string) => Promise<void>;
  cancel2FA: () => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

export function useAuth(): AuthState {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending2FA, setPending2FA] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await fetchMe();
      setUser(me.user ?? null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      const res = await apiLogin(username, password);
      if (res.requires_2fa && res.pending_token) {
        setPending2FA(res.pending_token);
        setUser(null);
        return '2fa' as const;
      }
      setPending2FA(null);
      setUser(res.user ?? null);
      return 'ok' as const;
    } catch (e) {
      setUser(null);
      setPending2FA(null);
      setError(e instanceof Error ? e.message : 'Falha no login');
      throw e;
    }
  }, []);

  const verify2FA = useCallback(async (code: string) => {
    if (!pending2FA) {
      throw new Error('Sessão 2FA expirada — faça login novamente');
    }
    setError(null);
    try {
      const res = await apiLogin2FA(pending2FA, code);
      setPending2FA(null);
      setUser(res.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Código 2FA inválido');
      throw e;
    }
  }, [pending2FA]);

  const cancel2FA = useCallback(() => {
    setPending2FA(null);
    setError(null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setPending2FA(null);
    }
  }, []);

  return {
    loading,
    user,
    error,
    pending2FA,
    login,
    verify2FA,
    cancel2FA,
    logout,
    refresh,
  };
}
