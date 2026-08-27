import { MODE_LEGEND, modeClass } from '../lib/casino'

export function CoverageLegend() {
  return (
    <div className="coverage-legend" aria-label="Legenda da cobertura">
      <p className="coverage-legend-lead">
        Cada célula é o pior resultado do último run naquele eixo da casa. Não mede conversão de
        bônus.
      </p>
      <ul className="coverage-legend-list">
        {MODE_LEGEND.map((row) => (
          <li key={row.mode}>
            <span className={modeClass(row.mode)}>{row.label}</span>
            <span>{row.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
