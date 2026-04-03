import { create } from 'zustand'
import type { Alert, OverbidData, AuctionSession } from '../types/auction'
import type { PlayerCard } from '../types/player'

interface AuctionState {
  session_id: string
  franchise_name: string
  format_type: 'T20I' | 'ODI' | 'TEST'
  budget_total: number
  budget_spent: number
  budget_remaining: number
  players_locked_in: string[]
  archetype_balance: Record<string, number>
  squad_dna_score: number
  current_player_id: string | null
  current_player_data: PlayerCard | null
  show_player_card: boolean
  show_overbid_modal: boolean
  overbid_data: OverbidData | null
  alerts: Alert[]
  ws_connected: boolean
  ws_reconnecting: boolean
  setSession(session: Partial<AuctionSession>): void
  setSessionId(id: string): void
  updateBudget(spent: number): void
  addPickedPlayer(player_id: string): void
  updateArchetypeBalance(balance: Record<string, number>): void
  setCurrentPlayer(player_id: string, data: PlayerCard | null): void
  setShowPlayerCard(show: boolean): void
  showOverbidModal(data: OverbidData): void
  hideOverbidModal(): void
  addAlert(alert: Alert): void
  removeAlert(id: string): void
  clearAlerts(): void
  setWSConnected(connected: boolean): void
  setWSReconnecting(reconnecting: boolean): void
}

export const useAuctionStore = create<AuctionState>((set) => ({
  session_id: '',
  franchise_name: 'My Franchise',
  format_type: 'T20I',
  budget_total: 100,
  budget_spent: 0,
  budget_remaining: 100,
  players_locked_in: [],
  archetype_balance: {},
  squad_dna_score: 0,
  current_player_id: null,
  current_player_data: null,
  show_player_card: false,
  show_overbid_modal: false,
  overbid_data: null,
  alerts: [],
  ws_connected: false,
  ws_reconnecting: false,

  setSession: (session) =>
    set((state) => ({
      ...state,
      session_id: session.session_id ?? state.session_id,
      franchise_name: session.franchise_name ?? state.franchise_name,
      format_type: (session.format_type as 'T20I' | 'ODI' | 'TEST') ?? state.format_type,
      budget_total: session.budget_total ?? state.budget_total,
      budget_spent: session.budget_spent ?? state.budget_spent,
      budget_remaining: session.budget_remaining ?? state.budget_remaining,
      players_locked_in: session.players_locked_in ?? state.players_locked_in,
      archetype_balance: session.archetype_balance ?? state.archetype_balance,
      squad_dna_score: session.squad_dna_score ?? state.squad_dna_score,
    })),

  setSessionId: (id) => set({ session_id: id }),

  updateBudget: (spent) =>
    set((state) => ({
      budget_spent: spent,
      budget_remaining: state.budget_total - spent,
    })),

  addPickedPlayer: (player_id) =>
    set((state) => ({
      players_locked_in: [...state.players_locked_in, player_id],
    })),

  updateArchetypeBalance: (balance) => set({ archetype_balance: balance }),

  setCurrentPlayer: (player_id, data) =>
    set({
      current_player_id: player_id,
      current_player_data: data,
      show_player_card: data !== null,
    }),

  setShowPlayerCard: (show) => set({ show_player_card: show }),

  showOverbidModal: (data) => set({ show_overbid_modal: true, overbid_data: data }),

  hideOverbidModal: () => set({ show_overbid_modal: false, overbid_data: null }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50),
    })),

  removeAlert: (id) =>
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id),
    })),

  clearAlerts: () => set({ alerts: [] }),

  setWSConnected: (connected) => set({ ws_connected: connected, ws_reconnecting: false }),

  setWSReconnecting: (reconnecting) => set({ ws_reconnecting: reconnecting }),
}))
