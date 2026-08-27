import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { DualReportTabs, type ReportBundle } from './DualReportTabs'

type Props = {
  open: boolean
  onClose: () => void
  integrityOverride?: Partial<ReportBundle>
  promoOverride?: Partial<ReportBundle>
  defaultTab?: 'integrity' | 'promo'
}

const EMPTY: ReportBundle = {
  available: false,
  markdown: '',
  filename: '',
  label: '',
  missing: 'Relatório indisponível neste lab.',
}

function mergeBundle(base: ReportBundle, override?: Partial<ReportBundle>): ReportBundle {
  if (!override) return base
  const markdown = override.markdown ?? base.markdown
  return {
    ...base,
    ...override,
    markdown,
    available: Boolean(markdown?.trim()) || Boolean(override.available),
    filename: override.filename || base.filename,
  }
}

export function DualReportsModal({
  open,
  onClose,
  integrityOverride,
  promoOverride,
  defaultTab = 'integrity',
}: Props) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [integrity, setIntegrity] = useState<ReportBundle>(EMPTY)
  const [promo, setPromo] = useState<ReportBundle>(EMPTY)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setBusy(true)
    setError('')
    setIntegrity(EMPTY)
    setPromo(EMPTY)
    api
      .latestReports()
      .then((payload) => {
        if (cancelled) return
        setIntegrity(mergeBundle(payload.integrity, integrityOverride))
        setPromo(mergeBundle(payload.promo, promoOverride))
      })
      .catch((e: Error) => {
        if (cancelled) return
        setError(e.message)
        setIntegrity(mergeBundle(EMPTY, integrityOverride))
        setPromo(mergeBundle(EMPTY, promoOverride))
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, integrityOverride?.markdown, promoOverride?.markdown]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null

  return (
    <div className="iron-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="dual-reports-title">
      <div className="iron-modal iron-modal--reports">
        <div className="iron-modal-head">
          <div>
            <h3 id="dual-reports-title">Relatórios da jornada</h3>
            <p className="muted">
              Dois artefatos distintos: cobertura cassino (Jornada de teste / Matriz) e kill-chain
              de bônus/PIX (Jornada promo). Um não substitui o outro.
            </p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>
        {busy && <div className="muted">Carregando últimos .md…</div>}
        {error && <div className="journey-callout critical">{error}</div>}
        {!busy && (
          <DualReportTabs integrity={integrity} promo={promo} defaultTab={defaultTab} />
        )}
      </div>
    </div>
  )
}
