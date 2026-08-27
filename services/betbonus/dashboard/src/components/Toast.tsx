export function Toast({
  message,
  error,
  onClose,
}: {
  message: string
  error?: boolean
  onClose: () => void
}) {
  return (
    <div className={`toast ${error ? 'error' : ''}`} role="status">
      <div>{message}</div>
      <button className="btn btn-ghost" style={{ marginTop: 8 }} onClick={onClose}>
        Fechar
      </button>
    </div>
  )
}
