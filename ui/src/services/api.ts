import axios from 'axios'
import { API_BASE_URL } from '../config/constants'
import type { PlayerFilter } from '../types/player'
import type {
  AuctionSessionRequest,
  PickConfirmRequest,
} from '../types/auction'
import type {
  DNASliderRequest,
  DNAExemplarRequest,
  DNAHistoricalRequest,
} from '../types/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API error:', error?.response?.data ?? error.message)
    return Promise.reject(error)
  }
)

export const playerAPI = {
  list: (params?: PlayerFilter) => api.get('/api/v1/players', { params }),
  get: (id: string) => api.get(`/api/v1/players/${id}`),
  search: (q: string) => api.get('/api/v1/players/search', { params: { q } }),
  pressureCurve: (id: string) => api.get(`/api/v1/players/${id}/pressure-curve`),
}

export const auctionAPI = {
  createSession: (data: AuctionSessionRequest) =>
    api.post('/api/v1/auction/session', data),
  getSession: (id: string) => api.get(`/api/v1/auction/session/${id}`),
  pick: (sessionId: string, data: PickConfirmRequest) =>
    api.post(`/api/v1/auction/session/${sessionId}/pick`, data),
  scores: (sessionId: string, lots: string[]) =>
    api.get(`/api/v1/auction/${sessionId}/scores`, {
      params: { upcoming_lots: lots },
    }),
  report: (sessionId: string) => api.get(`/api/v1/auction/${sessionId}/report`),
}

export const dnaAPI = {
  slider: (data: DNASliderRequest) => api.post('/api/v1/dna/slider', data),
  exemplar: (data: DNAExemplarRequest) => api.post('/api/v1/dna/exemplar', data),
  historical: (data: DNAHistoricalRequest) =>
    api.post('/api/v1/dna/historical', data),
  get: (id: string) => api.get(`/api/v1/dna/${id}`),
  score: (dnaId: string, playerIds: string[]) =>
    api.post(`/api/v1/dna/${dnaId}/score`, { player_ids: playerIds }),
}

export default api
