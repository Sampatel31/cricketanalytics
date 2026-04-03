export interface AuctionSession {
  session_id: string
  franchise_name: string
  budget_total: number
  budget_spent: number
  budget_remaining: number
  format_type: 'T20I' | 'ODI' | 'TEST'
  players_locked_in: string[]
  archetype_balance: Record<string, number>
  squad_dna_score: number
  created_at: string
}

export interface Alert {
  id: string
  type: 'overbid' | 'archetype_gap' | 'budget' | 'picked' | 'error' | 'info'
  message: string
  severity: 'info' | 'warning' | 'error' | 'success'
  timestamp: string
  data?: Record<string, unknown>
}

export interface OverbidData {
  player_name: string
  current_bid: number
  max_ceiling: number
  overpay_amount: number
  overpay_pct: number
  alternatives: Array<{ player_id: string; player_name: string; price: number }>
}

export interface AuctionSessionRequest {
  franchise_name: string
  budget_total: number
  format_type: 'T20I' | 'ODI' | 'TEST'
  dna_id?: string
}

export interface PickConfirmRequest {
  player_id: string
  price: number
}

export interface UpcomingTarget {
  player_id: string
  player_name: string
  archetype_code: string
  archetype_label: string
  dna_match_pct: number
  max_bid: number
  lot_number?: number
  already_picked?: boolean
}
