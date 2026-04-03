import React from 'react'
import { useAuctionStore } from '../store/auction.store'
import clsx from 'clsx'

interface Props {
  onReconnect?: () => void
}

export default function ConnectionStatus({ onReconnect }: Props): React.ReactElement {
  const { ws_connected, ws_reconnecting } = useAuctionStore()

  const status = ws_connected ? 'connected' : ws_reconnecting ? 'reconnecting' : 'disconnected'

  const dotColor = {
    connected: 'bg-green-500',
    reconnecting: 'bg-yellow-400 animate-blink',
    disconnected: 'bg-red-500',
  }[status]

  const label = {
    connected: 'Connected',
    reconnecting: 'Reconnecting...',
    disconnected: 'Disconnected',
  }[status]

  return (
    <button
      onClick={!ws_connected ? onReconnect : undefined}
      title={ws_connected ? 'WebSocket connected' : 'Click to reconnect'}
      aria-label={`WebSocket status: ${label}`}
      className={clsx(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
        'border border-[#1e1e30] bg-[#111120] transition-colors',
        !ws_connected && 'cursor-pointer hover:border-[#7f77dd]'
      )}
    >
      <span className={clsx('w-2 h-2 rounded-full', dotColor)} />
      <span className={ws_connected ? 'text-green-400' : ws_reconnecting ? 'text-yellow-300' : 'text-red-400'}>
        {label}
      </span>
    </button>
  )
}
