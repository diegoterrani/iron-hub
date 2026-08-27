export type BonusCategory = 'excellent' | 'good' | 'average' | 'poor' | 'avoid'
export type BonusType =
  | 'deposit_match'
  | 'no_deposit'
  | 'free_spins'
  | 'cashback'
  | 'welcome'
  | 'loyalty'
  | 'unknown'

export interface BonusOffer {
  id: string
  platform: string
  bonus_type: BonusType
  title: string
  amount: number
  currency: string
  match_percent: number | null
  free_spins: number | null
  wagering_multiple: number
  min_deposit: number
  max_bet_during_bonus: number | null
  expiry_days: number
  expiry_hours: number | null
  game_restrictions: string[]
  terms_url: string
  source_url: string
  raw_text: string
  scraped_at: string
  score: number
  category: BonusCategory
  score_breakdown: Record<string, number>
}

export interface Stats {
  total: number
  avg_score: number
  by_category: Record<string, number>
  by_platform: Record<string, number>
  by_type: Record<string, number>
  top_score: number
  notify_ready: number
  platforms_configured: string[]
  pipeline: string[]
}

export interface PlatformInfo {
  id: string
  name: string
  scraper: string
}

export interface ActivityEvent {
  id: string
  kind: string
  message: string
  level: 'info' | 'success' | 'warn' | 'error'
  meta: Record<string, unknown>
  created_at: string
}

export type JourneyLogLevel = 'info' | 'success' | 'warn' | 'error' | 'debug'

export interface JourneyLogEvent {
  id: string
  step: string
  kind: string
  level: JourneyLogLevel
  message: string
  detail: Record<string, unknown>
  created_at: string
}

export interface JourneySessionSummary {
  id: string
  label: string
  platform: string
  house_name: string
  house_url: string
  scout_mode: string
  status: 'active' | 'closed' | string
  started_at: string
  ended_at: string | null
  event_count: number
  last_message: string
  last_level: string
  meta: Record<string, unknown>
}

export interface JourneySession extends JourneySessionSummary {
  events: JourneyLogEvent[]
}

export interface ScrapeUrlResponse {
  ok: boolean
  error: string | null
  platform: string
  source_url: string
  offers: BonusOffer[]
}

export type ConversionStatus =
  | 'unknown'
  | 'no_bonus'
  | 'claimed'
  | 'wagering'
  | 'withdrawable'
  | 'blocked'
  | 'withdraw_attempted'
  | 'withdraw_ok'
  | 'withdraw_denied'

export interface ConversionSnapshot {
  platform: string
  status: ConversionStatus
  wallet: {
    platform: string
    balance: number
    bonus: number
    rollover: number
  }
  account_bonuses: number
  gates: string[]
  notes: string
  fetched_at: string
}

export interface GameBonusVector {
  id: string
  title: string
  severity: string
  rationale: string
  test_idea: string
  evidence?: Record<string, unknown>
  source?: string
  offer_id?: string
  offer_title?: string
}

export interface AbuseScoreItem {
  offer_id: string
  title: string
  platform: string
  abuse_score: number
  severity: string
  breakdown: Record<string, number>
  game_bonus_vectors?: GameBonusVector[]
}

export interface WithdrawOracleResult {
  ok: boolean
  attempted: boolean
  preflight_only: boolean
  status: ConversionStatus
  http_status: number | null
  code: string
  message: string
  amount: number
  currency: string
  method: string
  gates: string[]
  finding_id: string
  wallet_before?: { balance: number; bonus: number; rollover: number } | null
  wallet_after?: { balance: number; bonus: number; rollover: number } | null
}

export type IntegrityMode =
  | 'AUTOMATED'
  | 'SEMI_AUTO'
  | 'UNSUPPORTED'
  | 'SKIPPED'
  | 'BLOCKED'
  | 'DRY'

export interface IntegrityCell {
  mode: IntegrityMode
  ok: boolean | null
  severity: string
  count: number
  title: string
}

export interface IntegrityScenario {
  id: string
  axis: string
  title: string
  worker: string
  mode: string
  houses: string[]
  evidence: string
}

export interface IntegrityResult {
  id: string
  scenario_id: string
  axis: string
  platform: string
  title: string
  mode: IntegrityMode
  ok: boolean
  severity: string
  vulnerability: string
  note: string
  evidence: Record<string, unknown>
}

export interface IntegrityCatalog {
  axes: string[]
  houses: string[]
  scenarios: IntegrityScenario[]
  safety: {
    default_mode: string
    max_lab_stake_brl: number
    confirm_real_bet_default: boolean
    kill_switch: Record<string, boolean>
  }
  coverage: {
    cells: Record<string, Record<string, IntegrityCell>>
    mode_counts: Record<string, number>
    scenario_count: number
    automated_ratio: number
    note?: string
  }
  latest_run_id?: string
  finished_at?: string
  run_mode?: string
  results?: IntegrityResult[]
  planner?: {
    next_scenario_id?: string
    axis?: string
    house?: string
    rationale?: string
    source?: string
    title?: string
    priority?: string
  }
  notes?: string[]
  product?: string
}

export interface OpsHouseStatus {
  id: string
  label: string
  has_token: boolean
  has_refresh_token: boolean
  session_ok?: boolean
  session_note?: string
  email: string
  updated_at: string
}

export interface IntegrityRunSummary {
  id: string
  started_at: string
  finished_at: string
  run_mode: string
  houses: string[]
  axes: string[]
  scenario_count: number
  mode_counts: Record<string, number>
  automated_ratio?: number
  planner?: string
  kind?: string
  target_game?: CatalogGame
}

export interface CatalogGame {
  game_id: string | number
  name?: string
  provider?: string
  slug?: string
  aggregator?: string
  category_hint?: string
  source?: string
}

export interface OpsStatus {
  ok: boolean
  product: string
  health: { status: string; service: string; mode: string }
  houses: OpsHouseStatus[]
  llm: {
    configured: boolean
    chat_model: string
    name?: string
    api_key_set: boolean
  }
  safety: {
    default_mode: string
    max_lab_stake_brl: number
    kill_switch: Record<string, boolean>
  }
  latest_run: IntegrityRunSummary | null
  coverage: IntegrityCatalog['coverage']
  axes: string[]
  scenario_count: number
}
