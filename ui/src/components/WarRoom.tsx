import React from 'react'
import GalaxyView from './GalaxyView'
import PlayerCard from './PlayerCard'
import SquadBuilder from './SquadBuilder'
import PressureCurve from './PressureCurve'
import UpcomingTargets from './UpcomingTargets'
import AlertsFeed from './AlertsFeed'
import OverbidAlert from './OverbidAlert'
import Header from './Header'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuctionStore } from '../store/auction.store'

export default function WarRoom(): React.ReactElement {
  const { session_id } = useAuctionStore()
  useWebSocket(session_id)

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] overflow-hidden">
      <Header />

      <main className="flex-1 overflow-hidden p-5">
        <div
          className="grid h-full gap-4"
          style={{
            gridTemplateColumns: 'repeat(6, 1fr)',
            gridTemplateRows: 'repeat(3, 1fr)',
          }}
        >
          <div style={{ gridColumn: '1 / 3', gridRow: '1 / 4' }}>
            <GalaxyView />
          </div>
          <div style={{ gridColumn: '3 / 5', gridRow: '1 / 3' }}>
            <PlayerCard />
          </div>
          <div style={{ gridColumn: '5 / 7', gridRow: '1 / 3' }}>
            <SquadBuilder />
          </div>
          <div style={{ gridColumn: '3 / 5', gridRow: '3 / 4' }}>
            <PressureCurve />
          </div>
          <div style={{ gridColumn: '5 / 6', gridRow: '3 / 4' }}>
            <UpcomingTargets />
          </div>
          <div style={{ gridColumn: '6 / 7', gridRow: '3 / 4' }}>
            <AlertsFeed />
          </div>
        </div>
      </main>

      <OverbidAlert />
    </div>
  )
}
