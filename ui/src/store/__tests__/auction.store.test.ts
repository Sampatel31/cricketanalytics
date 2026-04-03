import { useAuctionStore } from '../../store/auction.store'

describe('auction.store', () => {
  beforeEach(() => {
    useAuctionStore.setState({
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
    })
  })

  it('sets session id', () => {
    useAuctionStore.getState().setSessionId('abc123')
    expect(useAuctionStore.getState().session_id).toBe('abc123')
  })

  it('updates budget', () => {
    useAuctionStore.getState().updateBudget(35)
    expect(useAuctionStore.getState().budget_spent).toBe(35)
    expect(useAuctionStore.getState().budget_remaining).toBe(65)
  })

  it('adds picked player', () => {
    useAuctionStore.getState().addPickedPlayer('player1')
    expect(useAuctionStore.getState().players_locked_in).toContain('player1')
  })

  it('adds and removes alerts', () => {
    const alert = { id: 'a1', type: 'info' as const, message: 'Test', severity: 'info' as const, timestamp: new Date().toISOString() }
    useAuctionStore.getState().addAlert(alert)
    expect(useAuctionStore.getState().alerts).toHaveLength(1)
    useAuctionStore.getState().removeAlert('a1')
    expect(useAuctionStore.getState().alerts).toHaveLength(0)
  })

  it('sets ws connected', () => {
    useAuctionStore.getState().setWSConnected(true)
    expect(useAuctionStore.getState().ws_connected).toBe(true)
    expect(useAuctionStore.getState().ws_reconnecting).toBe(false)
  })
})
