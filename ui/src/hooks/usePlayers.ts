import { useState, useEffect } from 'react'
import { playerAPI } from '../services/api'
import type { Player, PlayerFilter } from '../types/player'

export function usePlayers(filter?: PlayerFilter) {
  const [players, setPlayers] = useState<Player[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    playerAPI
      .list(filter)
      .then((res) => {
        if (!cancelled) {
          const data = res.data
          setPlayers(Array.isArray(data) ? data : data.items ?? [])
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load players')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [filter?.archetype, filter?.format, filter?.q])

  return { players, loading, error }
}
