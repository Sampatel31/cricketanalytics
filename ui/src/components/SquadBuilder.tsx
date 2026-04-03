import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import BudgetBar from './BudgetBar'
import ArchetypeBalance from './ArchetypeBalance'
import { formatCurrency } from '../utils/format'
import { SQUAD_SIZE } from '../config/constants'

export default function SquadBuilder(): React.ReactElement {
  const { players_locked_in, squad_dna_score, budget_spent } = useAuctionStore()
  const avgPrice = players_locked_in.length > 0 ? budget_spent / players_locked_in.length : 0

  return (
    <div className="panel h-full overflow-y-auto flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-[#e8e6df]">🏗️ Squad Builder</h3>

      <BudgetBar />

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="p-2 bg-[#111120] rounded-lg border border-[#1e1e30]">
          <p className="text-xs text-[#9c9a92]">Players</p>
          <p className="text-lg font-bold text-[#e8e6df]">{players_locked_in.length}/{SQUAD_SIZE}</p>
        </div>
        <div className="p-2 bg-[#111120] rounded-lg border border-[#1e1e30]">
          <p className="text-xs text-[#9c9a92]">DNA Score</p>
          <p className="text-lg font-bold text-[#7f77dd]">{squad_dna_score.toFixed(2)}</p>
        </div>
        <div className="p-2 bg-[#111120] rounded-lg border border-[#1e1e30]">
          <p className="text-xs text-[#9c9a92]">Avg Price</p>
          <p className="text-lg font-bold text-[#e8e6df]">{players_locked_in.length > 0 ? formatCurrency(avgPrice) : '—'}</p>
        </div>
      </div>

      <div>
        <p className="text-xs text-[#9c9a92] mb-2 uppercase tracking-wide">Archetype Balance</p>
        <ArchetypeBalance />
      </div>
    </div>
  )
}
