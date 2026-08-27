function scoreTier(score: number): 'critical' | 'high' | 'medium' | 'low' {
  if (score < 30) return 'critical'
  if (score < 50) return 'high'
  if (score < 70) return 'medium'
  return 'low'
}

export function ScoreBar({ score }: { score: number }) {
  const width = Math.max(0, Math.min(100, score))
  const tier = scoreTier(score)
  return (
    <div className="score-cell">
      <strong>{score.toFixed(1)}</strong>
      <div className={`score-bar score-bar--${tier}`} aria-hidden>
        <i style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}
