import React, { useState } from 'react'
import { useAuctionStore } from '../store/auction.store'
import ConnectionStatus from './ConnectionStatus'

export default function Header(): React.ReactElement {
  const { franchise_name, format_type, session_id } = useAuctionStore()
  const [elapsed, setElapsed] = useState('00:00')
  const startRef = React.useRef(Date.now())

  React.useEffect(() => {
    const timer = setInterval(() => {
      const diff = Math.floor((Date.now() - startRef.current) / 1000)
      const mm = String(Math.floor(diff / 60)).padStart(2, '0')
      const ss = String(diff % 60).padStart(2, '0')
      setElapsed(`${mm}:${ss}`)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-[#1e1e30] bg-[#0d0d18]">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-[#7f77dd] flex items-center justify-center font-bold text-white text-sm">
          S
        </div>
        <span className="text-white font-bold text-lg tracking-wide">War Room</span>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-[#e8e6df] font-semibold">{franchise_name}</span>
        <span className="px-2 py-0.5 rounded text-xs font-bold bg-[#7f77dd]/20 text-[#7f77dd] border border-[#7f77dd]/30">
          {format_type}
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-[#9c9a92] text-sm">
          <span className="mr-2">Session:</span>
          <span className="text-[#e8e6df] font-mono text-xs">{session_id ? session_id.slice(0, 8) + '...' : '—'}</span>
        </div>
        <div className="text-[#9c9a92] text-sm font-mono">{elapsed}</div>
        <ConnectionStatus />
      </div>
    </header>
  )
}
