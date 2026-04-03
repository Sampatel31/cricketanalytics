import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import { archetypeColor } from '../utils/color'
import clsx from 'clsx'

const ARCHETYPE_TARGETS: Record<string, number> = {
  FSH: 3,
  AGA: 4,
  PRB: 3,
  CON: 4,
  FIN: 3,
  ALL: 4,
  SPC: 2,
}

const ARCHETYPE_LABELS: Record<string, string> = {
  FSH: 'Format Shapeshifter',
  AGA: 'Aggressive Anchor',
  PRB: 'Pressure Responder',
  CON: 'Controller',
  FIN: 'Finisher',
  ALL: 'All-rounder',
  SPC: 'Specialist',
}

export default function ArchetypeBalance(): React.ReactElement {
  const { archetype_balance } = useAuctionStore()

  return (
    <div className="grid grid-cols-2 gap-2">
      {Object.entries(ARCHETYPE_TARGETS).map(([code, target]) => {
        const current = archetype_balance[code] ?? 0
        const complete = current >= target
        const partial = current > 0 && current < target

        return (
          <div
            key={code}
            className={clsx(
              'p-2 rounded-lg border',
              complete ? 'border-[#1d9e75]/40 bg-[#1d9e75]/10' :
              partial ? 'border-[#ef9f27]/40 bg-[#ef9f27]/10' :
              'border-[#d85a30]/40 bg-[#d85a30]/10'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span
                className="text-xs font-bold px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor: archetypeColor(code) + '33',
                  color: archetypeColor(code),
                }}
              >
                {code}
              </span>
              <span className={clsx('text-xs font-semibold', complete ? 'text-[#1d9e75]' : partial ? 'text-[#ef9f27]' : 'text-[#d85a30]')}>
                {current}/{target} {complete ? '✅' : partial ? '⬜' : '❌'}
              </span>
            </div>
            <div className="text-[10px] text-[#9c9a92] truncate">{ARCHETYPE_LABELS[code]}</div>
            <div className="mt-1 h-1 bg-[#1e1e30] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.min((current / target) * 100, 100)}%`,
                  backgroundColor: archetypeColor(code),
                }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
