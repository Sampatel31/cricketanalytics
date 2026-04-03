export interface Player {
  player_id: string
  player_name: string
  age: number
  archetype_code: string
  archetype_label: string
  confidence_weight: number
  umap_x?: number
  umap_y?: number
  market_price?: number
}

export interface PlayerCard {
  player_id: string
  player_name: string
  age: number
  country?: string
  features: Record<string, number>
  archetype_code: string
  archetype_label: string
  homology: number
  fair_value: number
  market_price: number
  arbitrage_gap: number
  arbitrage_pct?: number
  recommendation: string
  similar_player?: string
  similar_player_price?: number
  similar_player_pct?: number
}

export interface PressureCurveData {
  player_id: string
  tiers: string[]
  strike_rates: number[]
  avg_strike_rates: number[]
}

export interface PlayerFilter {
  archetype?: string
  format?: string
  min_age?: number
  max_age?: number
  q?: string
}
