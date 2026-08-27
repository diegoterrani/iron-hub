import type { BonusCategory } from '../types'

export function CategoryBadge({ category }: { category: BonusCategory }) {
  return <span className={`badge ${category}`}>{category}</span>
}
