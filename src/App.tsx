import { useEffect, useMemo, useState } from 'react';
import { KeyRound, LogOut, RefreshCw } from 'lucide-react';
import {
  SERVICES,
  CATEGORY_META,
  type ServiceCategory,
} from './data/services';
import { useServiceHealth } from './hooks/useServiceHealth';
import { CategoryIcon } from './components/Icons';
import { ServiceCard } from './components/ServiceCard';
import { TwoFAPanel } from './components/TwoFAPanel';
import { twoFAStatus } from './auth/api';
import { useAuth } from './auth/useAuth';
import { Login } from './pages/Login';

const ALL_CATEGORIES = Object.keys(CATEGORY_META) as ServiceCategory[];

export function App() {
  const auth = useAuth();

  if (auth.loading) {
    return (
      <div className="auth-boot">
        <div className="auth-boot-spinner" />
        <span>Verificando sessão…</span>
      </div>
    );
  }

  if (!auth.user) {
    return (
      <Login
        onLogin={auth.login}
        onVerify2FA={auth.verify2FA}
        onCancel2FA={auth.cancel2FA}
        pending2FA={Boolean(auth.pending2FA)}
        error={auth.error}
      />
    );
  }

  // After login (e.g. nginx auth_request → /console/?next=/go/open-webui)
  // Only follow gateway entry points — never OWUI internals (/error, /auth, /_app, …)
  const next = new URLSearchParams(window.location.search).get('next');
  const nextOk =
    !!next &&
    next.startsWith('/') &&
    !next.startsWith('//') &&
    (next.startsWith('/go/') || next.startsWith('/t/'));

  if (nextOk && next) {
    window.location.replace(next);
    return (
      <div className="auth-boot">
        <div className="auth-boot-spinner" />
        <span>Abrindo ferramenta…</span>
      </div>
    );
  }

  return <Hub user={auth.user} onLogout={auth.logout} />;
}

function Hub({ user, onLogout }: { user: string; onLogout: () => Promise<void> }) {
  const [filter, setFilter] = useState<ServiceCategory | 'all'>('all');
  const [search, setSearch] = useState('');
  const [show2FA, setShow2FA] = useState(false);
  const [twoFAOn, setTwoFAOn] = useState(false);
  const { health, loading, lastCheck, refresh } = useServiceHealth();

  useEffect(() => {
    void twoFAStatus()
      .then((s) => setTwoFAOn(s.enabled))
      .catch(() => setTwoFAOn(false));
  }, []);

  const webServices = SERVICES.filter((s) => s.type === 'web' || s.type === 'api');
  const onlineCount = webServices.filter((s) => health[s.id] === 'online').length;

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return SERVICES.filter((s) => {
      if (filter !== 'all' && s.category !== filter) return false;
      if (!q) return true;
      return (
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.tags.some((t) => t.toLowerCase().includes(q)) ||
        s.project.toLowerCase().includes(q)
      );
    });
  }, [filter, search]);

  const grouped = useMemo(() => {
    const map = new Map<ServiceCategory, typeof SERVICES>();
    for (const s of filtered) {
      const list = map.get(s.category) ?? [];
      list.push(s);
      map.set(s.category, list);
    }
    return ALL_CATEGORIES.filter((c) => map.has(c)).map((c) => ({
      category: c,
      services: map.get(c)!,
    }));
  }, [filtered]);

  const now = new Date().toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

  return (
    <div className="hub">
      <header className="hub-header">
        <a className="hub-brand" href="/console/" title="Iron Hub">
          <div className="hub-brand-icon">
            <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
              <path d="M8 22V10l8-4 8 4v12l-8 4-8-4z" stroke="#00D9FF" strokeWidth="1.5" />
            </svg>
          </div>
          <div>
            <h1>Iron Security</h1>
            <span>Command Hub v1.3 · gateway</span>
          </div>
        </a>
        <div className="hub-header-meta">
          <input
            className="search-input"
            type="search"
            placeholder="Buscar ferramenta..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <span className="hub-user" title="Sessão autenticada">
            {user}
          </span>
          <span
            className={`hub-2fa-badge ${twoFAOn ? 'hub-2fa-badge--on' : 'hub-2fa-badge--off'}`}
            title={twoFAOn ? '2FA ativo' : '2FA desativado — clique em 2FA para ativar'}
          >
            2FA {twoFAOn ? 'ON' : 'OFF'}
          </span>
          <span className="clock">{now}</span>
          <button
            className={`refresh-btn ${loading ? 'spinning' : ''}`}
            onClick={refresh}
            disabled={loading}
            type="button"
          >
            <RefreshCw size={14} strokeWidth={1.5} />
            Atualizar
          </button>
          <button
            className="refresh-btn"
            type="button"
            onClick={() => setShow2FA(true)}
            title="Configurar 2FA"
          >
            <KeyRound size={14} strokeWidth={1.5} />
            2FA
          </button>
          <button
            className="logout-btn"
            type="button"
            onClick={() => void onLogout()}
            title="Encerrar sessão"
          >
            <LogOut size={14} strokeWidth={1.5} />
            Sair
          </button>
        </div>
      </header>

      <TwoFAPanel
        open={show2FA}
        onClose={() => setShow2FA(false)}
        onStatusChange={setTwoFAOn}
      />

      <main className="hub-main">
        <section className="hero">
          <h2>Central de Operações</h2>
          <p>
            Acesso unificado via gateway autenticado. O browser fala só com o Hub;
            as ferramentas permanecem em loopback interno.
          </p>
        </section>

        <section className="stats-row">
          <div className="stat-card online">
            <div className="stat-value">{onlineCount}</div>
            <div className="stat-label">Serviços Online</div>
          </div>
          <div className="stat-card offline">
            <div className="stat-value">{webServices.length - onlineCount}</div>
            <div className="stat-label">Offline / Checking</div>
          </div>
          <div className="stat-card total">
            <div className="stat-value">{SERVICES.length}</div>
            <div className="stat-label">Total Ferramentas</div>
          </div>
          <div className="stat-card categories">
            <div className="stat-value">{ALL_CATEGORIES.length}</div>
            <div className="stat-label">Verticais</div>
          </div>
        </section>

        <nav className="filter-bar">
          <button
            type="button"
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Todas
          </button>
          {ALL_CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              className={`filter-btn ${filter === cat ? 'active' : ''}`}
              onClick={() => setFilter(cat)}
            >
              <CategoryIcon category={cat} size={12} />
              {CATEGORY_META[cat].label}
            </button>
          ))}
        </nav>

        {grouped.map(({ category, services }) => {
          const meta = CATEGORY_META[category];
          return (
            <section key={category} className="category-section">
              <div className="category-header">
                <span className="category-dot" style={{ background: meta.color }} />
                <h3>{meta.label}</h3>
                <span>{meta.description}</span>
              </div>
              <div className="services-grid">
                {services.map((service) => (
                  <ServiceCard
                    key={service.id}
                    service={service}
                    status={health[service.id] ?? 'unknown'}
                  />
                ))}
              </div>
            </section>
          );
        })}

        {grouped.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px', color: 'var(--color-text-muted)' }}>
            Nenhuma ferramenta encontrada para &quot;{search}&quot;
          </div>
        )}
      </main>

      <footer className="hub-footer">
        <span>Iron Security — Auth → Hub → Ferramenta</span>
        <span>
          {lastCheck
            ? `Health check: ${new Date(lastCheck).toLocaleTimeString('pt-BR')}`
            : 'Aguardando health check...'}
        </span>
      </footer>
    </div>
  );
}
