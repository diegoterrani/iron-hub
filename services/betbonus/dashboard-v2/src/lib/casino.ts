export const HOUSE_LABEL: Record<string, string> = {
  pagol_bet_br: 'pagol.bet.br',
  '4play_bet_br': '4play.bet.br',
  '4play': '4play.game',
}

export const HOUSE_IDS = ['pagol_bet_br', '4play_bet_br', '4play'] as const

export const AXIS_LABEL: Record<string, string> = {
  session: 'Sessão',
  wallet: 'Wallet',
  catalog: 'Catálogo',
  slots: 'Slots',
  crash: 'Crash',
  table: 'Mesa',
  timer: 'Timer',
  promo: 'Promo',
  jackpot: 'Jackpot',
  withdraw: 'Saque',
}

export const PIPELINE_PHASES = [
  'Recon',
  'Auth',
  'Discovery',
  'Acquire',
  'Arm',
  'Analyze',
  'Probe',
  'Cashout',
  'Report',
] as const

export type PipelinePhase = (typeof PIPELINE_PHASES)[number]

export function modeColor(mode: string): string {
  switch (String(mode || 'SKIPPED').toUpperCase()) {
    case 'AUTOMATED':
      return '#00ff88'
    case 'SEMI_AUTO':
      return '#00e5ff'
    case 'DRY':
      return '#ffb300'
    case 'BLOCKED':
      return '#ff3b4d'
    case 'UNSUPPORTED':
      return '#6b7280'
    case 'SKIPPED':
      return '#374151'
    default:
      return '#374151'
  }
}

export function modeBg(mode: string): string {
  const c = modeColor(mode)
  return `${c}18`
}
