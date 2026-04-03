import { renderHook } from '@testing-library/react'
import { useAuctionState } from '../useAuctionState'

describe('useAuctionState', () => {
  it('returns store state', () => {
    const { result } = renderHook(() => useAuctionState())
    expect(result.current).toBeDefined()
    expect(typeof result.current.session_id).toBe('string')
    expect(typeof result.current.budget_total).toBe('number')
  })
})
