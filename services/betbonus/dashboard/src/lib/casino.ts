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

export function modeClass(mode: string): string {
  const m = String(mode || 'SKIPPED').toLowerCase().replace('_', '-')
  return `integrity-mode integrity-mode--${m}`
}

export const MODE_LEGEND: Array<{ mode: string; label: string; text: string }> = [
  {
    mode: 'AUTOMATED',
    label: 'AUTOMATED',
    text: 'O agente concluiu sozinho na API da casa (sessão, wallet, catálogo, launch).',
  },
  {
    mode: 'SEMI_AUTO',
    label: 'SEMI AUTO',
    text: 'Falta ação no provider (spin, cashout, mesa). Sem jogada de RNG neste harness.',
  },
  {
    mode: 'UNSUPPORTED',
    label: 'UNSUPPORTED',
    text: 'A casa não expõe API para esse eixo — cobertura documental, não falha de sessão.',
  },
  {
    mode: 'BLOCKED',
    label: 'BLOCKED',
    text: 'Não rodou: sessão inválida, kill-switch, ou a casa recusou a chamada.',
  },
  {
    mode: 'SKIPPED',
    label: 'SKIPPED',
    text: 'Eixo/casa fora deste run, ou worker offline sem adapter.',
  },
  {
    mode: 'DRY',
    label: 'DRY',
    text: 'Simulação local — não chamou a API da casa.',
  },
]
