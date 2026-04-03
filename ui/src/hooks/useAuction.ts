import { useState } from 'react'
import { auctionAPI } from '../services/api'
import { useAuctionStore } from '../store/auction.store'
import type { AuctionSessionRequest, PickConfirmRequest } from '../types/auction'

export function useAuction() {
  const store = useAuctionStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createSession = async (data: AuctionSessionRequest) => {
    setLoading(true)
    setError(null)
    try {
      const res = await auctionAPI.createSession(data)
      const session = res.data
      store.setSession(session)
      return session
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session')
      return null
    } finally {
      setLoading(false)
    }
  }

  const confirmPick = async (data: PickConfirmRequest) => {
    if (!store.session_id) return null
    setLoading(true)
    try {
      const res = await auctionAPI.pick(store.session_id, data)
      store.addPickedPlayer(data.player_id)
      return res.data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to confirm pick')
      return null
    } finally {
      setLoading(false)
    }
  }

  return { createSession, confirmPick, loading, error }
}
