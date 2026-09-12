/** Iron Hub gateway prefix, e.g. `/t/betbonus` when served behind the hub. */
export function gatewayPrefix(): string {
  if (typeof window === 'undefined') return ''
  const m = window.location.pathname.match(/^(\/t\/[^/]+)/)
  return m?.[1] ?? ''
}

export function withGateway(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${gatewayPrefix()}${p}`
}

export function routerBasename(): string {
  const prefix = gatewayPrefix()
  return prefix || '/'
}
