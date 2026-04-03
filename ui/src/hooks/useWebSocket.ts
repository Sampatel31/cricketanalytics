import { useEffect, useRef } from 'react'
import { WebSocketClient } from '../services/websocket'
import { useAuctionStore } from '../store/auction.store'
import type { Alert, OverbidData } from '../types/auction'
import type { PlayerCard } from '../types/player'

function generateId(): string {
  return Math.random().toString(36).slice(2, 11)
}

function formatCr(value: number): string {
  return `₹${value.toFixed(1)}Cr`
}

export function useWebSocket(session_id: string): void {
  const store = useAuctionStore()
  const clientRef = useRef<WebSocketClient | null>(null)

  useEffect(() => {
    if (!session_id) return

    const client = new WebSocketClient(session_id)
    clientRef.current = client

    client.on('connected', () => {
      store.setWSConnected(true)
    })

    client.on('disconnected', () => {
      store.setWSConnected(false)
    })

    client.on('reconnecting', () => {
      store.setWSReconnecting(true)
    })

    client.on('player_card', (data) => {
      const playerData = data as unknown as PlayerCard
      store.setCurrentPlayer(playerData.player_id, playerData)
    })

    client.on('overbid_alert', (data) => {
      const overbid = data as unknown as OverbidData
      store.showOverbidModal(overbid)
      store.addAlert({
        id: generateId(),
        type: 'overbid',
        message: `⚠️ Over max bid! Current: ${formatCr(overbid.current_bid)}, Max: ${formatCr(overbid.max_ceiling)}`,
        severity: 'warning',
        timestamp: new Date().toISOString(),
        data: data as Record<string, unknown>,
      })
    })

    client.on('squad_update', (data) => {
      const update = data as { budget_spent?: number; archetype_balance?: Record<string, number>; squad_dna_score?: number }
      if (update.budget_spent !== undefined) {
        store.updateBudget(update.budget_spent)
      }
      if (update.archetype_balance) {
        store.updateArchetypeBalance(update.archetype_balance)
      }
      store.addAlert({
        id: generateId(),
        type: 'picked',
        message: `✅ Squad updated`,
        severity: 'success',
        timestamp: new Date().toISOString(),
      })
    })

    client.on('archetype_gap_alert', (data) => {
      const gap = data as { archetype_label?: string }
      store.addAlert({
        id: generateId(),
        type: 'archetype_gap',
        message: `🚨 Missing ${gap.archetype_label ?? 'archetype'}!`,
        severity: 'error',
        timestamp: new Date().toISOString(),
        data: data as Record<string, unknown>,
      })
    })

    client.on('error', (data) => {
      store.addAlert({
        id: generateId(),
        type: 'error',
        message: `🔴 Connection error: ${String(data.error ?? 'Unknown')}`,
        severity: 'error',
        timestamp: new Date().toISOString(),
      } as Alert)
    })

    client.connect().catch((err: unknown) => {
      console.error('WebSocket connection failed:', err)
    })

    return () => {
      client.disconnect()
      clientRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session_id])
}
