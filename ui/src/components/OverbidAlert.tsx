import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import { formatCurrency } from '../utils/format'

interface Props {
  onStop?: () => void
  onContinue?: () => void
}

export default function OverbidAlert({ onStop, onContinue }: Props): React.ReactElement | null {
  const { show_overbid_modal, overbid_data, hideOverbidModal } = useAuctionStore()

  if (!show_overbid_modal || !overbid_data) return null

  const { player_name, current_bid, max_ceiling, overpay_amount, overpay_pct, alternatives } = overbid_data

  const handleStop = () => {
    hideOverbidModal()
    onStop?.()
  }

  const handleContinue = () => {
    hideOverbidModal()
    onContinue?.()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="overbid-title"
    >
      <div className="absolute inset-0 bg-black/70" onClick={handleStop} />
      <div className="relative z-10 bg-[#0d0d18] border border-[#d85a30]/50 rounded-2xl p-6 max-w-md w-full shadow-2xl animate-fade-in">
        <h2 id="overbid-title" className="text-lg font-bold text-[#d85a30] mb-4">⚠️ OVERBID WARNING</h2>

        <div className="space-y-3 mb-4">
          <p className="text-[#9c9a92] text-sm">Player: <span className="text-[#e8e6df] font-semibold">{player_name}</span></p>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-xs text-[#9c9a92]">Current Bid</p>
              <p className="text-2xl font-bold text-[#d85a30]">{formatCurrency(current_bid)}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-[#9c9a92]">Max Ceiling</p>
              <p className="text-xl font-semibold text-[#9c9a92]">{formatCurrency(max_ceiling)}</p>
            </div>
          </div>
          <div className="p-3 bg-[#d85a30]/10 rounded-lg border border-[#d85a30]/30">
            <p className="text-[#d85a30] font-semibold">
              Overpay: +{formatCurrency(overpay_amount)} (+{overpay_pct.toFixed(0)}%)
            </p>
          </div>
        </div>

        {alternatives.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-[#9c9a92] mb-2">Same archetype, cheaper alternatives:</p>
            <ul className="space-y-1">
              {alternatives.slice(0, 3).map((alt) => (
                <li key={alt.player_id} className="flex justify-between text-sm">
                  <span className="text-[#e8e6df]">{alt.player_name}</span>
                  <span className="text-[#1d9e75]">{formatCurrency(alt.price)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleStop}
            className="flex-1 py-2 rounded-lg bg-[#d85a30] text-white font-bold hover:bg-[#c04a20] transition-colors"
          >
            STOP
          </button>
          <button
            onClick={handleContinue}
            className="flex-1 py-2 rounded-lg border border-[#ef9f27] text-[#ef9f27] font-bold hover:bg-[#ef9f27]/10 transition-colors"
          >
            CONTINUE ANYWAY
          </button>
        </div>
      </div>
    </div>
  )
}
