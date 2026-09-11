import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { CategoryBadge } from '../components/CategoryBadge'
import { HouseModal, type HouseDraft } from '../components/HouseModal'
import { DualReportTabs, type ReportBundle } from '../components/DualReportTabs'
import { DualReportsModal } from '../components/DualReportsModal'
import { ScoreBar } from '../components/ScoreBar'
import { Toast } from '../components/Toast'
import type {
  AbuseScoreItem,
  BonusOffer,
  ConversionSnapshot,
  JourneyLogLevel,
  WithdrawOracleResult,
} from '../types'

type StepId =
  | 'casa'
  | 'iniciar'
  | 'auth'
  | 'executar'
  | 'relatorio'
  | 'scrape'
  | 'discover'
  | 'wallet'
  | 'abuse'

/** Fluxo transparente para o operador. */
const STEPS: { id: StepId; label: string; hint: string }[] = [
  { id: 'casa', label: '1 · Recon', hint: 'Casa + sessão' },
  { id: 'iniciar', label: '2 · Auth', hint: 'Login / token' },
  { id: 'auth', label: '3 · Discovery', hint: 'Bônus + ledger' },
  { id: 'executar', label: '4 · Execute', hint: 'Acquire → probe → cashout' },
  { id: 'relatorio', label: '5 · Report', hint: 'MD completo' },
]

const EXEC_PIPELINE = [
  { id: 'auth', label: 'Auth / sessão API' },
  { id: 'discovery', label: 'Discovery de bônus + ledger' },
  { id: 'claim_all', label: 'Acquire — claim / redeem todos os bônus' },
  { id: 'arm_play_poll', label: 'Arm — Mines/Slots + poll' },
  { id: 'llm_analyze', label: 'Analyze — LLM Maverick + Deep Attack T&Cs' },
  { id: 'high_ev_probe', label: 'Probe — high-EV soft-probe' },
  { id: 'kill_chain_matrix', label: 'Probe — kill-chain matrix' },
  { id: 'oracle_withdraw', label: 'Cashout — oracle saque máximo' },
  { id: 'settle_validate', label: 'Cashout — validar saque / onde travou' },
]

const BUILTIN_HOUSES: HouseDraft[] = [
  {
    id: '4play',
    name: '4Play.game',
    url: 'https://4play.game/promotions',
    platform: '4play',
    blurb: 'Costa Rica · API pública + bônus da conta',
    scoutMode: 'live',
    auth: 'token|login',
  },
  {
    id: 'pagol',
    name: 'PAGOL.BET.BR',
    url: 'https://pagol.bet.br/br/my-account/bonuses-rollover/bonus-list',
    platform: 'pagol_bet_br',
    blurb: 'Brasil · Live API Lucky Gaming (bonuses + balance + promocodes)',
    scoutMode: 'live',
    auth: 'token|login',
  },
  {
    id: '4play_bet_br',
    name: '4PLAY.BET.BR',
    url: 'https://4play.bet.br/promocoes',
    platform: '4play_bet_br',
    blurb: 'Brasil · SoftBet SB2 (token + refreshToken do localStorage)',
    scoutMode: 'live',
    auth: 'token',
  },
]

const HOUSES_STORAGE_KEY = 'betbonus.customHouses.v1'

function loadCustomHouses(): HouseDraft[] {
  try {
    const raw = localStorage.getItem(HOUSES_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as HouseDraft[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveCustomHouses(houses: HouseDraft[]) {
  localStorage.setItem(HOUSES_STORAGE_KEY, JSON.stringify(houses))
}

export function Journey() {
  const [step, setStep] = useState<StepId>('casa')
  const [customHouses, setCustomHouses] = useState<HouseDraft[]>(() => loadCustomHouses())
  const [houseModalOpen, setHouseModalOpen] = useState(false)
  const [editingHouse, setEditingHouse] = useState<HouseDraft | null>(null)
  const [scoutMode, setScoutMode] = useState<HouseDraft['scoutMode']>('live')
  const [htmlPaste, setHtmlPaste] = useState('')
  const [platform, setPlatform] = useState('pagol_bet_br')
  const [url, setUrl] = useState(
    'https://pagol.bet.br/br/my-account/bonuses-rollover/bonus-list',
  )
  const [houseName, setHouseName] = useState('PAGOL.BET.BR')
  const [offers, setOffers] = useState<BonusOffer[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [refreshToken, setRefreshToken] = useState('')
  const [softbetJson, setSoftbetJson] = useState('')
  const [authed, setAuthed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState<string[]>([])
  const [walletMsg, setWalletMsg] = useState('')
  const [conversion, setConversion] = useState<ConversionSnapshot | null>(null)
  const [abuseItems, setAbuseItems] = useState<AbuseScoreItem[]>([])
  const [gameBonusRisk, setGameBonusRisk] = useState<{
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
      offer_title?: string
    }>
    wallet_signal?: {
      id: string
      title: string
      severity: string
      rationale: string
      test_idea: string
    } | null
  } | null>(null)
  const [withdrawResult, setWithdrawResult] = useState<WithdrawOracleResult | null>(null)
  const [killMatrix, setKillMatrix] = useState<{
    run_id: string
    report_md_path?: string
    verdict: {
      dominant_blocker: string
      summary: string
      vuln_count: number
      pix_materialized: boolean
    }
    coverage: {
      automated_stages: string[]
      semi_auto_stages: string[]
      manual_stages: string[]
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
    }>
    vulnerabilities: Array<{
      stage: string
      severity: string
      vulnerability: string
      note?: string
    }>
  } | null>(null)
  const [confirmMatrixWithdraw, setConfirmMatrixWithdraw] = useState(false)
  const [confirmAutoWithdraw, setConfirmAutoWithdraw] = useState(false)
  const [confirmAutoRedeem, setConfirmAutoRedeem] = useState(true)
  const [autoJourney, setAutoJourney] = useState<{
    run_id: string
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
    }
    steps: Array<{
      id: string
      title: string
      mode: string
      ok: boolean
      note?: string
    }>
  } | null>(null)
  const [reportsModalOpen, setReportsModalOpen] = useState(false)
  const [latestIntegrity, setLatestIntegrity] = useState<ReportBundle | null>(null)
  const [latestPromo, setLatestPromo] = useState<ReportBundle | null>(null)
  const [execRunning, setExecRunning] = useState(false)
  /** Progresso live durante EXECUTAR (antes da resposta HTTP finalizar). */
  const [liveExecSteps, setLiveExecSteps] = useState<
    Array<{ id: string; ok: boolean; mode: string; note?: string; title?: string }>
  >([])
  const [withdrawAmount, setWithdrawAmount] = useState(10000)
  const [confirmWithdraw, setConfirmWithdraw] = useState(false)
  const [minWithdraw, setMinWithdraw] = useState(10000)
  const [maxWithdraw, setMaxWithdraw] = useState(10000)
  const [highEvProbe, setHighEvProbe] = useState<{
    probed: number
    discovery_count?: number
    note: string
    wallet_unchanged?: boolean
    findings: Array<{ id: string; severity: string; title: string; rationale?: string }>
    probes: Array<{
      game_id: number
      name: string
      launches: Array<{
        ok: boolean
        mode: string
        use_bonus_balance?: boolean | null
        salsa_game?: string
        salsa_type?: string
        error?: string
      }>
    }>
  } | null>(null)
  const [promoCode, setPromoCode] = useState('')
  const [stakeBrl, setStakeBrl] = useState(1)
  const [confirmRedeem, setConfirmRedeem] = useState(false)
  const [confirmRealBet, setConfirmRealBet] = useState(false)
  const [bonusLab, setBonusLab] = useState<{
    ok: boolean
    auto_bet_implemented: boolean
    auto_bet_note: string
    stake_brl: number
    bet_armed: boolean
    gates: string[]
    provider_url?: string
    available_for_stake?: number
    findings: Array<{ id: string; severity: string; title: string; rationale?: string }>
    poll?: { changed?: boolean; balance_delta?: number; bonus_delta?: number }
  } | null>(null)
  const [llmInfo, setLlmInfo] = useState('')
  const [llmModels, setLlmModels] = useState<
    Array<{ id: string; name: string; description: string; max_tokens: number }>
  >([])
  const [llmModel, setLlmModel] = useState('')
  const [llmReport, setLlmReport] = useState<string>('')
  const [llmVectors, setLlmVectors] = useState<
    Array<{ title: string; severity: string; rationale: string; test_idea: string }>
  >([])
  const [deepPromoId, setDeepPromoId] = useState('')
  const [deepAttack, setDeepAttack] = useState<{
    offer_id: string
    title: string
    mode?: string
    abuse_score_heuristic: number
    abuse_severity_heuristic: string
    model: string
    llm: Record<string, unknown>
  } | null>(null)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [sessionLabel, setSessionLabel] = useState('')

  const houses = useMemo(() => {
    const customIds = new Set(customHouses.map((h) => h.id))
    return [...BUILTIN_HOUSES.filter((h) => !customIds.has(h.id)), ...customHouses]
  }, [customHouses])

  useEffect(() => {
    saveCustomHouses(customHouses)
  }, [customHouses])

  useEffect(() => {
    api
      .llmStatus()
      .then((status) => {
        setLlmModels(status.models || [])
        setLlmModel(status.chat_model)
        setLlmInfo(
          `${status.name || status.chat_model} · ${status.chat_model} · key=${status.api_key_masked || '—'} · src=${status.source}`,
        )
      })
      .catch(() => {
        /* LLM status is optional until the abuse step */
      })
  }, [])

  useEffect(() => {
    if (step !== 'relatorio' && !reportsModalOpen) return
    let cancelled = false
    api
      .latestReports()
      .then((payload) => {
        if (cancelled) return
        setLatestIntegrity(payload.integrity)
        const fromRun: Partial<ReportBundle> | undefined = autoJourney?.report_markdown
          ? {
              available: true,
              markdown: autoJourney.report_markdown,
              filename:
                autoJourney.report_filename ||
                `betbonus-auto-journey-${autoJourney.run_id.slice(0, 8)}.md`,
              label: 'Jornada promo',
            }
          : undefined
        setLatestPromo(
          fromRun
            ? {
                ...payload.promo,
                ...fromRun,
                available: true,
              }
            : payload.promo,
        )
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [step, reportsModalOpen, autoJourney?.run_id, autoJourney?.report_markdown, autoJourney?.report_filename])

  // Poll da sessão enquanto EXECUTAR roda — checklist deixa de ficar tudo "em curso"
  useEffect(() => {
    if (!execRunning || !sessionId) return
    let cancelled = false
    const tick = async () => {
      try {
        const sess = await api.getJourneySession(sessionId)
        if (cancelled) return
        const events = [...(sess.events || [])].sort((a, b) =>
          String(a.created_at).localeCompare(String(b.created_at)),
        )
        const byId = new Map<
          string,
          { id: string; ok: boolean; mode: string; note?: string; title?: string }
        >()
        for (const ev of events) {
          const kind = String(ev.kind || '')
          if (!kind.startsWith('auto.')) continue
          // auto.auth / auto.discovery / auto.llm_analyze.progress
          const parts = kind.split('.')
          const stageId = parts[1]
          if (!EXEC_PIPELINE.some((p) => p.id === stageId)) continue
          if (kind.endsWith('.progress')) {
            byId.set(stageId, {
              id: stageId,
              ok: false,
              mode: 'RUNNING',
              note: ev.message,
              title: EXEC_PIPELINE.find((p) => p.id === stageId)?.label,
            })
            continue
          }
          const ok = /ok=True/i.test(ev.message || '') || ev.level === 'success'
          const mode =
            /SKIPPED/i.test(ev.message || '') || /modo=SKIPPED/i.test(ev.message || '')
              ? 'SKIPPED'
              : 'AUTOMATED'
          byId.set(stageId, {
            id: stageId,
            ok,
            mode,
            note: ev.message,
            title: EXEC_PIPELINE.find((p) => p.id === stageId)?.label,
          })
        }
        setLiveExecSteps(Array.from(byId.values()))
        // espelha últimos eventos no log da UI
        const latest = events
          .filter((e) => String(e.kind || '').startsWith('auto'))
          .slice(-8)
          .map((e) => e.message)
        if (latest.length) {
          setLog((prev) => {
            const merged = [...latest].reverse()
            for (const line of prev) {
              if (!merged.includes(line)) merged.push(line)
            }
            return merged.slice(0, 40)
          })
        }
      } catch {
        /* ignore poll errors */
      }
    }
    void tick()
    const id = window.setInterval(tick, 2000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [execRunning, sessionId])

  const stepIndex = STEPS.findIndex((s) => s.id === step)
  const selectedOffers = useMemo(
    () => offers.filter((o) => selected[o.id]),
    [offers, selected],
  )
  /** Alvos do Deep Attack: PAGOL usa [promocode]/[conta]; 4Play usa [promo]. */
  const promoOffers = useMemo(() => {
    const byId = new Map<string, (typeof offers)[number]>()
    const push = (o: (typeof offers)[number]) => {
      if (o?.id && !byId.has(o.id)) byId.set(o.id, o)
    }
    for (const o of selectedOffers) push(o)
    for (const o of offers) {
      const t = o.title || ''
      const rawLen = o.raw_text?.length ?? 0
      if (
        t.startsWith('[promo]') ||
        t.startsWith('[promocode]') ||
        t.startsWith('[conta]') ||
        rawLen > 40
      ) {
        push(o)
      }
    }
    if (byId.size === 0) {
      for (const o of offers) push(o)
    }
    return Array.from(byId.values())
  }, [offers, selectedOffers])

  useEffect(() => {
    if (!promoOffers.length) {
      if (deepPromoId) setDeepPromoId('')
      return
    }
    if (deepPromoId && promoOffers.some((o) => o.id === deepPromoId)) return
    const pick =
      promoOffers.find((o) => selected[o.id]) ||
      promoOffers.find((o) => o.title.startsWith('[conta]')) ||
      promoOffers.find((o) => o.title.startsWith('[promo]')) ||
      promoOffers.find((o) => o.title.startsWith('[promocode]')) ||
      promoOffers[0]
    setDeepPromoId(pick.id)
  }, [promoOffers, selected, deepPromoId])

  const pushLog = (line: string) => setLog((prev) => [line, ...prev].slice(0, 40))

  const logJourney = async (
    stepName: StepId | 'system',
    kind: string,
    message: string,
    level: JourneyLogLevel = 'info',
    detail: Record<string, unknown> = {},
    sid = sessionId,
  ) => {
    pushLog(message)
    if (!sid) return
    try {
      await api.appendJourneyEvent(sid, {
        step: stepName,
        kind,
        message,
        level,
        detail,
      })
    } catch {
      /* keep UI responsive if log backend fails */
    }
  }

  const ensureSession = async (house?: {
    platform: string
    name: string
    url: string
    scoutMode: string
  }) => {
    const p = house?.platform || platform
    const n = house?.name || houseName
    const u = house?.url || url
    const sm = house?.scoutMode || scoutMode
    const res = await api.startJourneySession({
      platform: p,
      house_name: n,
      house_url: u,
      scout_mode: sm,
      label: `${n} · jornada`,
      meta: { source: 'journey_ui' },
      close_previous: true,
    })
    setSessionId(res.session.id)
    setSessionLabel(res.session.label)
    pushLog(`Sessão de logs iniciada · ${res.session.id.slice(0, 8)}`)
    return res.session.id
  }

  const selectHouse = (h: HouseDraft) => {
    setPlatform(h.platform)
    setUrl(h.url)
    setHouseName(h.name)
    setScoutMode(h.scoutMode)
    setAuthed(false)
    void logJourney('casa', 'house.select', `Casa selecionada: ${h.name}`, 'info', {
      platform: h.platform,
      url: h.url,
      scout_mode: h.scoutMode,
      auth: h.auth,
    })
  }

  const go = (id: StepId, sid?: string) => {
    setStep(id)
    void logJourney(
      id,
      'step.enter',
      `Etapa ${id}`,
      'debug',
      { from: step, to: id },
      sid || sessionId,
    )
  }

  const applyOffers = async (
    next: BonusOffer[],
    warning?: string | null,
    sid?: string,
  ) => {
    setOffers(next)
    const map: Record<string, boolean> = {}
    next.forEach((o) => {
      map[o.id] = o.score >= 45 || o.title.startsWith('[conta]')
    })
    setSelected(map)
    const msg =
      `Scout ${houseName}: ${next.length} bônus` + (warning ? ` · aviso: ${warning}` : '')
    await logJourney(
      'scrape',
      'scout.result',
      msg,
      warning ? 'warn' : 'success',
      {
        count: next.length,
        warning: warning || null,
        titles: next.slice(0, 12).map((o) => ({
          id: o.id,
          title: o.title,
          score: o.score,
          type: o.bonus_type,
          wagering: o.wagering_multiple,
        })),
      },
      sid,
    )
    setToast({ message: `${next.length} bônus descobertos` })
  }

  const runScrape = async (withAccount: boolean) => {
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'scrape',
        'scout.start',
        `Iniciando scout mode=${scoutMode}`,
        'info',
        { platform, url, scout_mode: scoutMode, with_account: withAccount },
        sid,
      )
      const livePlatforms = new Set(['4play', '4play_bet_br', 'pagol', 'pagol_bet_br'])
      if (scoutMode === 'live' || livePlatforms.has(platform)) {
        const liveKey = platform === 'pagol' ? 'pagol_bet_br' : platform
        const res = await api.runLive(liveKey)
        if (!res.ok && !res.offers?.length) {
          throw new Error(res.error || 'Scrape live falhou')
        }
        await applyOffers(res.offers, res.error, sid)
      } else if (scoutMode === 'url') {
        if (!url.trim()) throw new Error('Informe a URL de promoções da casa')
        const res = await api.runUrl(platform || 'generic', url.trim(), 1.2)
        if (!res.ok && !res.offers?.length) {
          throw new Error(res.error || 'Scrape por URL falhou')
        }
        await applyOffers(res.offers, res.error, sid)
      } else {
        if (!htmlPaste.trim()) {
          throw new Error('Cole o HTML da página de promoções no campo abaixo')
        }
        const next = await api.runHtml(platform || 'generic', htmlPaste)
        await applyOffers(next, null, sid)
      }
      if (withAccount) go('discover', sid)
      else go('auth', sid)
    } catch (e) {
      await logJourney('scrape', 'scout.error', (e as Error).message, 'error', {
        platform,
        scout_mode: scoutMode,
      })
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const saveHouseFromModal = (house: HouseDraft) => {
    setCustomHouses((prev) => {
      const without = prev.filter((h) => h.id !== house.id && h.platform !== house.platform)
      return [...without, house]
    })
    selectHouse(house)
    setHouseModalOpen(false)
    setEditingHouse(null)
    void logJourney('casa', 'house.save', `Casa salva: ${house.name}`, 'success', {
      platform: house.platform,
      url: house.url,
      scout_mode: house.scoutMode,
      auth: house.auth,
      blurb: house.blurb,
    })
    setToast({ message: `Casa ${house.name} pronta para teste` })
  }

  const removeCustomHouse = (id: string) => {
    const removed = customHouses.find((h) => h.id === id)
    setCustomHouses((prev) => prev.filter((h) => h.id !== id))
    if (removed && (platform === removed.platform || platform === removed.id)) {
      selectHouse(BUILTIN_HOUSES[0])
    }
  }

  const saveAuth = async () => {
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      const authMode = token.trim() ? 'token' : 'login'
      await logJourney(
        'auth',
        'auth.start',
        `Auth ${authMode} · ${platform}`,
        'info',
        { platform, mode: authMode, email: email || null },
        sid,
      )
      if (platform.includes('4play_bet_br') && (softbetJson.trim() || token.trim())) {
        // Prefer JSON único; senão token(+refresh) nos campos
        let access = token.trim()
        let refresh = refreshToken.trim()
        const raw = softbetJson.trim() || token.trim()
        if (raw.startsWith('{')) {
          try {
            const blob = JSON.parse(raw) as Record<string, string>
            access = String(blob.token || blob.accessToken || blob.access_token || '').trim()
            refresh = String(
              blob.refreshToken || blob.refresh_token || refresh || '',
            ).trim()
          } catch {
            throw new Error(
              'JSON inválido. Copie exatamente o valor das chaves token e refreshToken do Local Storage.',
            )
          }
        }
        if (!access) {
          throw new Error(
            'Falta o access token (chave Local Storage `token`). Veja o passo a passo à direita.',
          )
        }
        if (!refresh) {
          throw new Error(
            'Falta o refreshToken (chave Local Storage `refreshToken`). Os dois são obrigatórios.',
          )
        }
        const saved = (await api.saveToken(platform, {
          token: access,
          refresh_token: refresh,
          email,
        })) as { warning?: string }
        setToken('')
        setRefreshToken('')
        setSoftbetJson('')
        if (saved?.warning) {
          await logJourney('auth', 'auth.save_warning', saved.warning, 'warn', { platform }, sid)
        }
      } else if (token.trim()) {
        const saved = (await api.saveToken(platform, {
          token: token.trim(),
          refresh_token: refreshToken.trim() || undefined,
          email,
        })) as { warning?: string }
        setToken('')
        setRefreshToken('')
        if (saved?.warning) {
          await logJourney('auth', 'auth.save_warning', saved.warning, 'warn', { platform }, sid)
        }
      } else if (email && password) {
        if (platform.includes('4play_bet_br')) {
          throw new Error(
            '4play.bet.br: use token + refreshToken do localStorage (login automático ainda não ligado)',
          )
        }
        await api.loginPlatform(platform, { email, password })
        setPassword('')
      } else {
        throw new Error(
          platform.includes('4play_bet_br')
            ? 'Informe token + refreshToken'
            : 'Informe token ou email/senha',
        )
      }
      const check = (await api.validateCredentials(platform)) as {
        ok?: boolean
        warning?: string
        session?: { mode?: string; warning?: string; username?: string }
      }
      if (!check?.ok) {
        throw new Error('Validate falhou')
      }
      setAuthed(true)
      const sessionMode = check.session?.mode || 'live'
      const warn = check.warning || check.session?.warning || ''
      await logJourney(
        'auth',
        'auth.ok',
        `Auth OK · ${platform}${sessionMode === 'claims_trusted' ? ' (claims/JWT)' : ''}`,
        'success',
        { platform, validate: check },
        sid,
      )
      setToast({
        message: warn
          ? `Auth OK (${sessionMode}). API SoftBet bloqueia IP do servidor — JWT aceito.`
          : `Sessão autenticada${check.session?.username ? ` · ${check.session.username}` : ''}`,
        error: false,
      })
      try {
        await runScrape(true)
      } catch {
        /* discovery será refeita no EXECUTAR */
      }
      go(platform.includes('pagol') ? 'executar' : 'discover', sid)
    } catch (e) {
      await logJourney('auth', 'auth.error', (e as Error).message, 'error', { platform })
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const downloadMarkdownBlob = (markdown: string, filename: string) => {
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  }

  const creditSelected = async () => {
    if (!selectedOffers.length) {
      setToast({ message: 'Selecione ao menos um bônus', error: true })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'discover',
        'ledger.credit.start',
        `Creditando ${selectedOffers.length} offers no ledger`,
        'info',
        {
          count: selectedOffers.length,
          items: selectedOffers.map((o) => ({
            id: o.id,
            title: o.title,
            amount: o.amount,
            score: o.score,
          })),
        },
        sid,
      )
      const res = await api.creditWallet({
        platform,
        items: selectedOffers.map((o) => ({
          bonus_id: o.id,
          title: o.title,
          amount: o.amount,
          currency: o.currency,
          source: o.title.startsWith('[conta]') ? 'account' : 'promo',
          note: `score=${o.score} · ${o.bonus_type}`,
        })),
      })
      setWalletMsg(
        `${res.credited} creditados · totais: ${JSON.stringify(res.wallet.totals_by_currency)}`,
      )
      await logJourney(
        'wallet',
        'ledger.credit.ok',
        `Ledger interno (simulação): ${res.credited} itens — casa intacta`,
        'success',
        { credited: res.credited, totals: res.wallet.totals_by_currency },
        sid,
      )
      setToast({
        message: `${res.credited} itens no ledger INTERNO (simulação). Saldo da casa não mudou.`,
      })
      go('wallet', sid)
    } catch (e) {
      await logJourney('wallet', 'ledger.credit.error', (e as Error).message, 'error')
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runAbuseEvaluate = async () => {
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      const payloadOffers = selectedOffers.length ? selectedOffers : offers.slice(0, 12)
      await logJourney(
        'abuse',
        'abuse.evaluate.start',
        `Avaliando conversão + abuse score (${payloadOffers.length} offers)`,
        'info',
        { count: payloadOffers.length },
        sid,
      )
      const res = await api.abuseEvaluate({
        offers: payloadOffers,
        platform,
      })
      setConversion(res.conversion)
      setAbuseItems(res.abuse.items)
      setGameBonusRisk(res.game_bonus_risk || null)
      const minW =
        Number(res.house.min_withdraw || 0) || (platform.includes('pagol') ? 20 : 10000)
      const maxW =
        Number(res.house.max_withdraw || 0) || (platform.includes('pagol') ? 1900 : 100000)
      const bal = Number(res.conversion?.wallet?.balance || 0)
      const maxAvail = platform.includes('pagol')
        ? Math.floor(Math.min(bal, maxW) * 100) / 100
        : Math.floor(Math.min(bal, maxW))
      setMinWithdraw(minW)
      setMaxWithdraw(maxW)
      setWithdrawAmount(maxAvail > 0 ? maxAvail : minW)
      const gameNote =
        res.game_bonus_risk && res.game_bonus_risk.count > 0
          ? ` · jogos/bônus: ${res.game_bonus_risk.count} vetores (crit=${res.game_bonus_risk.critical})`
          : ''
      const note =
        res.conversion.status === 'blocked'
          ? 'Finding OK: casa bloqueia saque (saldo < mínimo)'
          : res.conversion.status === 'withdrawable'
            ? 'Finding: saldo candidato a saque'
            : `Status: ${res.conversion.status}`
      await logJourney(
        'abuse',
        'abuse.evaluate.result',
        `Abuse: ${note}${gameNote} · balance=${res.conversion.wallet.balance} · scores=${res.abuse.count}`,
        'success',
        {
          conversion: res.conversion,
          abuse_items: res.abuse.items,
          game_bonus_risk: res.game_bonus_risk || null,
          house: res.house,
          verdict: res.verdict || null,
        },
        sid,
      )
      setToast({
        message: note,
        error: false,
      })
      go('abuse', sid)
    } catch (e) {
      await logJourney('abuse', 'abuse.evaluate.error', (e as Error).message, 'error')
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runLlmAnalyze = async () => {
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      const status = await api.llmStatus()
      setLlmModels(status.models || [])
      setLlmModel(status.chat_model)
      setLlmInfo(
        `${status.name || status.chat_model} · ${status.chat_model} · key=${status.api_key_masked || '—'} · src=${status.source}`,
      )
      const target = selectedOffers.length ? selectedOffers : offers.slice(0, 2)
      await logJourney(
        'abuse',
        'llm.analyze.start',
        `LLM analyze · ${target.length} offers · ${status.chat_model}`,
        'info',
        { model: status.chat_model, source: status.source, count: target.length },
        sid,
      )
      const res = await api.abuseLlmAnalyze({
        offers: target,
        platform,
        limit: Math.min(2, Math.max(1, target.length || 1)),
      })
      const usable = res.items.filter(
        (item) => !item.llm?.parse_error && Array.isArray(item.llm?.abuse_vectors),
      )
      const first = usable[0] || res.items[0]
      const vectors =
        usable.flatMap((item) =>
          (item.llm?.abuse_vectors || []).map((v) => ({
            title: v.title,
            severity: v.severity,
            rationale: v.rationale,
            test_idea: v.test_idea,
          })),
        ) || []
      setLlmVectors(vectors)
      setLlmReport(
        [
          `model=${res.model} · offers=${res.count}`,
          first?.llm?.parse_error
            ? `parse_error: ${first.llm.reason || 'JSON truncado/inválido'}`
            : first?.llm?.summary || '',
          first?.llm?.conversion_path ? `Path: ${first.llm.conversion_path}` : '',
          ...(first?.llm?.controls_to_verify || []).map((c) => `• ${c}`),
        ]
          .filter(Boolean)
          .join('\n'),
      )
      await logJourney(
        'abuse',
        'llm.analyze.result',
        `LLM: ${res.count} offers · ${vectors.length} vetores · ${res.model}`,
        res.ok ? 'success' : 'warn',
        {
          model: res.model,
          count: res.count,
          vectors,
          summary: first?.llm?.parse_error ? '' : first?.llm?.summary || '',
          errors: res.errors,
          parse_error: Boolean(first?.llm?.parse_error),
        },
        sid,
      )
      setToast({
        message: res.ok
          ? `LLM: ${vectors.length} vetores de abuso`
          : res.errors[0]?.error || 'LLM JSON truncado/inválido — tente de novo',
        error: !res.ok,
      })
    } catch (e) {
      await logJourney('abuse', 'llm.analyze.error', (e as Error).message, 'error')
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runDeepAttack = async () => {
    const offer =
      promoOffers.find((o) => o.id === deepPromoId) ||
      offers.find((o) => o.id === deepPromoId) ||
      null
    if (!offer) {
      setToast({
        message: 'Selecione um alvo ([promo] / [promocode] / [conta]) para o deep attack',
        error: true,
      })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'abuse',
        'llm.deep_attack.start',
        `Deep attack · ${offer.title}`,
        'warn',
        { offer_id: offer.id, title: offer.title },
        sid,
      )
      const res = await api.abuseLlmDeepAttack({
        offer,
        platform,
        prior_summary: llmReport,
        prior_vectors: llmVectors as unknown as Array<Record<string, unknown>>,
      })
      setDeepAttack(res.item)
      const llm = res.item.llm || {}
      const vectors = Array.isArray(llm.abuse_vectors)
        ? (llm.abuse_vectors as Array<Record<string, unknown>>)
        : []
      const parseFail = Boolean(llm.parse_error) || !res.ok
      await logJourney(
        'abuse',
        parseFail ? 'llm.deep_attack.error' : 'llm.deep_attack.result',
        parseFail
          ? `Deep attack parse_error · ${res.model}`
          : `Deep attack OK · ${vectors.length} vetores · ${res.model}`,
        parseFail ? 'error' : 'success',
        {
          offer_id: res.item.offer_id,
          title: res.item.title,
          model: res.model,
          summary: parseFail ? '' : String(llm.summary || ''),
          vectors_count: vectors.length,
          primary_kill_chain: llm.primary_kill_chain || '',
          lab_runbook: llm.lab_runbook || [],
          protection_plan: llm.protection_backlog || llm.protection_plan || [],
          parse_error: parseFail,
          error: res.error,
        },
        sid,
      )
      setToast({
        message: parseFail
          ? res.error || 'Deep attack: JSON truncado/inválido — tente de novo'
          : `Deep attack: ${vectors.length} vetores ofensivos em ${offer.title.slice(0, 48)}`,
        error: parseFail,
      })
    } catch (e) {
      await logJourney('abuse', 'llm.deep_attack.error', (e as Error).message, 'error')
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const downloadFullReport = async () => {
    const sid = sessionId || (await ensureSession())
    setBusy(true)
    try {
      await api.downloadJourneyReportMd(sid, {
        summary: [
          `Jornada ${houseName} (${platform}) · scout=${scoutMode} · offers=${offers.length}`,
          killMatrix
            ? `Kill-chain blocker=${killMatrix.verdict.dominant_blocker} vulns=${killMatrix.verdict.vuln_count}`
            : '',
        ]
          .filter(Boolean)
          .join(' · '),
        conversion: conversion || undefined,
        abuse_items: abuseItems,
        game_bonus_risk: gameBonusRisk || undefined,
        llm_report: [
          llmReport,
          killMatrix
            ? `\n\n## Kill-chain matrix\n\n${killMatrix.verdict.summary}\n\nBlocker: ${killMatrix.verdict.dominant_blocker}\n`
            : '',
        ]
          .filter(Boolean)
          .join(''),
        llm_vectors: llmVectors,
        deep_attack: deepAttack || undefined,
        offers: offers.map((o) => ({
          id: o.id,
          title: o.title,
          bonus_type: o.bonus_type,
          amount: o.amount,
          currency: o.currency,
          wagering_multiple: o.wagering_multiple,
          score: o.score,
        })),
        withdraw_result: withdrawResult || undefined,
      })
      await logJourney('abuse', 'report.md.download', 'Relatório .md baixado', 'success', {
        session_id: sid,
      })
      setToast({ message: 'Relatório .md baixado' })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runAutoJourney = async () => {
    if (!platform.includes('pagol')) {
      setToast({ message: 'EXECUTAR completo só na PAGOL neste lab', error: true })
      return
    }
    if (!authed) {
      setToast({ message: 'Conclua o Auth antes de EXECUTAR', error: true })
      go('auth')
      return
    }
    setBusy(true)
    setExecRunning(true)
    setLiveExecSteps([])
    setAutoJourney(null)
    setStep('executar')
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'executar',
        'auto_journey.start',
        `EXECUTAR exhaust · redeem=${confirmAutoRedeem} withdraw=${confirmAutoWithdraw}`,
        'warn',
        {
          exhaust_mode: true,
          confirm_redeem: confirmAutoRedeem,
          confirm_real_withdraw: confirmAutoWithdraw,
        },
        sid,
      )
      const res = await api.abuseAutoJourney({
        platform,
        session_id: sid,
        exhaust_mode: true,
        confirm_redeem: confirmAutoRedeem,
        confirm_real_withdraw: confirmAutoWithdraw,
        confirm_real_bet: true,
        settle_withdraw: confirmAutoWithdraw,
        settle_timeout_s: 120,
        promocode_limit: 40,
        llm_limit: 2,
        run_deep_attack: true,
        poll_seconds: 30,
        persist_findings: true,
      })
      setAutoJourney(res)
      if (res.session_id && res.session_id !== sessionId) {
        setSessionId(res.session_id)
      }
      await logJourney(
        'executar',
        'auto_journey.result',
        `EXECUTAR stuck=${res.stuck_point} goal_met=${res.automation_goal_met}`,
        res.automation_goal_met ? 'success' : 'warn',
        {
          run_id: res.run_id,
          stuck_point: res.stuck_point,
          report_md_path: res.report_md_path,
          diagnosis: res.diagnosis,
        },
        sid,
      )
      if (res.report_markdown) {
        downloadMarkdownBlob(
          res.report_markdown,
          res.report_filename || `betbonus-auto-journey-${res.run_id.slice(0, 8)}.md`,
        )
      }
      go('relatorio', sid)
      setReportsModalOpen(true)
      setToast({
        message: `Relatório .md pronto · travou em: ${res.stuck_point}`,
        error: !res.ok,
      })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
      setExecRunning(false)
    }
  }

  const runKillChainMatrix = async () => {
    if (!platform.includes('pagol')) {
      setToast({ message: 'Kill-chain matrix só na PAGOL neste lab', error: true })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'abuse',
        'matrix.start',
        `Kill-chain matrix · withdraw=${confirmMatrixWithdraw}`,
        'warn',
        { confirm_real_withdraw: confirmMatrixWithdraw },
        sid,
      )
      const res = await api.abuseKillChainMatrix({
        platform,
        promocode: promoCode.trim() || undefined,
        confirm_redeem: confirmRedeem && !!promoCode.trim(),
        confirm_real_withdraw: confirmMatrixWithdraw,
        settle_withdraw: confirmMatrixWithdraw,
        settle_timeout_s: 60,
        probe_high_ev: true,
        probe_slots: true,
        arm_wager_poll: false,
        persist_findings: true,
      })
      setKillMatrix(res)
      await logJourney(
        'abuse',
        'matrix.result',
        `Matrix blocker=${res.verdict?.dominant_blocker} vulns=${res.verdict?.vuln_count}`,
        res.verdict?.pix_materialized ? 'success' : 'warn',
        { result: res },
        sid,
      )
      setToast({
        message: `Matrix: ${res.verdict?.dominant_blocker || '—'} · ${res.verdict?.vuln_count || 0} vulns`,
        error: !res.ok,
      })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runHighEvProbe = async () => {
    if (!platform.includes('pagol')) {
      setToast({ message: 'Probe high-EV live só na PAGOL neste lab', error: true })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'abuse',
        'games.high_ev.probe.start',
        'Discovery + soft-probe high-EV (sem aposta)',
        'info',
        {},
        sid,
      )
      const res = await api.abuseGamesProbe({
        platform,
        limit: 6,
        include_bonus_flag: true,
      })
      setHighEvProbe(res)
      await logJourney(
        'abuse',
        'games.high_ev.probe.result',
        `Probe: ${res.probed} jogos · ${res.findings?.length || 0} findings`,
        res.findings?.length ? 'warn' : 'success',
        { result: res },
        sid,
      )
      setToast({
        message: `High-EV: ${res.discovery_count ?? '—'} no catálogo · probed ${res.probed} · findings ${res.findings?.length || 0}`,
      })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runBonusMultiplierLab = async () => {
    if (!platform.includes('pagol')) {
      setToast({ message: 'Bonus multiplier lab só na PAGOL', error: true })
      return
    }
    if (promoCode.trim() && !confirmRedeem) {
      setToast({ message: 'Marque confirmação para resgatar o promocode', error: true })
      return
    }
    if (!confirmRealBet) {
      setToast({
        message: 'Marque confirmação para armar stake (abre Mines + poll; aposta no provider é manual)',
        error: true,
      })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'abuse',
        'games.bonus_multiplier.start',
        `Bonus-lab stake=${stakeBrl} promo=${promoCode || '-'}`,
        'warn',
        { stake_brl: stakeBrl, promocode: promoCode, confirm_redeem: confirmRedeem },
        sid,
      )
      const res = await api.abuseBonusMultiplier({
        platform,
        promocode: promoCode.trim(),
        game_id: 1624,
        stake_brl: stakeBrl,
        confirm_redeem: confirmRedeem && !!promoCode.trim(),
        confirm_real_bet: confirmRealBet,
        use_bonus_balance: true,
        poll_seconds: confirmRealBet ? 30 : 0,
      })
      setBonusLab(res)
      await logJourney(
        'abuse',
        'games.bonus_multiplier.result',
        `Bonus-lab armed=${res.bet_armed} gates=${(res.gates || []).join(',')}`,
        res.bet_armed ? 'success' : 'warn',
        { result: res },
        sid,
      )
      setToast({
        message: res.bet_armed
          ? `Sessão armada · stake ≤ R$ ${res.stake_brl} · abra provider_url e aposte`
          : `Lab bloqueado: ${(res.gates || []).slice(0, 2).join(' · ') || 'ver gates'}`,
        error: !res.bet_armed,
      })
    } catch (e) {
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  const runWithdrawOracle = async (preflightOnly: boolean) => {
    if (!preflightOnly && !confirmWithdraw) {
      setToast({ message: 'Marque a confirmação de saque REAL', error: true })
      return
    }
    setBusy(true)
    try {
      const sid = sessionId || (await ensureSession())
      await logJourney(
        'abuse',
        preflightOnly ? 'oracle.preflight' : 'oracle.withdraw.start',
        preflightOnly
          ? `Preflight saque MÁXIMO (cap=${maxWithdraw})`
          : `Oracle saque REAL MÁXIMO (cap=${maxWithdraw})`,
        preflightOnly ? 'info' : 'warn',
        {
          use_max_available: true,
          max_amount: maxWithdraw,
          preflight_only: preflightOnly,
          confirm: confirmWithdraw,
          min_withdraw: minWithdraw,
        },
        sid,
      )
      const res = await api.abuseWithdraw({
        platform,
        amount: 0,
        confirm_real_withdraw: preflightOnly ? true : confirmWithdraw,
        method: platform.includes('pagol') ? 'PIX' : 'tft',
        max_amount: maxWithdraw,
        preflight_only: preflightOnly,
        use_max_available: true,
      })
      setWithdrawResult(res)
      if (typeof res.amount === 'number' && res.amount > 0) {
        setWithdrawAmount(res.amount)
      }
      const snap = await api.abuseSnapshot(platform)
      setConversion(snap)
      const bal = Number(snap.wallet?.balance || 0)
      const maxAvail = platform.includes('pagol')
        ? Math.floor(Math.min(bal, maxWithdraw) * 100) / 100
        : Math.floor(Math.min(bal, maxWithdraw))
      if (maxAvail > 0) setWithdrawAmount(maxAvail)
      await logJourney(
        'abuse',
        'oracle.withdraw.result',
        `Oracle: attempted=${res.attempted} ok=${res.ok} code=${res.code || '-'} status=${res.status}`,
        res.ok ? 'success' : res.attempted ? 'warn' : 'info',
        { result: res, snapshot: snap },
        sid,
      )
      setToast({
        message: res.ok
          ? 'Saque aceito pela casa'
          : res.attempted
            ? `Saque negado: ${res.code || res.message}`
            : res.message,
        error: !res.ok && res.attempted,
      })
    } catch (e) {
      await logJourney('abuse', 'oracle.withdraw.error', (e as Error).message, 'error')
      setToast({ message: (e as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Jornada BetBonus</h2>
          <p>
            Casa → Iniciar → Auth → Executar (kill-chain completa) → Relatório .md · lab redteam.
          </p>
        </div>
        <div className="actions">
          {sessionId && (
            <span className="session-chip" title={sessionLabel}>
              logs · {sessionId.slice(0, 8)}
              <Link to="/logs">abrir</Link>
            </span>
          )}
          <button
            className="btn btn-ghost"
            onClick={async () => {
              if (sessionId) {
                try {
                  await api.closeJourneySession(sessionId, 'Jornada reiniciada pelo operador')
                } catch {
                  /* ignore */
                }
              }
              setStep('casa')
              setOffers([])
              setSelected({})
              setWalletMsg('')
              setConversion(null)
              setAbuseItems([])
              setWithdrawResult(null)
              setConfirmWithdraw(false)
              setLlmInfo('')
              setLlmReport('')
              setLlmVectors([])
              setLog([])
              setSessionId('')
              setSessionLabel('')
              setAuthed(false)
              setAutoJourney(null)
              setExecRunning(false)
              setLiveExecSteps([])
              setKillMatrix(null)
              setDeepAttack(null)
            }}
          >
            Reiniciar jornada
          </button>
        </div>
      </div>

      <div className="journey-rail" aria-label="Etapas da jornada">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            className={`journey-step ${i === stepIndex ? 'active' : ''} ${i < stepIndex ? 'done' : ''}`}
            onClick={() => go(s.id)}
            type="button"
          >
            <span className="journey-index">{i + 1}</span>
            <span>
              <strong>{s.label.replace(/^\d+\s·\s/, '')}</strong>
              <small>{s.hint}</small>
            </span>
          </button>
        ))}
      </div>

      {step === 'casa' && (
        <div className="panel journey-panel">
          <div className="page-head" style={{ marginBottom: 8, paddingBottom: 0, border: 'none' }}>
            <div>
              <h3>Escolha a casa</h3>
              <p className="muted">Preset piloto ou cadastre uma nova casa para teste redteam.</p>
            </div>
            <button
              type="button"
              className="btn btn-accent"
              onClick={() => {
                setEditingHouse(null)
                setHouseModalOpen(true)
              }}
            >
              + Nova casa
            </button>
          </div>

          <div className="preset-grid">
            {houses.map((p) => {
              const isCustom = !BUILTIN_HOUSES.some((b) => b.id === p.id)
              return (
                <div
                  key={p.id}
                  className={`preset-card ${platform === p.platform ? 'selected' : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectHouse(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      selectHouse(p)
                    }
                  }}
                >
                  <div className="preset-card-top">
                    <strong>{p.name}</strong>
                    <span className="badge">{p.scoutMode}</span>
                  </div>
                  <span>{p.blurb}</span>
                  <code>{p.url || '(HTML / upload)'}</code>
                  <small className="muted">platform: {p.platform}</small>
                  {isCustom && (
                    <div className="preset-card-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => {
                          setEditingHouse(p)
                          setHouseModalOpen(true)
                        }}
                      >
                        Editar
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => removeCustomHouse(p.id)}
                      >
                        Remover
                      </button>
                    </div>
                  )}
                </div>
              )
            })}

            <button
              type="button"
              className="preset-card preset-card-add"
              onClick={() => {
                setEditingHouse(null)
                setHouseModalOpen(true)
              }}
            >
              <strong>+ Nova casa de teste</strong>
              <span>URL, platform id e modo scout (live / URL / HTML)</span>
            </button>
          </div>

          <div className="journey-callout" style={{ marginTop: 16 }}>
            Selecionada: <strong>{houseName}</strong> · <code>{platform}</code> · scout=
            {scoutMode}
            {url ? (
              <>
                <br />
                {url}
              </>
            ) : null}
          </div>

          <div className="actions" style={{ marginTop: 16 }}>
            <button
              className="btn btn-accent"
              disabled={busy || !houseName || !platform}
              onClick={async () => {
                setBusy(true)
                try {
                  const sid = await ensureSession()
                  await logJourney(
                    'casa',
                    'journey.begin',
                    `Jornada iniciada · ${houseName}`,
                    'success',
                    { platform, url, scout_mode: scoutMode },
                    sid,
                  )
                  go('iniciar', sid)
                } catch (e) {
                  setToast({ message: (e as Error).message, error: true })
                } finally {
                  setBusy(false)
                }
              }}
            >
              {busy ? 'Abrindo sessão…' : 'INICIAR jornada'}
            </button>
          </div>
        </div>
      )}

      {step === 'iniciar' && (
        <div className="panel journey-panel">
          <h3>Iniciar · {houseName}</h3>
          <p className="muted">
            Fluxo transparente: <strong>Casa → Iniciar → Auth → Executar → Relatório .md</strong>
          </p>
          <div className="journey-callout">
            Em <strong>EXECUTAR</strong> o lab esgota a kill-chain: discovery, claim/redeem, Mines/Slots +
            poll, LLM Maverick + Deep Attack, High-EV probe, matrix, oracle e diagnóstico de saque.
            O relatório final .md baixa automaticamente.
          </div>
          <ol className="muted" style={{ lineHeight: 1.8, paddingLeft: 20 }}>
            {EXEC_PIPELINE.map((s) => (
              <li key={s.id}>{s.label}</li>
            ))}
          </ol>
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => go('casa')}>
              Voltar
            </button>
            <button className="btn btn-primary" onClick={() => go('auth')}>
              Continuar para Auth
            </button>
          </div>
        </div>
      )}

      {step === 'scrape' && (
        <div className="panel journey-panel">
          <h3>Scout / Scrape</h3>
          <p className="muted">
            Captura promoções de <strong>{houseName}</strong>
            {url ? (
              <>
                {' '}
                (<code>{url}</code>)
              </>
            ) : null}
            . Modo: <strong>{scoutMode}</strong>.
          </p>
          <div className="journey-callout">
            Pipeline: Scrape → Parse → NLP → Score → Store
          </div>

          {scoutMode === 'html' && (
            <div className="field" style={{ marginTop: 14 }}>
              <label>HTML da página de promoções</label>
              <textarea
                value={htmlPaste}
                onChange={(e) => setHtmlPaste(e.target.value)}
                placeholder="Cole aqui o HTML salvo da casa…"
                style={{ minHeight: 140 }}
              />
            </div>
          )}

          {scoutMode === 'url' && (
            <div className="field" style={{ marginTop: 14 }}>
              <label>URL (ajustável nesta sessão)</label>
              <input value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
          )}

          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => go('casa')}>
              Voltar
            </button>
            <button className="btn btn-accent" disabled={busy} onClick={() => runScrape(false)}>
              {busy ? 'Scraping…' : 'Rodar scout público'}
            </button>
            <button className="btn btn-primary" disabled={busy} onClick={() => go('auth')}>
              Ir para Auth
            </button>
          </div>
          {offers.length > 0 && (
            <p style={{ marginTop: 14 }}>
              Já há <strong>{offers.length}</strong> offers em memória desta sessão.
            </p>
          )}
        </div>
      )}

      {step === 'auth' && (
        <div className="panel journey-panel">
          <h3>Autenticação</h3>
          <p className="muted">
            {platform.includes('4play_bet_br') ? (
              <>
                SoftBet: cole o JSON do Local Storage (<code>token</code> +{' '}
                <code>refreshToken</code>). O <code>token</code> pode ser sessão (
                <code>iss=4play</code>) ou access (<code>iss=SB2</code>) — os dois são válidos.
              </>
            ) : (
              <>
                Libera bônus da conta / wallet. Token fica em <code>data/credentials.json</code>.
              </>
            )}
          </p>
          <div className="two-col" style={{ marginTop: 12 }}>
            <div className="form-grid">
              {!platform.includes('4play_bet_br') && (
                <>
                  <div className="field">
                    <label>Email</label>
                    <input value={email} onChange={(e) => setEmail(e.target.value)} />
                  </div>
                  <div className="field">
                    <label>Password</label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <div className="field">
                    <label>Ou Bearer token (localStorage → token)</label>
                    <textarea
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      style={{ minHeight: 90 }}
                    />
                  </div>
                </>
              )}
              {platform.includes('4play_bet_br') && (
                <>
                  <div className="field">
                    <label>Cole o JSON completo (recomendado)</label>
                    <textarea
                      value={softbetJson}
                      onChange={(e) => setSoftbetJson(e.target.value)}
                      placeholder='{"token":"eyJ...","refreshToken":"eyJ..."}'
                      style={{ minHeight: 110 }}
                    />
                  </div>
                  <details>
                    <summary className="muted">Ou colar token / refreshToken separados</summary>
                    <div className="field" style={{ marginTop: 8 }}>
                      <label>token (localStorage.token)</label>
                      <textarea
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        style={{ minHeight: 70 }}
                      />
                    </div>
                    <div className="field">
                      <label>refreshToken</label>
                      <textarea
                        value={refreshToken}
                        onChange={(e) => setRefreshToken(e.target.value)}
                        style={{ minHeight: 70 }}
                      />
                    </div>
                  </details>
                </>
              )}
              <div className="actions">
                <button className="btn btn-ghost" onClick={() => go('iniciar')}>
                  Voltar
                </button>
                <button className="btn btn-accent" disabled={busy} onClick={saveAuth}>
                  {busy ? 'Autenticando…' : 'Autenticar'}
                </button>
                <button
                  className="btn btn-primary"
                  disabled={busy || !authed}
                  onClick={() => go(platform.includes('pagol') ? 'executar' : 'discover')}
                >
                  Ir para Executar
                </button>
              </div>
              {authed && <span className="badge good">Sessão autenticada</span>}
            </div>
            <div>
              <h3>{platform.includes('4play_bet_br') ? 'Export SoftBet (recomendado)' : 'Por que auth?'}</h3>
              {platform.includes('4play_bet_br') ? (
                <div className="muted" style={{ lineHeight: 1.7 }}>
                  <p style={{ marginTop: 0 }}>
                    O que você colou antes era o <strong>refresh</strong> SoftBet (
                    <code>iss=4play</code> + <code>sessionToken</code>), não o access SB2. Isso
                    acontece quando o Local Storage está sem o JWT longo — o script abaixo corrige.
                  </p>
                  <ol style={{ paddingLeft: 18 }}>
                    <li>
                      Abra <a href="https://4play.bet.br/" target="_blank" rel="noreferrer">4play.bet.br</a>{' '}
                      <strong>já logado</strong> (saldo visível)
                    </li>
                    <li>
                      <strong>F12</strong> → aba <strong>Console</strong>
                    </li>
                    <li>Cole o script abaixo e Enter</li>
                    <li>
                      Se aparecer alerta <code>OK access</code>, volte aqui e Ctrl+V no JSON
                    </li>
                  </ol>
                  <ol style={{ paddingLeft: 18, marginTop: 0 }}>
                    <li>
                      Esteja <strong>logado</strong> em{' '}
                      <a href="https://4play.bet.br/" target="_blank" rel="noreferrer">4play.bet.br</a>{' '}
                      (saldo visível)
                    </li>
                    <li>
                      <strong>F12 → Console</strong> → cole o script → Enter
                    </li>
                    <li>
                      Alerta <code>OK</code> → volte aqui → Ctrl+V no JSON → Autenticar
                    </li>
                  </ol>
                  <pre
                    style={{
                      whiteSpace: 'pre-wrap',
                      fontSize: 11,
                      background: 'rgba(0,0,0,.25)',
                      padding: 10,
                      borderRadius: 8,
                      maxHeight: 160,
                      overflow: 'auto',
                    }}
                  >{`(() => {
  const token = localStorage.getItem("token") || "";
  const refreshToken = localStorage.getItem("refreshToken") || "";
  if (!token || !refreshToken) {
    alert("Sem token/refreshToken. Faça login em 4play.bet.br (saldo visível) e rode de novo.");
    return;
  }
  const text = JSON.stringify({ token, refreshToken });
  console.log("COLE_NO_BETBONUS:");
  console.log(text);
  const done = () => alert("OK — JSON pronto (" + token.length + "+" + refreshToken.length + ").\\nBetBonus → Auth → Ctrl+V.\\nSe não colar, copie a linha COLE_NO_BETBONUS do Console.");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => { try { copy(text); } catch(e) {} done(); });
  } else {
    try { copy(text); } catch (e) {}
    done();
  }
})();`}</pre>
                  <p style={{ marginBottom: 0 }}>
                    O bug anterior (rejeitar sessão <code>iss=4play</code>) já foi corrigido — pode
                    colar esse JSON normalmente.
                  </p>
                </div>
              ) : (
                <ul className="muted" style={{ paddingLeft: 18, lineHeight: 1.7 }}>
                  <li>Promoções públicas ≠ bônus já na conta</li>
                  <li>Com token: discovery inclui `[conta]` e regras live</li>
                  <li>Próximo passo: <strong>EXECUTAR</strong> a kill-chain completa</li>
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {step === 'executar' && (
        <div className="panel journey-panel">
          <h3>EXECUTAR · esgotar kill-chain</h3>
          <p className="muted">
            Roda todas as etapas deep com o máximo de recursos mapeados e gera o relatório .md ao
            final.
          </p>
          {!platform.includes('pagol') && (
            <div className="journey-callout warn">
              EXECUTAR completo (auto-journey) está ligado para <strong>PAGOL</strong> neste lab.
            </div>
          )}
          <label className="muted" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={confirmAutoRedeem}
              onChange={(e) => setConfirmAutoRedeem(e.target.checked)}
            />
            Redeem/claim real de promocodes + activate bônus
          </label>
          <label className="muted" style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <input
              type="checkbox"
              checked={confirmAutoWithdraw}
              onChange={(e) => setConfirmAutoWithdraw(e.target.checked)}
            />
            Oracle PIX real + poll BO (materialização)
          </label>

          <div style={{ marginBottom: 16 }}>
            {EXEC_PIPELINE.map((stage, idx) => {
              const fromFinal = (autoJourney?.steps || []).find((s) => s.id === stage.id)
              const fromLive = liveExecSteps.find((s) => s.id === stage.id)
              const row = fromFinal || fromLive
              const doneIds = new Set(
                (autoJourney?.steps || liveExecSteps).map((s) => s.id),
              )
              const prevDone =
                idx === 0 || EXEC_PIPELINE.slice(0, idx).every((p) => doneIds.has(p.id))
              let status = 'pendente'
              let tone = 'muted'
              if (row?.mode === 'RUNNING') {
                status = 'em curso…'
                tone = 'warn'
              } else if (row) {
                status = row.ok ? 'OK' : row.mode === 'SKIPPED' ? 'skip' : 'falhou/parcial'
                tone = row.ok || row.mode === 'SKIPPED' ? 'good' : 'warn'
              } else if (execRunning && prevDone) {
                status = 'em curso…'
                tone = 'warn'
              }
              return (
                <div
                  key={stage.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    padding: '8px 0',
                    borderBottom: '1px solid rgba(255,255,255,.06)',
                  }}
                >
                  <span>
                    <strong>{stage.label}</strong>
                    {row?.note ? (
                      <div className="muted" style={{ fontSize: 12 }}>
                        {row.note}
                      </div>
                    ) : null}
                  </span>
                  <span className={`badge ${tone === 'good' ? 'good' : ''}`}>{status}</span>
                </div>
              )
            })}
          </div>

          <div className="actions">
            <button className="btn btn-ghost" disabled={busy} onClick={() => go('auth')}>
              Voltar Auth
            </button>
            <button
              className="btn btn-primary"
              disabled={busy || !authed || !platform.includes('pagol')}
              onClick={runAutoJourney}
              style={{ fontWeight: 700 }}
            >
              {busy || execRunning
                ? 'Executando kill-chain…'
                : '▶ EXECUTAR — esgotar todas as etapas'}
            </button>
            <button
              className="btn btn-accent"
              disabled={busy}
              onClick={() => {
                setReportsModalOpen(true)
                go('relatorio')
              }}
            >
              Ver relatórios
            </button>
          </div>
        </div>
      )}

      {step === 'relatorio' && (
        <div className="panel journey-panel">
          <h3>Relatórios — teste/matriz e promo</h3>
          <p className="muted">
            Dois artefatos: cobertura cassino (Jornada de teste / Matriz) e kill-chain de bônus/PIX
            (Jornada promo). Recarregar a página continua servindo o último .md do servidor.
          </p>
          {autoJourney ? (
            <div className="journey-callout warn">
              <strong>stuck=`{autoJourney.stuck_point}`</strong>
              <div className="muted">{autoJourney.diagnosis?.summary}</div>
              {(autoJourney.diagnosis?.secondary_blockers || []).length > 0 && (
                <div className="muted" style={{ marginTop: 6 }}>
                  Bloqueios: {autoJourney.diagnosis?.secondary_blockers?.join(' · ')}
                </div>
              )}
            </div>
          ) : (
            <p className="muted">
              Sem EXECUTAR nesta sessão de browser — abaixo vão os últimos relatórios gravados no
              lab.
            </p>
          )}
          {autoJourney?.remediation?.dev_instructions && (
            <div style={{ marginTop: 12, marginBottom: 12 }}>
              <strong>DEV</strong>
              <ul className="muted">
                {autoJourney.remediation.dev_instructions.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              <strong>CRM</strong>
              <ul className="muted">
                {(autoJourney.remediation.crm_instructions || []).map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </div>
          )}
          {latestIntegrity && latestPromo ? (
            <DualReportTabs
              integrity={latestIntegrity}
              promo={latestPromo}
              defaultTab={autoJourney ? 'promo' : 'integrity'}
            />
          ) : (
            <p className="muted">Carregando relatórios…</p>
          )}
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => go('executar')}>
              Voltar Executar
            </button>
            <button className="btn btn-primary" onClick={() => setReportsModalOpen(true)}>
              Abrir em modal
            </button>
          </div>
        </div>
      )}

      {step === 'discover' && (
        <div className="panel journey-panel">
          <h3>Discovery de bônus</h3>
          <p className="muted">
            Selecione o que vai para a carteira operacional. Conta = já vinculado ao player; promo =
            oferta pública scoreada.
          </p>
          <div className="actions" style={{ marginBottom: 12 }}>
            <button
              className="btn btn-ghost"
              onClick={() => {
                const map: Record<string, boolean> = {}
                offers.forEach((o) => {
                  map[o.id] = true
                })
                setSelected(map)
              }}
            >
              Selecionar todos
            </button>
            <button className="btn btn-ghost" onClick={() => setSelected({})}>
              Limpar seleção
            </button>
            <button className="btn btn-accent" disabled={busy} onClick={creditSelected}>
              Registrar {selectedOffers.length} no ledger BetBonus
            </button>
            <p className="muted" style={{ width: '100%', margin: '4px 0 0' }}>
              Isso <strong>não</strong> deposita saldo na casa ({houseName}). Só registra no ledger
              interno do BetBonus. Claim/depósito/saque reais ficam na plataforma.
            </p>
          </div>
          {offers.length === 0 ? (
            <div className="empty">Nenhum bônus — volte e rode o scout.</div>
          ) : (
            <div className="top-list">
              {offers.map((offer) => (
                <label className="top-item discover-row" key={offer.id}>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                    <input
                      type="checkbox"
                      checked={!!selected[offer.id]}
                      onChange={(e) =>
                        setSelected((prev) => ({ ...prev, [offer.id]: e.target.checked }))
                      }
                    />
                    <div>
                      <strong>{offer.title}</strong>
                      <div className="muted">
                        {offer.platform} · {offer.bonus_type} · {offer.amount} {offer.currency} ·{' '}
                        {offer.wagering_multiple}x
                      </div>
                      <div style={{ marginTop: 6 }}>
                        <CategoryBadge category={offer.category} />
                      </div>
                    </div>
                  </div>
                  <ScoreBar score={offer.score} />
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 'wallet' && (
        <div className="panel journey-panel">
          <h3>Ledger BetBonus (não é a carteira da casa)</h3>
          <p className="muted">
            O passo anterior só registrou offers no ledger interno para ops. O saldo real de{' '}
            <strong>{houseName}</strong> continua intacto até haver depósito/claim nativo da
            plataforma.
          </p>
          {walletMsg ? (
            <div className="journey-callout ok">{walletMsg}</div>
          ) : (
            <div className="empty">Ainda sem registros nesta sessão.</div>
          )}
          <div className="journey-callout" style={{ marginTop: 12 }}>
            {platform.includes('pagol') ? (
              <>
                Casa <strong>PAGOL.BET.BR</strong> → depósito / conta:{' '}
                <a href="https://pagol.bet.br/" target="_blank" rel="noreferrer">
                  pagol.bet.br
                </a>
                {' · '}
                bônus:{' '}
                <a
                  href="https://pagol.bet.br/br/my-account/bonuses-rollover/bonus-list"
                  target="_blank"
                  rel="noreferrer"
                >
                  minha conta / bônus
                </a>
                {' · '}
                saques PIX na área de withdrawals (pedidos PENDING não voltam ao saldo).
              </>
            ) : platform.includes('4play_bet_br') ? (
              <>
                Casa <strong>4PLAY.BET.BR</strong> →{' '}
                <a href="https://4play.bet.br/" target="_blank" rel="noreferrer">
                  4play.bet.br
                </a>
                {' · '}
                promos:{' '}
                <a href="https://4play.bet.br/promocoes" target="_blank" rel="noreferrer">
                  /promocoes
                </a>
              </>
            ) : (
              <>
                Casa <strong>4Play.game</strong> → abrir depósito:{' '}
                <a href="https://4play.game/?deposit=show" target="_blank" rel="noreferrer">
                  4play.game/?deposit=show
                </a>
              </>
            )}
          </div>
          <div className="actions" style={{ marginTop: 16 }}>
            <button className="btn btn-ghost" onClick={() => go('discover')}>
              Voltar ao discovery
            </button>
            <button className="btn btn-accent" disabled={busy} onClick={runAbuseEvaluate}>
              {busy ? 'Avaliando…' : 'Ir para Abuse / Conversão'}
            </button>
            <Link className="btn btn-primary" to="/wallet">
              Ver ledger + saldo real
            </Link>
          </div>
        </div>
      )}

      {step === 'abuse' && (
        <div className="panel journey-panel">
          <h3>Abuse · Conversão → saque real</h3>
          {platform.includes('pagol') && (
            <div
              className="panel"
              style={{
                marginBottom: 16,
                padding: 14,
                border: '1px solid rgba(120, 200, 120, .35)',
                borderRadius: 10,
                background: 'rgba(40, 80, 40, .18)',
              }}
            >
              <h4 style={{ marginTop: 0 }}>Jornada automática completa</h4>
              <p className="muted" style={{ marginTop: 0 }}>
                Auth → Discovery → Claim/Redeem → Mines/Slots+poll → LLM Maverick+T&Cs →
                High-EV → Kill-chain matrix → Oracle → Validar saque/saldo → Relatório
                DEV/CRM. Objetivo: multiplicar bônus e materializar saque com o máximo
                automatizado.
              </p>
              <label className="muted" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={confirmAutoRedeem}
                  onChange={(e) => setConfirmAutoRedeem(e.target.checked)}
                />
                Redeem/claim real de promocodes + activate bônus
              </label>
              <label className="muted" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <input
                  type="checkbox"
                  checked={confirmAutoWithdraw}
                  onChange={(e) => setConfirmAutoWithdraw(e.target.checked)}
                />
                Oracle PIX real + poll BO (materialização)
              </label>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={runAutoJourney}
                style={{ fontWeight: 700 }}
              >
                {busy ? 'Executando jornada…' : '▶ Rodar jornada completa automática'}
              </button>
              {autoJourney && (
                <div className="journey-callout warn" style={{ marginTop: 14 }}>
                  <strong>
                    stuck=`{autoJourney.stuck_point}` · goal_met=
                    {String(autoJourney.automation_goal_met)}
                  </strong>
                  <div className="muted">{autoJourney.diagnosis?.summary}</div>
                  <div className="muted" style={{ marginTop: 6 }}>
                    Relatório: {autoJourney.report_latest_md || autoJourney.report_md_path}
                  </div>
                  {(autoJourney.steps || []).map((s) => (
                    <div key={s.id} style={{ marginTop: 6 }}>
                      <strong>
                        [{s.mode}] {s.ok ? 'OK' : 'X'} {s.title}
                      </strong>
                      {s.note && <div className="muted">{s.note}</div>}
                    </div>
                  ))}
                  {autoJourney.remediation?.dev_instructions && (
                    <div style={{ marginTop: 10 }}>
                      <strong>DEV</strong>
                      <ul className="muted">
                        {autoJourney.remediation.dev_instructions.slice(0, 5).map((x) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                      <strong>CRM</strong>
                      <ul className="muted">
                        {(autoJourney.remediation.crm_instructions || [])
                          .slice(0, 5)
                          .map((x) => (
                            <li key={x}>{x}</li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <p className="muted">
            {platform.includes('pagol') ? (
              <>
                Piloto <strong>PAGOL.BET.BR</strong> em prod. Oracle chama{' '}
                <code>POST /user/withdrawals/request.do</code> (PIX). Sempre saca o{' '}
                <strong>máximo</strong> (saldo ∩ teto R$ {maxWithdraw}). Min house = R${' '}
                {minWithdraw}.
              </>
            ) : platform.includes('4play_bet_br') ? (
              <>
                Piloto <strong>4PLAY.BET.BR</strong> SoftBet. Auth via token+refresh; wallet live
                pode ficar limitada pelo IP do servidor. Min lab = R$ {minWithdraw}.
              </>
            ) : (
              <>
                Piloto <strong>4Play.game</strong> em prod. Oracle chama{' '}
                <code>POST /wallet/withdraw</code> (SINPE Móvil). Sempre saca o{' '}
                <strong>máximo</strong> (saldo ∩ teto ₡{maxWithdraw}). Min house = ₡
                {minWithdraw}.
              </>
            )}
          </p>

          <div className="field" style={{ maxWidth: 480, marginBottom: 12 }}>
            <label>Modelo LLM (OpenRouter)</label>
            <select
              value={llmModel}
              disabled={busy || llmModels.length === 0}
              onChange={async (e) => {
                const next = e.target.value
                setLlmModel(next)
                try {
                  const status = await api.llmSetModel(next)
                  setLlmModels(status.models || llmModels)
                  setLlmModel(status.chat_model)
                  setLlmInfo(
                    `${status.name || status.chat_model} · ${status.chat_model} · src=${status.source}`,
                  )
                  setToast({ message: `LLM: ${status.name || status.chat_model}` })
                } catch (err) {
                  setToast({ message: (err as Error).message, error: true })
                }
              }}
            >
              {llmModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} — {m.id}
                </option>
              ))}
            </select>
          </div>
          <div className="actions" style={{ marginBottom: 12 }}>
            <button className="btn btn-ghost" disabled={busy} onClick={runAbuseEvaluate}>
              Atualizar snapshot + scores
            </button>
            <button className="btn btn-accent" disabled={busy} onClick={runLlmAnalyze}>
              {busy ? 'LLM…' : 'LLM Maverick · analisar T&Cs'}
            </button>
            {platform.includes('pagol') && (
              <button className="btn btn-accent" disabled={busy} onClick={runHighEvProbe}>
                {busy ? 'Probe…' : 'High-EV · discovery + probe'}
              </button>
            )}
            {platform.includes('pagol') && (
              <button className="btn btn-primary" disabled={busy} onClick={runKillChainMatrix}>
                {busy ? 'Matrix…' : 'Kill-chain matrix · cercar automação'}
              </button>
            )}
            <button className="btn btn-ghost" onClick={() => go('wallet')}>
              Voltar ao ledger
            </button>
          </div>

          {platform.includes('pagol') && (
            <label className="muted" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={confirmMatrixWithdraw}
                onChange={(e) => setConfirmMatrixWithdraw(e.target.checked)}
              />
              Matrix: também pedir saque máximo + poll BO (PIX real)
            </label>
          )}

          {killMatrix && (
            <div
              className="journey-callout warn"
              style={{ marginTop: 0, marginBottom: 14 }}
            >
              <strong>
                Kill-chain matrix · blocker={killMatrix.verdict.dominant_blocker} · vulns=
                {killMatrix.verdict.vuln_count}
              </strong>
              <div className="muted">{killMatrix.verdict.summary}</div>
              <div className="muted" style={{ marginTop: 6 }}>
                AUTO: {killMatrix.coverage.automated_stages.join(', ')}
              </div>
              <div className="muted">
                SEMI: {killMatrix.coverage.semi_auto_stages.join(', ') || '—'} · MANUAL:{' '}
                {killMatrix.coverage.manual_stages.join(', ') || '—'}
              </div>
              <div className="muted">
                Ainda não automatizável: {killMatrix.coverage.not_automatable_yet.join(', ')}
              </div>
              {(killMatrix.stages || []).map((s) => (
                <div key={s.id} style={{ marginTop: 8 }}>
                  <strong>
                    [{s.mode}] {s.ok ? 'OK' : 'X'} {s.title}
                  </strong>
                  {s.vulnerability && (
                    <div className="muted">
                      {s.severity}: {s.vulnerability}
                    </div>
                  )}
                  {s.note && <div className="muted">{s.note}</div>}
                </div>
              ))}
              {killMatrix.report_md_path && (
                <div className="muted" style={{ marginTop: 8 }}>
                  Relatório: {killMatrix.report_md_path}
                </div>
              )}
            </div>
          )}

          {highEvProbe && (
            <div
              className="journey-callout warn"
              style={{ marginTop: 0, marginBottom: 14 }}
            >
              <strong>
                High-EV soft-probe · {highEvProbe.probed} jogos
                {highEvProbe.discovery_count != null
                  ? ` · catálogo ${highEvProbe.discovery_count}`
                  : ''}
              </strong>
              <div className="muted">{highEvProbe.note}</div>
              <div className="muted">
                wallet unchanged={String(highEvProbe.wallet_unchanged)} · findings=
                {highEvProbe.findings?.length || 0}
              </div>
              {(highEvProbe.findings || []).slice(0, 8).map((f) => (
                <div key={f.id} style={{ marginTop: 8 }}>
                  <strong>
                    [{f.severity}] {f.title}
                  </strong>
                  {f.rationale && <div className="muted">{f.rationale}</div>}
                </div>
              ))}
              <div style={{ marginTop: 10 }}>
                {(highEvProbe.probes || []).slice(0, 8).map((p) => {
                  const ok = (p.launches || []).filter((l) => l.ok).length
                  const salsa = (p.launches || []).find((l) => l.ok)?.salsa_game
                  return (
                    <div key={p.game_id} className="muted">
                      #{p.game_id} {p.name} · launches_ok={ok}
                      {salsa ? ` · salsa=${salsa}` : ''}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {platform.includes('pagol') && (
            <div
              className="panel"
              style={{
                marginBottom: 14,
                padding: 14,
                border: '1px solid rgba(255,255,255,.08)',
                borderRadius: 10,
              }}
            >
              <h4 style={{ marginTop: 0 }}>Bonus multiplier lab (Mines)</h4>
              <p className="muted" style={{ marginTop: 0 }}>
                Resgata promo (opt) → abre Mines Spribe → arma stake ≤ R$ 5. A aposta no
                provider ainda é manual (SmartFox WS); o lab mede a carteira por 30s.
              </p>
              <div className="form-grid">
                <div className="field">
                  <label>Promocode (opcional)</label>
                  <input
                    value={promoCode}
                    onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                    placeholder="ex.: CODIGO"
                  />
                </div>
                <div className="field">
                  <label>Stake lab (BRL)</label>
                  <input
                    type="number"
                    min={0.5}
                    max={5}
                    step={0.5}
                    value={stakeBrl}
                    onChange={(e) => setStakeBrl(Number(e.target.value))}
                  />
                </div>
              </div>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={confirmRedeem}
                  onChange={(e) => setConfirmRedeem(e.target.checked)}
                />
                <span>Confirmo <strong>resgatar promocode</strong> (efeito real)</span>
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={confirmRealBet}
                  onChange={(e) => setConfirmRealBet(e.target.checked)}
                />
                <span>
                  Confirmo armar stake real · vou apostar ≤ R$ {stakeBrl} na URL Mines
                </span>
              </label>
              <div className="actions" style={{ marginTop: 10 }}>
                <button
                  className="btn btn-danger"
                  disabled={busy || !confirmRealBet}
                  onClick={runBonusMultiplierLab}
                >
                  {busy ? 'Armando…' : 'Armar redeem + Mines + poll'}
                </button>
              </div>
              {bonusLab && (
                <div
                  className={`journey-callout ${bonusLab.bet_armed ? 'ok' : 'warn'}`}
                  style={{ marginTop: 12 }}
                >
                  <strong>
                    Bonus-lab · armed={String(bonusLab.bet_armed)} · stake≤R${' '}
                    {bonusLab.stake_brl}
                  </strong>
                  <div className="muted">{bonusLab.auto_bet_note}</div>
                  <div className="muted">
                    available={bonusLab.available_for_stake ?? '—'} · gates=
                    {(bonusLab.gates || []).join(' | ') || '—'}
                  </div>
                  {bonusLab.provider_url && (
                    <div style={{ marginTop: 8 }}>
                      <a href={bonusLab.provider_url} target="_blank" rel="noreferrer">
                        Abrir Mines (provider_url)
                      </a>
                    </div>
                  )}
                  {bonusLab.poll && (
                    <div className="muted" style={{ marginTop: 6 }}>
                      poll changed={String(bonusLab.poll.changed)} Δbal=
                      {bonusLab.poll.balance_delta ?? 0} Δbonus=
                      {bonusLab.poll.bonus_delta ?? 0}
                    </div>
                  )}
                  {(bonusLab.findings || []).map((f) => (
                    <div key={f.id} style={{ marginTop: 6 }}>
                      <strong>
                        [{f.severity}] {f.title}
                      </strong>
                      {f.rationale && <div className="muted">{f.rationale}</div>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {llmInfo && (
            <p className="muted" style={{ marginTop: 0 }}>
              LLM Iron Red Team: {llmInfo}
            </p>
          )}

          {conversion ? (
            <div
              className={`journey-callout ${
                conversion.status === 'blocked'
                  ? 'critical'
                  : conversion.status === 'withdrawable'
                    ? 'ok'
                    : 'warn'
              }`}
              style={{ marginBottom: 14 }}
            >
              <strong>
                {conversion.status === 'blocked'
                  ? 'Finding válido · conversão bloqueada pela casa'
                  : `Status: ${conversion.status}`}
              </strong>
              <br />
              Balance={conversion.wallet.balance} · Bonus={conversion.wallet.bonus} · Rollover=
              {conversion.wallet.rollover}
              <br />
              {conversion.notes}
              {conversion.gates.length > 0 && (
                <>
                  <br />
                  <span className="muted">Gates: {conversion.gates.join(' · ')}</span>
                </>
              )}
              {conversion.status === 'blocked' && (
                <>
                  <br />
                  <span className="muted">
                    Para testar saque com êxito real: creditar a conta redteam ≥{' '}
                    {platform.includes('pagol') ? `R$ ${minWithdraw}` : `₡${minWithdraw}`}{' '}
                    (ou claim de campanha com rollover→clear).
                  </span>
                </>
              )}
            </div>
          ) : (
            <div className="empty">Rode a avaliação para carregar o snapshot da casa.</div>
          )}

          {abuseItems.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3>Abuse score (selecionados / top)</h3>
              <div className="top-list">
                {abuseItems.slice(0, 8).map((item) => (
                  <div className="top-item" key={item.offer_id}>
                    <div>
                      <strong>{item.title}</strong>
                      <div className="muted">
                        {item.severity} · abuse_score={item.abuse_score}
                        {item.breakdown?.bonus_game_gap
                          ? ` · game_gap=${item.breakdown.bonus_game_gap}`
                          : ''}
                      </div>
                    </div>
                    <ScoreBar score={item.abuse_score} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {gameBonusRisk && gameBonusRisk.count > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h3>Vetores · jogos com bônus (sem rollover / sem depósito)</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                {gameBonusRisk.focus} · {gameBonusRisk.count} sinal(is) · critical=
                {gameBonusRisk.critical} · high={gameBonusRisk.high}
              </p>
              <div className="top-list">
                {gameBonusRisk.items.slice(0, 10).map((v, idx) => {
                  const sev = (v.severity || '').toLowerCase()
                  const sevClass =
                    sev.includes('crit')
                      ? 'severity-critical'
                      : sev.includes('high') || sev.includes('alto')
                        ? 'severity-high'
                        : sev.includes('med')
                          ? 'severity-medium'
                          : 'severity-low'
                  return (
                    <div className="top-item" key={`${v.id}-${idx}`}>
                      <div>
                        <strong>
                          <span className={sevClass}>[{v.severity}]</span> {v.title}
                        </strong>
                        {v.offer_title && (
                          <div className="muted">Offer: {v.offer_title}</div>
                        )}
                        <div className="muted">{v.rationale}</div>
                        <div className="muted">Teste lab: {v.test_idea}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {(llmReport || llmVectors.length > 0) && (
            <div style={{ marginBottom: 16 }}>
              <h3>
                Análise LLM (
                {llmModels.find((m) => m.id === llmModel)?.name || llmModel || 'OpenRouter'})
              </h3>
              {llmReport && (
                <div className="journey-callout" style={{ whiteSpace: 'pre-wrap', marginBottom: 12 }}>
                  {llmReport}
                </div>
              )}
              {llmVectors.length > 0 && (
                <div className="top-list">
                  {llmVectors.slice(0, 8).map((v, idx) => {
                    const sev = (v.severity || '').toLowerCase()
                    const sevClass =
                      sev.includes('crit')
                        ? 'severity-critical'
                        : sev.includes('high') || sev.includes('alto')
                          ? 'severity-high'
                          : sev.includes('med') || sev.includes('médio') || sev.includes('medio')
                            ? 'severity-medium'
                            : 'severity-low'
                    return (
                      <div className="top-item" key={`${idx}-${v.title}`}>
                        <div>
                          <strong>
                            <span className={sevClass}>[{v.severity}]</span> {v.title}
                          </strong>
                          <div className="muted">{v.rationale}</div>
                          <div className="muted">Teste: {v.test_idea}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          <div className="form-grid">
            <div className="field">
              <label>
                Valor do saque — máximo disponível (
                {platform.includes('pagol') || platform.includes('bet_br') ? 'BRL' : 'CRC'})
              </label>
              <input
                type="number"
                min={0}
                value={withdrawAmount}
                readOnly
                title="Calculado automaticamente: min(saldo, teto lab)"
              />
              <div className="muted" style={{ marginTop: 4 }}>
                Oracle usa sempre <code>use_max_available</code> · teto lab ={' '}
                {platform.includes('pagol') || platform.includes('bet_br') ? 'R$' : '₡'}
                {maxWithdraw}
              </div>
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={confirmWithdraw}
                onChange={(e) => setConfirmWithdraw(e.target.checked)}
              />
              <span>
                Confirmo <strong>saque REAL</strong> na conta redteam{' '}
                {platform.includes('pagol') ? 'PAGOL (PIX)' : '4Play (SINPE)'} (prod)
              </span>
            </label>
            <div className="actions">
              <button
                className="btn btn-ghost"
                disabled={busy}
                onClick={() => runWithdrawOracle(true)}
              >
                Preflight (sem POST)
              </button>
              <button
                className="btn btn-danger"
                disabled={busy || !confirmWithdraw}
                onClick={() => runWithdrawOracle(false)}
              >
                {busy ? 'Enviando…' : 'Oracle: tentar saque real'}
              </button>
            </div>
          </div>

          {withdrawResult && (
            <div
              className={`journey-callout ${
                withdrawResult.ok ? 'ok' : withdrawResult.attempted ? 'critical' : 'warn'
              }`}
              style={{ marginTop: 14 }}
            >
              <strong>
                {withdrawResult.attempted ? 'Tentativa enviada' : 'Sem POST'} · {withdrawResult.status}
              </strong>
              <br />
              code={withdrawResult.code || '—'} · http={withdrawResult.http_status ?? '—'}
              <br />
              {withdrawResult.message}
              {withdrawResult.finding_id && (
                <>
                  <br />
                  finding={withdrawResult.finding_id}
                </>
              )}
            </div>
          )}

          <div
            className="panel"
            style={{
              marginTop: 20,
              padding: 14,
              border: '1px solid rgba(255,255,255,.08)',
              borderRadius: 10,
            }}
          >
            <h3 style={{ marginTop: 0 }}>Pós-teste · Deep attack + relatório</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              1) Selecione um alvo (<code>[promo]</code> / <code>[promocode]</code> /{' '}
              <code>[conta]</code>) e rode tentativa ofensiva com mais recursos LLM.
              2) Ao final, baixe o <code>.md</code> com timeline + scores + LLM + deep attack +
              oracle + matrix.
            </p>
            <div className="field">
              <label>Alvo do deep attack (promo / promocode / bônus conta)</label>
              <select
                value={deepPromoId}
                onChange={(e) => setDeepPromoId(e.target.value)}
                disabled={!promoOffers.length || busy}
              >
                <option value="">
                  {promoOffers.length
                    ? `— escolher (${promoOffers.length} alvos) —`
                    : 'Nenhum alvo no discovery — rode Scout / credite offers'}
                </option>
                {promoOffers.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.title.slice(0, 90)} · score={o.score}
                  </option>
                ))}
              </select>
            </div>
            <div className="actions" style={{ marginTop: 10 }}>
              <button
                className="btn btn-accent"
                disabled={busy || !deepPromoId || !promoOffers.length}
                onClick={runDeepAttack}
                title={
                  !promoOffers.length
                    ? 'Sem offers no discovery'
                    : !deepPromoId
                      ? 'Selecione um alvo na lista'
                      : 'Rodar deep attack LLM'
                }
              >
                {busy ? 'Deep attack…' : 'Tentativa ofensiva (mais recursos)'}
              </button>
              <button className="btn btn-primary" disabled={busy} onClick={downloadFullReport}>
                Baixar relatório .md
              </button>
            </div>

            {deepAttack && (
              <div className="journey-callout warn" style={{ marginTop: 14, whiteSpace: 'pre-wrap' }}>
                <strong>
                  Deep attack · {deepAttack.title} · {deepAttack.model}
                  {deepAttack.llm?.parse_error ? ' · PARSE ERROR' : ''}
                </strong>
                <br />
                score heurístico={deepAttack.abuse_score_heuristic} · severity=
                {deepAttack.abuse_severity_heuristic}
                <br />
                {String(deepAttack.llm?.summary || '')}
                {deepAttack.llm?.primary_kill_chain ? (
                  <>
                    <br />
                    <br />
                    <strong>Kill chain:</strong> {String(deepAttack.llm.primary_kill_chain)}
                  </>
                ) : null}
                {Array.isArray(deepAttack.llm?.lab_runbook) &&
                (deepAttack.llm.lab_runbook as unknown[]).length > 0 ? (
                  <>
                    <br />
                    <br />
                    <strong>Lab runbook</strong>
                    <br />
                    {(deepAttack.llm.lab_runbook as string[]).map((row, i) => (
                      <span key={i}>
                        {i + 1}. {row}
                        <br />
                      </span>
                    ))}
                  </>
                ) : null}

                {(() => {
                  const plan = (deepAttack.llm?.protection_backlog ||
                    deepAttack.llm?.protection_plan ||
                    []) as Array<{
                    priority?: string
                    title?: string
                    why?: string
                    fixes?: string[]
                    implementation?: string[]
                    blocks_vectors?: string[]
                    owner?: string
                    effort?: string
                    effort_days?: number
                    impact?: string
                  }>
                  if (!Array.isArray(plan) || plan.length === 0) return null
                  return (
                    <>
                      <br />
                      <br />
                      <strong>Sugestões de correção / proteção anti-abuso</strong>
                      <div className="top-list" style={{ marginTop: 8 }}>
                        {plan.slice(0, 10).map((p, idx) => (
                          <div className="top-item" key={`${idx}-${p.title}`}>
                            <div>
                              <strong>
                                [{p.priority || '?'}] {p.title}
                              </strong>
                              {p.why && <div className="muted">{p.why}</div>}
                              {(p.implementation || p.fixes || []).slice(0, 6).map((f, i) => (
                                <div className="muted" key={i}>
                                  • {f}
                                </div>
                              ))}
                              <div className="muted">
                                {p.owner ? `owner=${p.owner}` : ''}
                                {p.effort || p.effort_days != null
                                  ? ` · effort=${p.effort ?? p.effort_days}`
                                  : ''}
                                {p.impact ? ` · impact=${p.impact}` : ''}
                                {p.blocks_vectors?.length
                                  ? ` · bloqueia: ${p.blocks_vectors.join(', ')}`
                                  : ''}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )
                })()}

                {Array.isArray(deepAttack.llm?.abuse_vectors) && (
                  <>
                    <br />
                    <strong>
                      Vetores ({(deepAttack.llm.abuse_vectors as unknown[]).length})
                    </strong>
                    <div className="top-list" style={{ marginTop: 8 }}>
                      {(
                        deepAttack.llm.abuse_vectors as Array<{
                          title?: string
                          severity?: string
                          exploitability?: string
                          rationale?: string
                          test_idea?: string
                          kill_control?: string
                          remediation?: {
                            priority?: string
                            owner?: string
                            fix?: string
                            engineering_change?: string
                            config_change?: string
                            detection_rule?: string
                            acceptance_test?: string
                          }
                        }>
                      )
                        .slice(0, 12)
                        .map((v, idx) => (
                          <div className="top-item" key={`${idx}-${v.title}`}>
                            <div>
                              <strong>
                                [{v.severity}/{v.exploitability || '?'}] {v.title}
                              </strong>
                              <div className="muted">{v.rationale}</div>
                              <div className="muted">Teste: {v.test_idea}</div>
                              {v.kill_control && (
                                <div className="muted">Kill: {v.kill_control}</div>
                              )}
                              {v.remediation?.fix && (
                                <div className="muted">
                                  <strong>
                                    Correção [{v.remediation.priority || '?'}/
                                    {v.remediation.owner || '?'}]:
                                  </strong>{' '}
                                  {v.remediation.fix}
                                  {v.remediation.engineering_change
                                    ? ` · eng: ${v.remediation.engineering_change}`
                                    : ''}
                                  {v.remediation.config_change
                                    ? ` · cfg: ${v.remediation.config_change}`
                                    : ''}
                                  {v.remediation.detection_rule
                                    ? ` · detect: ${v.remediation.detection_rule}`
                                    : ''}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {log.length > 0 && (
        <div className="panel" style={{ marginTop: 14 }}>
          <div className="page-head" style={{ border: 0, marginBottom: 8, paddingBottom: 0 }}>
            <div>
              <h3>Log da sessão</h3>
              <p className="muted">
                {sessionId
                  ? `Sessão ${sessionId.slice(0, 8)} · detalhe completo em Logs`
                  : 'Sessão ainda não persistida'}
              </p>
            </div>
            {sessionId && (
              <Link className="btn btn-ghost" to="/logs">
                Ver detalhamento
              </Link>
            )}
          </div>
          <div className="activity-list">
            {log.map((line, i) => (
              <div className="activity-item success" key={`${i}-${line}`}>
                <div className="dot" />
                <div>{line}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}

      <HouseModal
        open={houseModalOpen}
        initial={
          editingHouse || {
            name: '',
            platform: '',
            url: '',
            blurb: 'Casa redteam · teste de campanha',
            scoutMode: 'url',
            auth: 'optional',
          }
        }
        onClose={() => {
          setHouseModalOpen(false)
          setEditingHouse(null)
        }}
        onSave={saveHouseFromModal}
      />
      <DualReportsModal
        open={reportsModalOpen}
        onClose={() => setReportsModalOpen(false)}
        defaultTab={autoJourney ? 'promo' : 'integrity'}
        promoOverride={
          autoJourney?.report_markdown
            ? {
                available: true,
                markdown: autoJourney.report_markdown,
                filename:
                  autoJourney.report_filename ||
                  `betbonus-auto-journey-${autoJourney.run_id.slice(0, 8)}.md`,
                label: 'Jornada promo',
              }
            : undefined
        }
      />
    </>
  )
}
