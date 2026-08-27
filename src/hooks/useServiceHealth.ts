import { useCallback, useEffect, useState } from 'react';
import type { ServiceStatus } from '../data/services';

export type HealthMap = Record<string, ServiceStatus>;

interface HealthResponse {
  services: Record<string, { status: ServiceStatus; latency_ms?: number }>;
  checked_at: string;
}

export function useServiceHealth(intervalMs = 30_000) {
  const [health, setHealth] = useState<HealthMap>({});
  const [loading, setLoading] = useState(false);
  const [lastCheck, setLastCheck] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/hub/api/health', { credentials: 'include' });
      if (res.status === 401) {
        setHealth({});
        return;
      }
      if (!res.ok) throw new Error('health check failed');
      const data: HealthResponse = await res.json();
      const map: HealthMap = {};
      for (const [id, entry] of Object.entries(data.services)) {
        map[id] = entry.status;
      }
      setHealth(map);
      setLastCheck(data.checked_at);
    } catch {
      setHealth({});
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => clearInterval(timer);
  }, [refresh, intervalMs]);

  return { health, loading, lastCheck, refresh };
}
