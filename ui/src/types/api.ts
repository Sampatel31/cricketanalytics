export interface APIResponse<T> {
  data: T
  status: number
  message?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface WSMessage {
  type: string
  session_id?: string
  data: Record<string, unknown>
  timestamp?: string
}

export interface DNASliderRequest {
  format_type: 'T20I' | 'ODI' | 'TEST'
  weights: Record<string, number>
  franchise_name?: string
}

export interface DNAExemplarRequest {
  format_type: 'T20I' | 'ODI' | 'TEST'
  player_ids: string[]
  franchise_name?: string
}

export interface DNAHistoricalRequest {
  format_type: 'T20I' | 'ODI' | 'TEST'
  team_name: string
  seasons?: number[]
  franchise_name?: string
}

export interface FranchiseDNA {
  dna_id: string
  franchise_name: string
  format_type: string
  archetype_targets: Record<string, number>
  feature_weights: Record<string, number>
  created_at: string
}
