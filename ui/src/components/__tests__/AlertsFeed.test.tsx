import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import AlertsFeed from '../AlertsFeed'
import { useAuctionStore } from '../../store/auction.store'

describe('AlertsFeed', () => {
  beforeEach(() => {
    useAuctionStore.setState({ alerts: [] })
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it('shows empty state', () => {
    render(<AlertsFeed />)
    expect(screen.getByText(/No alerts yet/i)).toBeInTheDocument()
  })

  it('shows alerts when present', () => {
    useAuctionStore.setState({
      alerts: [{
        id: 'a1',
        type: 'info',
        message: 'Test alert message',
        severity: 'info',
        timestamp: new Date().toISOString(),
      }],
    })
    render(<AlertsFeed />)
    expect(screen.getByText('Test alert message')).toBeInTheDocument()
  })

  it('dismisses alert on button click', () => {
    useAuctionStore.setState({
      alerts: [{
        id: 'a1',
        type: 'info',
        message: 'Dismiss me',
        severity: 'info',
        timestamp: new Date().toISOString(),
      }],
    })
    render(<AlertsFeed />)
    const dismissBtn = screen.getByLabelText('Dismiss alert')
    fireEvent.click(dismissBtn)
    expect(useAuctionStore.getState().alerts).toHaveLength(0)
  })
})
