import React, { useState, useEffect } from 'react'
import { useAuctionStore } from '../store/auction.store'
import { auctionAPI } from '../services/api'
import { archetypeColor, dnaMatchColor } from '../utils/color'
import { formatCurrency } from '../utils/format'
import type { UpcomingTarget } from '../types/auction'
import clsx from 'clsx'

export default function UpcomingTargets(): React.ReactElement {
  const { session_id, players_locked_in, setCurrentPlayer } = useAuctionStore()
  const [targets, setTargets] = useState<UpcomingTarget[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!session_id) return
    setLoading(true)
    auctionAPI
      .scores(session_id, [])
      .then((res) => {
        const data = res.data
        const items: UpcomingTarget[] = Array.isArray(data) ? data : data.targets ?? data.players ?? []
        setTargets(items.slice(0, 5))
      })
      .catch(() => setTargets([]))
      .finally(() => setLoading(false))
  }, [session_id, players_locked_in.length])

  return (
    <div className="panel h-full flex flex-col">
      <h3 className="text-sm font-semibold text-[#e8e6df] mb-3">🎯 Upcoming Targets</h3>
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#9c9a92] text-sm">Loading...</div>
      ) : targets.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-[#9c9a92] text-sm">
          {session_id ? 'No targets available' : 'Start a session to see targets'}
        </div>
      ) : (
        <ul className="space-y-2 overflow-y-auto flex-1">
          {targets.map((t) => {
            const picked = players_locked_in.includes(t.player_id)
            return (
              <li key={t.player_id}>
                <button
                  onClick={() => !picked && setCurrentPlayer(t.player_id, null)}
                  className={clsx(
                    'w-full text-left p-2 rounded-lg border transition-colors',
                    picked
                      ? 'border-[#1e1e30] opacity-50 cursor-default'
                      : 'border-[#1e1e30] hover:border-[#7f77dd]/50 cursor-pointer'
                  )}
                  disabled={picked}
                  aria-label={`${t.player_name} - ${t.dna_match_pct}% DNA match`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[#e8e6df] truncate">{t.player_name}</span>
                    <span className="text-xs font-bold ml-2 shrink-0" style={{ color: dnaMatchColor(t.dna_match_pct) }}>
                      {t.dna_match_pct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                      style={{
                        backgroundColor: archetypeColor(t.archetype_code) + '33',
                        color: archetypeColor(t.archetype_code),
                      }}
                    >
                      {t.archetype_code}
                    </span>
                    <span className="text-xs text-[#1d9e75]">{formatCurrency(t.max_bid)}</span>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
