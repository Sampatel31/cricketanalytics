import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import { formatCurrency } from '../utils/format'
import clsx from 'clsx'

export default function BudgetBar(): React.ReactElement {
  const { budget_total, budget_spent, budget_remaining } = useAuctionStore()
  const pct = budget_total > 0 ? (budget_spent / budget_total) * 100 : 0

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-[#9c9a92]">Budget</span>
        <span className="text-[#e8e6df] font-medium">{formatCurrency(budget_total, 0)}</span>
      </div>
      <div className="relative h-3 bg-[#1e1e30] rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-500',
            pct > 80 ? 'bg-[#d85a30]' : pct > 60 ? 'bg-[#ef9f27]' : 'bg-[#1d9e75]'
          )}
          style={{ width: `${Math.min(pct, 100)}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-[#1d9e75]">Spent: {formatCurrency(budget_spent)}</span>
        <span className="text-[#9c9a92]">Remaining: {formatCurrency(budget_remaining)}</span>
      </div>
    </div>
  )
}
