import { withGateway } from '../lib/gateway'
import type {
  ActivityEvent,
  AbuseScoreItem,
  BonusOffer,
  ConversionSnapshot,
  JourneyLogEvent,
  JourneyLogLevel,
  JourneySession,
  JourneySessionSummary,
  PlatformInfo,
  ScrapeUrlResponse,
  Stats,
  WithdrawOracleResult,
  IntegrityCatalog,
  IntegrityResult,
  IntegrityRunSummary,
  OpsStatus,
  CatalogGame,
} from '../types'

async function fetchMarkdown(path: string): Promise<{ text: string; filename: string; status: number }> {
  const res = await fetch(withGateway(path), { credentials: 'same-origin' })
  const text = await res.text()
  const cd = res.headers.get('content-disposition') || ''
  const named = cd.match(/filename="?([^";]+)"?/i)
  return {
    text,
    filename: (named?.[1] || path.split('/').pop() || 'report.md').trim(),
    status: res.status,
  }
}

function looksLikeApiMiss(status: number, body: string): boolean {
  if (status === 200) return false
  return /API route not found/i.test(body) || status === 404
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(withGateway(path), {
    ...init,
    credentials: 'same-origin',
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  stats: () => request<Stats>('/api/stats'),
  platforms: () => request<PlatformInfo[]>('/api/platforms'),
  bonuses: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') qs.set(k, String(v))
    })
    const suffix = qs.toString() ? `?${qs}` : ''
    return request<BonusOffer[]>(`/api/bonuses${suffix}`)
  },
  deleteBonus: (id: string) =>
    request<{ deleted: boolean }>(`/api/bonuses/${id}`, { method: 'DELETE' }),
  clearBonuses: () => request<{ deleted: number }>('/api/bonuses', { method: 'DELETE' }),
  analyze: (body: { platform: string; text: string; title?: string; persist?: boolean }) =>
    request<BonusOffer>('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  runFixture: (platforms: string[], fixture = 'sample_promos.html') =>
    request<BonusOffer[]>('/api/pipeline/fixture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platforms, fixture }),
    }),
  runHtml: (platform: string, html: string) =>
    request<BonusOffer[]>('/api/pipeline/html', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, html }),
    }),
  runUrl: (platform: string, url: string, delay = 1.5) =>
    request<ScrapeUrlResponse>('/api/pipeline/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, url, delay }),
    }),
  runLive: (platform: string) =>
    request<ScrapeUrlResponse>('/api/pipeline/live', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform }),
    }),
  credentials: () =>
    request<
      Array<{
        platform: string
        email: string
        label: string
        has_token: boolean
        token_preview: string
        updated_at: string
      }>
    >('/api/credentials'),
  saveToken: (
    platform: string,
    body: { token: string; refresh_token?: string; email?: string; label?: string },
  ) =>
    request(`/api/credentials/${platform}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, ...body }),
    }),
  deleteCredentials: (platform: string) =>
    request(`/api/credentials/${platform}`, { method: 'DELETE' }),
  loginPlatform: (platform: string, body: { email: string; password: string; label?: string }) =>
    request<{ ok: boolean; credentials: unknown; session: unknown }>(
      `/api/credentials/${platform}/login`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, ...body }),
      },
    ),
  validateCredentials: (platform: string) =>
    request<{ ok: boolean; session?: unknown }>(`/api/credentials/${platform}/validate`, {
      method: 'POST',
    }),
  wallet: () =>
    request<{
      total_entries: number
      credited: number
      totals_by_currency: Record<string, number>
      note?: string
      house_wallet?: {
        connected?: boolean
        balance?: string | number
        bonus?: string | number
        rollover?: string | number
        error?: string
      }
      items: Array<{
        id: string
        platform: string
        title: string
        amount: number
        currency: string
        source: string
        status: string
        created_at: string
      }>
    }>('/api/wallet'),
  creditWallet: (body: {
    platform: string
    items: Array<{
      bonus_id?: string
      title: string
      amount: number
      currency: string
      source: string
      note?: string
    }>
  }) =>
    request<{
      ok: boolean
      credited: number
      wallet: {
        totals_by_currency: Record<string, number>
        credited: number
      }
    }>('/api/wallet/credit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  clearWallet: () => request<{ deleted: number }>('/api/wallet', { method: 'DELETE' }),
  abuseSnapshot: (platform = '4play') =>
    request<ConversionSnapshot>(`/api/abuse/snapshot?platform=${encodeURIComponent(platform)}`),
  abuseScore: (body: { offer_ids?: string[]; offers?: BonusOffer[]; platform?: string }) =>
    request<{ count: number; items: AbuseScoreItem[] }>('/api/abuse/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  abuseEvaluate: (body: { offer_ids?: string[]; offers?: BonusOffer[]; platform?: string }) =>
    request<{
      conversion: ConversionSnapshot
      abuse: { count: number; items: AbuseScoreItem[] }
      game_bonus_risk?: {
        count: number
        critical: number
        high: number
        focus: string
        items: Array<{
          id: string
          title: string
          severity: string
          rationale: string
          test_idea: string
          offer_id?: string
          offer_title?: string
        }>
        wallet_signal?: {
          id: string
          title: string
          severity: string
          rationale: string
          test_idea: string
        } | null
      }
      house: {
        min_withdraw?: number | null
        max_withdraw?: number | null
        withdraw_methods: string[]
        currency?: string
        note?: string
      }
      verdict?: { ok: boolean; status: string; note: string; redteam_success: boolean }
    }>('/api/abuse/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  abuseWithdraw: (body: {
    platform?: string
    amount?: number
    confirm_real_withdraw: boolean
    method?: 'tft' | 'dtr' | 'PIX' | 'pix' | 'preflight'
    phone?: string
    iban?: string
    max_amount?: number
    preflight_only?: boolean
    use_max_available?: boolean
  }) =>
    request<WithdrawOracleResult>('/api/abuse/oracle/withdraw', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_max_available: true, ...body }),
    }),
  abuseFindings: (limit = 50) => request<unknown[]>(`/api/abuse/findings?limit=${limit}`),
  abuseGamesHighEv: (platform = 'pagol_bet_br', maxGames = 60) =>
    request<{
      count: number
      term_hits: Record<string, number>
      games: Array<{
        game_id: number
        name: string
        slug?: string
        provider?: string
        high_ev?: boolean
        matched_terms?: string[]
        basic?: Record<string, unknown>
      }>
      note?: string
    }>(`/api/abuse/games/high-ev?platform=${encodeURIComponent(platform)}&max_games=${maxGames}`),
  abuseGamesProbe: (body: {
    platform?: string
    limit?: number
    include_bonus_flag?: boolean
  }) =>
    request<{
      probe_kind: string
      note: string
      probed: number
      discovery_count?: number
      term_hits?: Record<string, number>
      wallet_before?: { balance: number; bonus: number }
      wallet_after?: { balance: number; bonus: number }
      wallet_unchanged?: boolean
      probes: Array<{
        game_id: number
        name: string
        slug?: string
        provider?: string
        launches: Array<{
          ok: boolean
          mode: string
          use_bonus_balance?: boolean | null
          salsa_game?: string
          salsa_type?: string
          salsa_balance_brl?: number
          error?: string
        }>
      }>
      findings: Array<{
        id: string
        severity: string
        title: string
        rationale?: string
        test_idea?: string
      }>
    }>('/api/abuse/games/probe-contribution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  abuseBonusMultiplier: (body: {
    platform?: string
    promocode?: string
    game_id?: number
    stake_brl?: number
    confirm_redeem?: boolean
    confirm_real_bet?: boolean
    use_bonus_balance?: boolean
    poll_seconds?: number
  }) =>
    request<{
      lab: string
      ok: boolean
      auto_bet_implemented: boolean
      auto_bet_note: string
      stake_brl: number
      bet_armed: boolean
      gates: string[]
      provider_url?: string
      salsa_url?: string
      available_for_stake?: number
      wallet_start?: { balance: number; bonus: number }
      wallet_end?: { balance: number; bonus: number }
      poll?: { changed?: boolean; balance_delta?: number; bonus_delta?: number }
      findings: Array<{ id: string; severity: string; title: string; rationale?: string }>
      steps: Array<Record<string, unknown>>
    }>('/api/abuse/games/bonus-multiplier', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  abuseAutoJourney: (body: {
    platform?: string
    session_id?: string
    exhaust_mode?: boolean
    confirm_redeem?: boolean
    confirm_real_withdraw?: boolean
    confirm_real_bet?: boolean
    settle_withdraw?: boolean
    settle_timeout_s?: number
    promocode_limit?: number
    llm_limit?: number
    run_deep_attack?: boolean
    poll_seconds?: number
    persist_findings?: boolean
  }) =>
    request<{
      ok: boolean
      run_id: string
      session_id?: string
      stuck_point: string
      automation_goal_met: boolean
      report_md_path?: string
      report_latest_md?: string
      report_markdown?: string
      report_filename?: string
      diagnosis?: {
        summary?: string
        stuck_point?: string
        secondary_blockers?: string[]
        pix_materialized?: boolean
        balance_delta?: number
        bonus_delta?: number
      }
      remediation?: {
        stuck_point?: string
        dev_instructions?: string[]
        crm_instructions?: string[]
        backlog?: Array<Record<string, unknown>>
      }
      steps: Array<{
        id: string
        title: string
        mode: string
        ok: boolean
        note?: string
      }>
    }>('/api/abuse/auto-journey/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  downloadAutoJourneyLatestMd: async () => {
    const res = await fetch(withGateway('/api/abuse/auto-journey/latest.md'), {
      credentials: 'same-origin',
    })
    if (!res.ok) {
      throw new Error((await res.text()) || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'betbonus-auto-journey-latest.md'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return { ok: true as const }
  },
  abuseKillChainMatrix: (body: {
    platform?: string
    promocode?: string
    confirm_redeem?: boolean
    confirm_real_withdraw?: boolean
    settle_withdraw?: boolean
    settle_timeout_s?: number
    probe_high_ev?: boolean
    probe_slots?: boolean
    arm_wager_poll?: boolean
    poll_seconds?: number
    high_ev_limit?: number
    slots_limit?: number
    persist_findings?: boolean
  }) =>
    request<{
      ok: boolean
      run_id: string
      report_path?: string
      report_md_path?: string
      verdict: {
        bonus_to_cash_path_clear: boolean
        pix_materialized: boolean
        dominant_blocker: string
        vuln_count: number
        summary: string
      }
      coverage: {
        automated_stages: string[]
        semi_auto_stages: string[]
        manual_stages: string[]
        blocked_or_failed: string[]
        not_automatable_yet: string[]
      }
      stages: Array<{
        id: string
        title: string
        mode: string
        ok: boolean
        severity?: string
        vulnerability?: string
        note?: string
        gates?: string[]
      }>
      vulnerabilities: Array<{
        stage: string
        severity: string
        vulnerability: string
        mode: string
        note?: string
      }>
    }>('/api/abuse/matrix/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  llmStatus: () =>
    request<{
      configured: boolean
      model: string
      chat_model: string
      name?: string
      api_key_set: boolean
      api_key_masked: string
      source: string
      shared_with: string
      max_tokens?: number
      models?: Array<{
        id: string
        name: string
        description: string
        max_tokens: number
        tools: boolean
      }>
    }>('/api/llm/status'),
  llmPing: () =>
    request<{ ok: boolean; reply?: string; error?: string; chat_model?: string; source?: string }>(
      '/api/llm/ping',
    ),
  llmSetModel: (model: string) =>
    request<{
      configured: boolean
      model: string
      chat_model: string
      name?: string
      source: string
      models?: Array<{ id: string; name: string; description: string; max_tokens: number }>
    }>('/api/llm/model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    }),
  abuseLlmAnalyze: (body: {
    offer_ids?: string[]
    offers?: BonusOffer[]
    text?: string
    title?: string
    platform?: string
    limit?: number
  }) =>
    request<{
      ok: boolean
      model: string
      source: string
      count: number
      items: Array<{
        offer_id: string
        title: string
        abuse_score_heuristic: number
        abuse_severity_heuristic: string
        model: string
        llm: {
          summary?: string
          conversion_path?: string
          controls_to_verify?: string[]
          parse_error?: boolean
          reason?: string
          repaired?: boolean
          abuse_vectors?: Array<{
            id: string
            title: string
            severity: string
            rationale: string
            test_idea: string
          }>
          rules?: Record<string, unknown>
        }
      }>
      errors: Array<{ offer_id: string; title: string; error: string }>
    }>('/api/abuse/llm/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  abuseLlmDeepAttack: (body: {
    offer_id?: string
    offer?: BonusOffer
    platform?: string
    prior_summary?: string
    prior_vectors?: Array<Record<string, unknown>>
  }) =>
    request<{
      ok: boolean
      model: string
      source: string
      item: {
        offer_id: string
        title: string
        mode?: string
        abuse_score_heuristic: number
        abuse_severity_heuristic: string
        model: string
        truncated?: boolean
        retried?: boolean
        llm: Record<string, unknown>
        raw_preview?: string
      }
      error?: string | null
    }>('/api/abuse/llm/deep-attack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  downloadJourneyReportMd: async (
    sessionId: string,
    body: {
      summary?: string
      conversion?: unknown
      abuse_items?: unknown[]
      game_bonus_risk?: unknown
      llm_report?: string
      llm_vectors?: unknown[]
      deep_attack?: unknown
      offers?: unknown[]
      withdraw_result?: unknown
    },
  ) => {
    const res = await fetch(withGateway(`/api/journey/sessions/${sessionId}/report.md`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      credentials: 'same-origin',
    })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const bodyJson = await res.json()
        detail = bodyJson.detail || JSON.stringify(bodyJson)
      } catch {
        detail = (await res.text()) || detail
      }
      throw new Error(detail)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `betbonus-journey-${sessionId.slice(0, 8)}.md`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return { ok: true as const }
  },
  journeyPresets: () =>
    request<Array<{ id: string; name: string; url: string; platform: string; notes: string }>>(
      '/api/journey/presets',
    ),
  upload: async (platform: string, file: File) => {
    const form = new FormData()
    form.append('platform', platform)
    form.append('file', file)
    return request<BonusOffer[]>('/api/pipeline/upload', { method: 'POST', body: form })
  },
  activity: (limit = 40) => request<ActivityEvent[]>(`/api/activity?limit=${limit}`),
  clearActivity: () => request<{ status: string }>('/api/activity', { method: 'DELETE' }),
  journeySessions: (limit = 50) =>
    request<JourneySessionSummary[]>(`/api/journey/sessions?limit=${limit}`),
  journeySessionActive: () =>
    request<{ active: boolean; session: JourneySession | null }>('/api/journey/sessions/active'),
  startJourneySession: (body: {
    platform: string
    house_name?: string
    house_url?: string
    scout_mode?: string
    label?: string
    meta?: Record<string, unknown>
    close_previous?: boolean
  }) =>
    request<{ ok: boolean; session: JourneySession }>('/api/journey/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  getJourneySession: (id: string) => request<JourneySession>(`/api/journey/sessions/${id}`),
  appendJourneyEvent: (
    id: string,
    body: {
      step?: string
      kind: string
      message: string
      level?: JourneyLogLevel
      detail?: Record<string, unknown>
    },
  ) =>
    request<{ ok: boolean; event: JourneyLogEvent }>(`/api/journey/sessions/${id}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  closeJourneySession: (id: string, note = '') =>
    request<{ ok: boolean; session: JourneySession }>(`/api/journey/sessions/${id}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note }),
    }),
  deleteJourneySession: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/api/journey/sessions/${id}`, { method: 'DELETE' }),
  clearJourneySessions: () => request<{ deleted: number }>('/api/journey/sessions', { method: 'DELETE' }),
  integrityCatalog: () => request<IntegrityCatalog>('/api/integrity/catalog'),
  integritySims: () =>
    request<{ ok: boolean; suite: Record<string, unknown> }>('/api/integrity/sims'),
  integrityRuns: (limit = 20) =>
    request<{ ok: boolean; runs: IntegrityRunSummary[] }>(`/api/integrity/runs?limit=${limit}`),
  opsStatus: () => request<OpsStatus>('/api/ops/status'),
  integrityRun: (body: {
    houses?: string[]
    axes?: string[]
    scenario_ids?: string[]
    run_mode?: string
    confirm_real_bet?: boolean
    persist?: boolean
    plan?: boolean
    require_auth?: boolean
    target_game?: CatalogGame & { house?: string }
  }) =>
    request<
      IntegrityCatalog & {
        id: string
        results: IntegrityResult[]
        coverage: IntegrityCatalog['coverage']
        finished_at?: string
        run_mode?: string
        planner?: IntegrityCatalog['planner']
        notes?: string[]
        kind?: string
        target_game?: CatalogGame
        report_markdown?: string
        report_filename?: string
      }
    >('/api/integrity/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  integrityGames: (house: string, q = '', limit = 120) =>
    request<{ ok: boolean; house: string; count: number; games: CatalogGame[]; note?: string }>(
      `/api/integrity/games?house=${encodeURIComponent(house)}&q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
  latestReports: async () => {
    const emptyIntegrity = {
      available: false,
      markdown: '',
      filename: 'casino-integrity-latest.md',
      run_id: null as string | null,
      label: 'Jornada de teste / Matriz',
      missing: 'Nenhum run DRY/PROBE persistido. Execute a Jornada de teste.',
    }
    const emptyPromo = {
      available: false,
      markdown: '',
      filename: 'betbonus-auto-journey-latest.md',
      run_id: null as string | null,
      label: 'Jornada promo',
      missing: 'Nenhuma jornada promo persistida. Execute EXECUTAR em Jornada promo.',
    }

    const jsonTry = await fetch(withGateway('/api/reports/latest'), { credentials: 'same-origin' })
    if (jsonTry.ok) {
      try {
        const payload = (await jsonTry.json()) as {
          ok: boolean
          integrity: typeof emptyIntegrity
          promo: typeof emptyPromo
        }
        if (payload?.integrity && payload?.promo) return payload
      } catch {
        /* fall through to .md endpoints */
      }
    }

    const [integrityMd, promoMd] = await Promise.all([
      fetchMarkdown('/api/integrity/runs/latest/report.md'),
      fetchMarkdown('/api/abuse/auto-journey/latest.md'),
    ])
    const integrityOk =
      integrityMd.status === 200 &&
      Boolean(integrityMd.text.trim()) &&
      !looksLikeApiMiss(integrityMd.status, integrityMd.text)
    const promoOk =
      promoMd.status === 200 &&
      Boolean(promoMd.text.trim()) &&
      !looksLikeApiMiss(promoMd.status, promoMd.text)
    return {
      ok: integrityOk || promoOk,
      integrity: integrityOk
        ? {
            ...emptyIntegrity,
            available: true,
            markdown: integrityMd.text,
            filename: integrityMd.filename || emptyIntegrity.filename,
          }
        : {
            ...emptyIntegrity,
            missing: looksLikeApiMiss(integrityMd.status, integrityMd.text)
              ? emptyIntegrity.missing
              : emptyIntegrity.missing,
          },
      promo: promoOk
        ? {
            ...emptyPromo,
            available: true,
            markdown: promoMd.text,
            filename: promoMd.filename || emptyPromo.filename,
          }
        : emptyPromo,
    }
  },
  downloadIntegrityReport: async (runId: string, filename?: string) => {
    const res = await fetch(withGateway(`/api/integrity/runs/${runId}/report.md`), {
      credentials: 'same-origin',
    })
    if (!res.ok) throw new Error(`Relatório ${res.status}`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `casino-integrity-${runId.slice(0, 8)}.md`
    a.click()
    URL.revokeObjectURL(url)
  },
  integrityPlan: (use_llm = true) =>
    request<{ ok: boolean; plan: IntegrityCatalog['planner'] }>('/api/integrity/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_llm }),
    }),
}
