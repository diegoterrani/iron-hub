import type { BonusOffer } from '../types'
import { CategoryBadge } from './CategoryBadge'
import { ScoreBar } from './ScoreBar'

export function BonusDrawer({
  offer,
  onClose,
  onDelete,
}: {
  offer: BonusOffer
  onClose: () => void
  onDelete: (id: string) => void
}) {
  const maxBreak = Math.max(...Object.values(offer.score_breakdown), 1)

  return (
    <div className="drawer" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="page-head" style={{ marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 18 }}>{offer.title || 'Bonus'}</h2>
            <p>
              {offer.platform} · {offer.bonus_type}
            </p>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 }}>
          <CategoryBadge category={offer.category} />
          <ScoreBar score={offer.score} />
        </div>

        <div className="panel">
          <h3>Detalhes</h3>
          <p>
            <strong>
              {offer.amount} {offer.currency}
            </strong>
            {offer.match_percent != null ? ` · ${offer.match_percent}% match` : ''}
            {offer.free_spins != null ? ` · ${offer.free_spins} free spins` : ''}
          </p>
          <p className="muted">
            Wagering {offer.wagering_multiple}x · Min deposit {offer.min_deposit} · Expiry{' '}
            {offer.expiry_hours != null ? `${offer.expiry_hours}h` : `${offer.expiry_days}d`}
          </p>
          {offer.game_restrictions.length > 0 && (
            <div className="chip-row" style={{ marginTop: 10 }}>
              {offer.game_restrictions.map((r) => (
                <span className="chip" key={r}>
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="panel" style={{ marginTop: 12 }}>
          <h3>Score breakdown</h3>
          <div className="breakdown">
            {Object.entries(offer.score_breakdown).map(([key, value]) => (
              <div className="breakdown-row" key={key}>
                <span>{key}</span>
                <div className="track">
                  <i style={{ width: `${Math.max(0, (value / maxBreak) * 100)}%` }} />
                </div>
                <strong>{value.toFixed(1)}</strong>
              </div>
            ))}
          </div>
        </div>

        {offer.raw_text && (
          <div className="panel" style={{ marginTop: 12 }}>
            <h3>Texto fonte</h3>
            <p className="muted" style={{ whiteSpace: 'pre-wrap' }}>
              {offer.raw_text}
            </p>
          </div>
        )}

        <div className="actions" style={{ marginTop: 16 }}>
          <button className="btn btn-danger" onClick={() => onDelete(offer.id)}>
            Remover
          </button>
        </div>
      </div>
    </div>
  )
}
