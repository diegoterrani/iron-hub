import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Toast } from '../components/Toast'

type WalletSummary = {
  total_entries: number
  credited: number
  totals_by_currency: Record<string, number>
  note?: string
  house_wallet?: {
    connected?: boolean
    platform?: string
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
}

export function Wallet() {
  const [data, setData] = useState<WalletSummary | null>(null)
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null)

  const load = async () => setData(await api.wallet())

  useEffect(() => {
    load().catch((e: Error) => setToast({ message: e.message, error: true }))
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Carteira</h2>
          <p>
            Ledger ops do BetBonus + saldo real da casa (quando autenticado). Registrar na jornada{' '}
            <strong>não</strong> credita a 4Play.
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-ghost" onClick={() => load()}>
            Atualizar
          </button>
          <button
            className="btn btn-danger"
            onClick={async () => {
              if (!confirm('Limpar carteira?')) return
              await api.clearWallet()
              await load()
              setToast({ message: 'Carteira limpa' })
            }}
          >
            Limpar
          </button>
        </div>
      </div>

      {data?.house_wallet?.connected && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <h3>Saldo real 4Play</h3>
          {data.house_wallet.error ? (
            <p className="muted">{data.house_wallet.error}</p>
          ) : (
            <div className="grid-stats" style={{ marginBottom: 0 }}>
              <div className="stat stat--info">
                <div className="label">Balance</div>
                <div className="value">{data.house_wallet.balance ?? '—'}</div>
              </div>
              <div className="stat stat--medium">
                <div className="label">Bonus</div>
                <div className="value">{data.house_wallet.bonus ?? '—'}</div>
              </div>
              <div className="stat stat--high">
                <div className="label">Rollover</div>
                <div className="value">{data.house_wallet.rollover ?? '—'}</div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid-stats">
        <div className="stat stat--info">
          <div className="label">Ledger entradas</div>
          <div className="value">{data?.total_entries ?? '—'}</div>
        </div>
        <div className="stat stat--low">
          <div className="label">Registrados</div>
          <div className="value">{data?.credited ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">Moedas</div>
          <div className="value">{data ? Object.keys(data.totals_by_currency).length : '—'}</div>
        </div>
        <div className="stat">
          <div className="label">Totais ledger</div>
          <div className="value" style={{ fontSize: 14 }}>
            {data && Object.keys(data.totals_by_currency).length
              ? Object.entries(data.totals_by_currency)
                  .map(([c, v]) => `${v.toLocaleString()} ${c}`)
                  .join(' · ')
              : '—'}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Quando</th>
                <th>Platform</th>
                <th>Título</th>
                <th>Valor</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((item) => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td>{item.platform}</td>
                  <td>
                    <strong>{item.title}</strong>
                  </td>
                  <td>
                    {item.amount} {item.currency}
                  </td>
                  <td>{item.source}</td>
                  <td>
                    <span className="badge good">{item.status}</span>
                  </td>
                </tr>
              ))}
              {!data?.items?.length && (
                <tr>
                  <td colSpan={6}>
                    <div className="empty">Carteira vazia — rode a Jornada e credite bônus.</div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} error={toast.error} onClose={() => setToast(null)} />
      )}
    </>
  )
}
