import React, { useEffect, useRef, useState } from 'react'
import { usePlayers } from '../hooks/usePlayers'
import { useAuctionStore } from '../store/auction.store'
import { archetypeColor } from '../utils/color'
import type { Player } from '../types/player'

interface TooltipState {
  x: number
  y: number
  player: Player
}

export default function GalaxyView(): React.ReactElement {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const { players, loading } = usePlayers()
  const store = useAuctionStore()
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [dims, setDims] = useState({ w: 600, h: 400 })

  useEffect(() => {
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDims({
          w: entry.contentRect.width,
          h: entry.contentRect.height,
        })
      }
    })
    if (containerRef.current) obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  const playersWithPos = React.useMemo(() => {
    if (!players.length) return []
    const xs = players.map((p) => p.umap_x ?? 0)
    const ys = players.map((p) => p.umap_y ?? 0)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const rangeX = maxX - minX || 1
    const rangeY = maxY - minY || 1
    const pad = 40

    return players.map((p) => ({
      ...p,
      cx: pad + (((p.umap_x ?? 0) - minX) / rangeX) * (dims.w - pad * 2),
      cy: pad + (((p.umap_y ?? 0) - minY) / rangeY) * (dims.h - pad * 2),
      r: 4 + Math.min(8, (p.market_price ?? 1) * 0.5),
    }))
  }, [players, dims])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, dims.w, dims.h)

    playersWithPos.forEach((p) => {
      const isHovered = p.player_id === hoveredId
      const alpha = hoveredId && !isHovered ? 0.3 : 1
      const color = archetypeColor(p.archetype_code)

      ctx.save()
      ctx.globalAlpha = alpha
      ctx.beginPath()
      ctx.arc(p.cx, p.cy, isHovered ? p.r + 3 : p.r, 0, Math.PI * 2)
      ctx.fillStyle = color + (isHovered ? 'ff' : 'cc')
      ctx.fill()
      if (isHovered) {
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()
        ctx.shadowBlur = 12
        ctx.shadowColor = color
      }
      ctx.restore()
    })
  }, [playersWithPos, hoveredId, dims])

  function handleMouseMove(e: React.MouseEvent<HTMLCanvasElement>): void {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    let nearest: (typeof playersWithPos)[0] | null = null
    let minDist = 16

    for (const p of playersWithPos) {
      const d = Math.hypot(p.cx - mx, p.cy - my)
      if (d < minDist) {
        minDist = d
        nearest = p
      }
    }

    if (nearest) {
      setHoveredId(nearest.player_id)
      setTooltip({ x: mx, y: my, player: nearest })
    } else {
      setHoveredId(null)
      setTooltip(null)
    }
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>): void {
    const rect = (e.target as HTMLCanvasElement).getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top

    for (const p of playersWithPos) {
      const d = Math.hypot(p.cx - mx, p.cy - my)
      if (d < p.r + 4) {
        store.setCurrentPlayer(p.player_id, null)
        break
      }
    }
  }

  return (
    <div ref={containerRef} className="panel h-full flex flex-col relative">
      <h3 className="text-sm font-semibold text-[#e8e6df] mb-3">🌌 Galaxy View</h3>
      {loading ? (
        <div className="flex-1 flex items-center justify-center text-[#9c9a92]">Loading players...</div>
      ) : (
        <div className="flex-1 relative">
          <canvas
            ref={canvasRef}
            width={dims.w}
            height={dims.h - 40}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => { setHoveredId(null); setTooltip(null) }}
            onClick={handleClick}
            className="w-full h-full cursor-crosshair"
            aria-label="Player galaxy scatter plot"
            role="img"
          />
          {tooltip && (
            <div
              className="absolute z-10 pointer-events-none bg-[#111120] border border-[#1e1e30] rounded-lg p-2 text-xs shadow-lg"
              style={{
                left: Math.min(tooltip.x + 12, dims.w - 160),
                top: Math.max(tooltip.y - 40, 0),
              }}
            >
              <p className="text-[#e8e6df] font-semibold">{tooltip.player.player_name}</p>
              <p className="text-[#9c9a92]">{tooltip.player.archetype_label}</p>
              {tooltip.player.market_price !== undefined && (
                <p className="text-[#1d9e75]">₹{tooltip.player.market_price}Cr</p>
              )}
            </div>
          )}
          <div className="absolute bottom-2 left-2 flex flex-wrap gap-2">
            {['FSH', 'AGA', 'PRB', 'CON', 'FIN', 'ALL', 'SPC'].map((code) => (
              <div key={code} className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: archetypeColor(code) }} />
                <span className="text-[9px] text-[#9c9a92]">{code}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
