import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import { formatCurrency } from '../utils/format'
import { dnaMatchColor, archetypeColor } from '../utils/color'
import clsx from 'clsx'

export default function PlayerCard(): React.ReactElement {
  const { current_player_data, show_player_card, setShowPlayerCard, session_id } = useAuctionStore()

  const handleBidMax = () => {
    if (!current_player_data || !session_id) return
    console.info('Bid max for', current_player_data.player_name)
  }

  const handleStop = () => {
    setShowPlayerCard(false)
  }

  if (!show_player_card || !current_player_data) {
    return (
      <div className="panel h-full flex items-center justify-center">
        <div className="text-center text-[#9c9a92]">
          <div className="text-4xl mb-2">🏏</div>
          <p className="text-sm">Waiting for next lot...</p>
        </div>
      </div>
    )
  }

  const p = current_player_data
  const homologyPct = Math.round(p.homology * 100)
  const matchColor = dnaMatchColor(homologyPct)
  const acColor = archetypeColor(p.archetype_code)

  return (
    <div className={clsx('panel h-full overflow-y-auto animate-slide-in-right', show_player_card ? 'block' : 'hidden')}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-[#e8e6df]">{p.player_name}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm text-[#9c9a92]">{p.age} yrs</span>
            {p.country && <span className="text-sm text-[#9c9a92]">{p.country}</span>}
          </div>
        </div>
        <button
          onClick={handleStop}
          aria-label="Close player card"
          className="text-[#9c9a92] hover:text-[#e8e6df] text-xl leading-none"
        >
          ×
        </button>
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-[#9c9a92]">DNA Match</span>
          <span className="text-lg font-bold" style={{ color: matchColor }}>{homologyPct}%</span>
        </div>
        <div className="h-2 bg-[#1e1e30] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${homologyPct}%`, backgroundColor: matchColor }}
            role="progressbar"
            aria-valuenow={homologyPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: acColor + '40', backgroundColor: acColor + '15' }}>
        <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ backgroundColor: acColor + '33', color: acColor }}>
          {p.archetype_code}
        </span>
        <span className="ml-2 text-sm text-[#e8e6df]">{p.archetype_label}</span>
        <p className="text-xs text-[#9c9a92] mt-1">{p.recommendation}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-2 bg-[#1d9e75]/10 border border-[#1d9e75]/30 rounded-lg">
          <p className="text-xs text-[#9c9a92]">Fair Value</p>
          <p className="text-lg font-bold text-[#1d9e75]">{formatCurrency(p.fair_value)}</p>
        </div>
        <div className="p-2 bg-[#111120] border border-[#1e1e30] rounded-lg">
          <p className="text-xs text-[#9c9a92]">Market Price</p>
          <p className="text-lg font-bold text-[#9c9a92]">{formatCurrency(p.market_price)}</p>
        </div>
      </div>

      {p.arbitrage_gap !== 0 && (
        <div className={clsx('p-2 rounded-lg mb-4 text-sm font-semibold', p.arbitrage_gap > 0 ? 'bg-[#1d9e75]/10 text-[#1d9e75]' : 'bg-[#d85a30]/10 text-[#d85a30]')}>
          Gap: {p.arbitrage_gap > 0 ? '+' : ''}{formatCurrency(p.arbitrage_gap)}{p.arbitrage_pct !== undefined ? ` (${p.arbitrage_pct > 0 ? '+' : ''}${p.arbitrage_pct.toFixed(1)}%)` : ''}
        </div>
      )}

      {p.similar_player && (
        <p className="text-xs text-[#9c9a92] mb-4">
          {p.similar_player_pct ?? 0}% similar to <span className="text-[#e8e6df]">{p.similar_player}</span>
          {p.similar_player_price !== undefined && <span className="text-[#1d9e75]"> ({formatCurrency(p.similar_player_price)})</span>}
        </p>
      )}

      <div className="flex gap-3 mt-auto pt-4">
        <button
          onClick={handleBidMax}
          className="flex-1 py-2.5 rounded-lg bg-[#1d9e75] text-white font-bold hover:bg-[#179060] transition-colors"
          aria-label={`Bid max ${formatCurrency(p.fair_value)} for ${p.player_name}`}
        >
          BID MAX {formatCurrency(p.fair_value)}
        </button>
        <button
          onClick={handleStop}
          className="flex-1 py-2.5 rounded-lg border border-[#d85a30] text-[#d85a30] font-bold hover:bg-[#d85a30]/10 transition-colors"
          aria-label={`Stop bidding on ${p.player_name}`}
        >
          STOP BIDDING
        </button>
      </div>
    </div>
  )
}
