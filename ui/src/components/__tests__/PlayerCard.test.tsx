import React from 'react'
import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import PlayerCard from '../PlayerCard'
import { useAuctionStore } from '../../store/auction.store'

describe('PlayerCard', () => {
  it('shows waiting state when no player', () => {
    useAuctionStore.setState({ show_player_card: false, current_player_data: null })
    render(<PlayerCard />)
    expect(screen.getByText(/Waiting for next lot/i)).toBeInTheDocument()
  })

  it('shows player data when available', () => {
    useAuctionStore.setState({
      show_player_card: true,
      current_player_data: {
        player_id: 'p1',
        player_name: 'Virat Kohli',
        age: 35,
        features: {},
        archetype_code: 'AGA',
        archetype_label: 'Aggressive Anchor',
        homology: 0.92,
        fair_value: 16,
        market_price: 14,
        arbitrage_gap: 2,
        recommendation: 'Strong buy',
      },
    })
    render(<PlayerCard />)
    expect(screen.getByText('Virat Kohli')).toBeInTheDocument()
    expect(screen.getByText('92%')).toBeInTheDocument()
  })
})
