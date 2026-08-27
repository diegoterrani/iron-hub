import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { BonusDrawer } from '../components/BonusDrawer'
import { CategoryBadge } from '../components/CategoryBadge'
import { ScoreBar } from '../components/ScoreBar'
import { Toast } from '../components/Toast'
import type { BonusOffer } from '../types'

export function Bonuses() {
  const [offers, setOffers] = useState<BonusOffer[]>([])
  const [selected, setSelected] = useState<BonusOffer | null>(null)
  const [q, setQ] = useState('')
  const [platform, setPlatform] = useState('')
  const [category, setCategory] = useState('')
  const [minScore, setMinScore] = useState('')
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const load = async () => {
    const data = await api.bonuses({
      q: q || undefined,
      platform: platform || undefined,
      category: category || undefined,
      min_score: minScore ? Number(minScore) : undefined,
    })
    setOffers(data)
  }

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  const onDelete = async (id: string) => {
    await api.deleteBonus(id)
    setSelected(null)
    setToast({ message: 'Bônus removido' })
    await load()
  }

  const onClear = async () => {
    if (!confirm('Limpar todos os bônus armazenados?')) return
    const res = await api.clearBonuses()
    setToast({ message: `${res.deleted} removidos` })
    await load()
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Bonuses</h2>
          <p>Inventário classificado — filtre, inspecione breakdown e limpe ofertas antigas.</p>
        </div>
        <button className="btn btn-danger" onClick={onClear}>
          Limpar tudo
        </button>
      </div>

      <div className="panel">
        <div className="toolbar">
          <div className="field" style={{ flex: 1, minWidth: 180 }}>
            <label>Busca</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="título, plataforma…" />
          </div>
          <div className="field">
            <label>Platform</label>
            <input value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="bet365" />
          </div>
          <div className="field">
            <label>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">Todas</option>
              <option value="excellent">excellent</option>
              <option value="good">good</option>
              <option value="average">average</option>
              <option value="poor">poor</option>
              <option value="avoid">avoid</option>
            </select>
          </div>
          <div className="field">
            <label>Min score</label>
            <input
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              type="number"
              min={0}
              max={100}
              placeholder="0"
            />
          </div>
          <div className="field" style={{ alignSelf: 'end' }}>
            <label>&nbsp;</label>
            <button className="btn btn-primary" onClick={() => load().catch((e: Error) => setToast({ message: e.message, error: true }))}>
              Filtrar
            </button>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Title</th>
                <th>Platform</th>
                <th>Type</th>
                <th>Value</th>
                <th>Wagering</th>
                <th>Category</th>
              </tr>
            </thead>
            <tbody>
              {offers.map((offer) => (
                <tr key={offer.id} style={{ cursor: 'pointer' }} onClick={() => setSelected(offer)}>
                  <td>
                    <ScoreBar score={offer.score} />
                  </td>
                  <td>
                    <strong>{offer.title}</strong>
                  </td>
                  <td>{offer.platform}</td>
                  <td>{offer.bonus_type}</td>
                  <td>
                    {offer.amount} {offer.currency}
                  </td>
                  <td>{offer.wagering_multiple}x</td>
                  <td>
                    <CategoryBadge category={offer.category} />
                  </td>
                </tr>
              ))}
              {offers.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="empty">Nenhum bônus encontrado.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <BonusDrawer offer={selected} onClose={() => setSelected(null)} onDelete={onDelete} />
      )}
      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
