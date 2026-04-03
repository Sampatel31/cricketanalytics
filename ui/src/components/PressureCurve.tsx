import React, { useEffect, useState } from 'react'
import { useAuctionStore } from '../store/auction.store'
import { playerAPI } from '../services/api'
import { archetypeColor } from '../utils/color'
import type { PressureCurveData } from '../types/player'

export default function PressureCurve(): React.ReactElement {
  const { current_player_data } = useAuctionStore()
  const [curveData, setCurveData] = useState<PressureCurveData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!current_player_data) {
      setCurveData(null)
      return
    }
    setLoading(true)
    playerAPI
      .pressureCurve(current_player_data.player_id)
      .then((res) => setCurveData(res.data as PressureCurveData))
      .catch(() => setCurveData(null))
      .finally(() => setLoading(false))
  }, [current_player_data?.player_id])

  const color = current_player_data ? archetypeColor(current_player_data.archetype_code) : '#7f77dd'
  const tiers = curveData?.tiers ?? ['Low', 'Medium', 'High', 'Extreme']
  const sr = curveData?.strike_rates ?? []
  const avgSr = curveData?.avg_strike_rates ?? []

  const DEFAULT_MAX_STRIKE_RATE = 150
  const CHART_HEIGHT = 120
  const CHART_WIDTH = 300
  const PADDING_LEFT = 36
  const PADDING_BOTTOM = 24
  const PADDING_RIGHT = 8
  const PADDING_TOP = 8
  const innerW = CHART_WIDTH - PADDING_LEFT - PADDING_RIGHT
  const innerH = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM

  const maxSR = Math.max(...sr, ...avgSr, DEFAULT_MAX_STRIKE_RATE)

  function toX(i: number): number {
    return PADDING_LEFT + (i / (tiers.length - 1)) * innerW
  }
  function toY(v: number): number {
    return PADDING_TOP + innerH - (v / maxSR) * innerH
  }

  function buildPath(values: number[]): string {
    if (values.length < 2) return ''
    return values.map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i)},${toY(v)}`).join(' ')
  }

  return (
    <div className="panel h-full flex flex-col">
      <h3 className="text-sm font-semibold text-[#e8e6df] mb-3">📈 Pressure Curve</h3>
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#9c9a92] text-sm">Loading...</div>
      ) : !current_player_data ? (
        <div className="flex-1 flex items-center justify-center text-[#9c9a92] text-sm">Select a player</div>
      ) : (
        <div className="flex-1 flex flex-col">
          <svg
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            className="w-full"
            aria-label="Pressure curve chart"
            role="img"
          >
            {[0, 50, 100, 150].map((v) => (
              <g key={v}>
                <line
                  x1={PADDING_LEFT} y1={toY(v)} x2={CHART_WIDTH - PADDING_RIGHT} y2={toY(v)}
                  stroke="#1e1e30" strokeWidth="1"
                />
                <text x={PADDING_LEFT - 4} y={toY(v) + 4} textAnchor="end" fontSize="9" fill="#9c9a92">{v}</text>
              </g>
            ))}
            {tiers.map((tier, i) => (
              <text key={tier} x={toX(i)} y={CHART_HEIGHT - 2} textAnchor="middle" fontSize="9" fill="#9c9a92">{tier}</text>
            ))}
            {avgSr.length >= 2 && (
              <path d={buildPath(avgSr)} fill="none" stroke="#9c9a92" strokeWidth="1.5" strokeDasharray="4,2" />
            )}
            {sr.length >= 2 && (
              <path d={buildPath(sr)} fill="none" stroke={color} strokeWidth="2" />
            )}
            {sr.map((v, i) => (
              <circle key={i} cx={toX(i)} cy={toY(v)} r="3" fill={color} />
            ))}
          </svg>
          <div className="flex gap-4 mt-2 text-[10px]">
            <span className="flex items-center gap-1">
              <span className="w-4 border-t-2" style={{ borderColor: color }} />
              <span className="text-[#9c9a92]">{current_player_data.player_name}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-4 border-t border-dashed border-[#9c9a92]" />
              <span className="text-[#9c9a92]">Average</span>
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
