export type MeResponse = { ok: boolean; user?: string; error?: string };

export type LoginResponse = {
  ok: boolean;
  user?: string;
  requires_2fa?: boolean;
  pending_token?: string;
  error?: string;
};

export type TwoFAStatus = { ok: boolean; enabled: boolean };
export type TwoFASetup = {
  ok: boolean;
  secret: string;
  otpauth_url: string;
  qr_png_base64: string;
  issuer: string;
  account: string;
};

async function hubFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  });
  const data = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || `HTTP ${res.status}`);
  }
  return data;
}

export function fetchMe() {
  return hubFetch<MeResponse>('/hub/api/me');
}

export function login(username: string, password: string) {
  return hubFetch<LoginResponse>('/hub/api/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}

export function login2FA(pendingToken: string, code: string) {
  return hubFetch<{ ok: boolean; user: string }>('/hub/api/login/2fa', {
    method: 'POST',
    body: JSON.stringify({ pending_token: pendingToken, code }),
  });
}

export function logout() {
  return hubFetch<{ ok: boolean }>('/hub/api/logout', { method: 'POST' });
}

export function twoFAStatus() {
  return hubFetch<TwoFAStatus>('/hub/api/2fa/status');
}

export function twoFASetup() {
  return hubFetch<TwoFASetup>('/hub/api/2fa/setup', { method: 'POST' });
}

export function twoFAEnable(code: string) {
  return hubFetch<{ ok: boolean; enabled: boolean }>('/hub/api/2fa/enable', {
    method: 'POST',
    body: JSON.stringify({ code }),
  });
}

export function twoFADisable(password: string, code: string) {
  return hubFetch<{ ok: boolean; enabled: boolean }>('/hub/api/2fa/disable', {
    method: 'POST',
    body: JSON.stringify({ password, code }),
  });
}
