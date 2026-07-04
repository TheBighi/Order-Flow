import { useEffect, useMemo, useRef, useState } from 'react'

function cumulativeRows(levels) {
  let cumulative = 0

  return levels.map((level) => {
    cumulative += Number(level.qty)

    return {
      price: Number(level.price),
      qty: Number(level.qty),
      cumulative,
    }
  })
}

function cloneRows(rows) {
  return rows.map((row) => ({ ...row }))
}

function easeRows(currentRows, targetRows, alpha) {
  return targetRows.map((targetRow, index) => {
    const currentRow = currentRows[index] || targetRow

    return {
      ...targetRow,
      cumulative:
        currentRow.cumulative + (targetRow.cumulative - currentRow.cumulative) * alpha,
    }
  })
}

function nearestRow(rows, index) {
  if (!rows.length) {
    return null
  }

  return rows[Math.max(0, Math.min(rows.length - 1, index))]
}

function formatLadderPrice(value) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatLadderQty(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 6,
  })
}

function DepthLadder({ asks, bids, levels = 10 }) {
  const visibleAsks = asks.slice(0, levels)
  const visibleBids = bids.slice(0, levels)

  // Farthest ask at the top, best ask sitting right above the spread —
  // asks arrive sorted best-first (ascending price), so reverse for display.
  const orderedAsks = [...visibleAsks].reverse()

  const maxQty = Math.max(
    1,
    ...visibleAsks.map((level) => Number(level.qty)),
    ...visibleBids.map((level) => Number(level.qty)),
  )

  function LadderRow({ level, side }) {
    const isAsk = side === 'ask'
    const barWidth = `${Math.max(2, (Number(level.qty) / maxQty) * 100)}%`

    return (
      <div
        key={`${side}:${level.price}`}
        style={{
          position: 'relative',
          display: 'flex',
          justifyContent: 'space-between',
          padding: '2px 8px',
          fontFamily: 'ui-monospace, Consolas, monospace',
          fontSize: '12px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            right: 0,
            width: barWidth,
            background: isAsk ? 'rgba(220, 38, 38, 0.22)' : 'rgba(22, 163, 74, 0.22)',
          }}
        />
        <span style={{ position: 'relative', color: isAsk ? '#dc2626' : '#16a34a' }}>
          {formatLadderPrice(level.price)}
        </span>
        <span style={{ position: 'relative', color: '#e5e7eb' }}>
          {formatLadderQty(level.qty)}
        </span>
      </div>
    )
  }

  return (
    <div className="depth-ladder" style={{ marginTop: '16px' }}>
      {orderedAsks.map((level) => (
        <LadderRow level={level} side="ask" key={`ask:${level.price}`} />
      ))}
      <div
        style={{
          borderTop: '1px solid #4b5563',
          borderBottom: '1px solid #4b5563',
          margin: '4px 0',
          padding: '2px 8px',
          fontSize: '11px',
          color: '#9ca3af',
        }}
      >
        Spread
      </div>
      {visibleBids.map((level) => (
        <LadderRow level={level} side="bid" key={`bid:${level.price}`} />
      ))}
    </div>
  )
}

export function DepthChart({ asks, bids }) {
  const canvasRef = useRef(null)
  const animationRef = useRef(null)
  const maxCumulativeRef = useRef(1)
  const targetRowsRef = useRef({ asks: [], bids: [] })
  const displayRowsRef = useRef({ asks: [], bids: [] })
  const [hoverPoint, setHoverPoint] = useState(null)

  const chartData = useMemo(() => {
    return {
      asks: cumulativeRows(asks),
      bids: cumulativeRows(bids),
    }
  }, [asks, bids])

  useEffect(() => {
    targetRowsRef.current = chartData

    if (!displayRowsRef.current.asks.length && !displayRowsRef.current.bids.length) {
      displayRowsRef.current = {
        asks: cloneRows(chartData.asks),
        bids: cloneRows(chartData.bids),
      }
    }
  }, [chartData])

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas.getContext('2d')

    function draw() {
      const width = canvas.clientWidth
      const height = canvas.clientHeight
      const ratio = window.devicePixelRatio || 1

      if (
        canvas.width !== Math.floor(width * ratio) ||
        canvas.height !== Math.floor(height * ratio)
      ) {
        canvas.width = Math.floor(width * ratio)
        canvas.height = Math.floor(height * ratio)
      }

      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.clearRect(0, 0, width, height)

      displayRowsRef.current = {
        asks: easeRows(displayRowsRef.current.asks, targetRowsRef.current.asks, 0.14),
        bids: easeRows(displayRowsRef.current.bids, targetRowsRef.current.bids, 0.14),
      }

      const askRows = displayRowsRef.current.asks
      const bidRows = displayRowsRef.current.bids
      const allRows = [...bidRows, ...askRows]

      if (!allRows.length) {
        context.fillStyle = '#6b7280'
        context.font = '13px ui-monospace, Consolas, monospace'
        context.fillText('Waiting for depth data', 16, 28)
        animationRef.current = window.requestAnimationFrame(draw)
        return
      }

      const padding = 24
      const centerX = width / 2
      const chartBottom = height - padding
      const chartTop = padding
      const chartHeight = chartBottom - chartTop
      const sideWidth = centerX - padding
      const currentMaxCumulative = Math.max(...allRows.map((row) => row.cumulative), 1)
      const smoothedMaxCumulative =
        maxCumulativeRef.current * 0.95 + currentMaxCumulative * 0.05

      maxCumulativeRef.current = Math.max(
        smoothedMaxCumulative,
        currentMaxCumulative * 0.8,
        1,
      )

      function yFor(cumulative) {
        return chartBottom - (cumulative / maxCumulativeRef.current) * chartHeight
      }

      function xFor(index, count, side) {
        const progress = count <= 1 ? 0 : index / (count - 1)

        if (side === 'bid') {
          return centerX - progress * sideWidth
        }

        return centerX + progress * sideWidth
      }

      function drawSide(rows, side, color, fillColor) {
        if (!rows.length) {
          return
        }

        context.beginPath()
        context.moveTo(centerX, chartBottom)

        rows.forEach((row, index) => {
          context.lineTo(xFor(index, rows.length, side), yFor(row.cumulative))
        })

        const lastX = xFor(rows.length - 1, rows.length, side)
        context.lineTo(lastX, chartBottom)
        context.closePath()
        context.fillStyle = fillColor
        context.fill()

        context.beginPath()
        rows.forEach((row, index) => {
          const x = xFor(index, rows.length, side)
          const y = yFor(row.cumulative)

          if (index === 0) {
            context.moveTo(x, y)
          } else {
            context.lineTo(x, y)
          }
        })

        context.strokeStyle = color
        context.lineWidth = 2
        context.stroke()
      }

      context.strokeStyle = '#d1d5db'
      context.lineWidth = 1
      context.beginPath()
      context.moveTo(padding, chartBottom)
      context.lineTo(width - padding, chartBottom)
      context.moveTo(centerX, chartTop)
      context.lineTo(centerX, chartBottom)
      context.stroke()

      context.fillStyle = '#9ca3af'
      context.font = '12px ui-monospace, Consolas, monospace'
      context.textBaseline = 'middle'
      context.textAlign = 'center'
      context.fillText('Bid levels', centerX - sideWidth / 2, chartBottom + 14)
      context.fillText('Ask levels', centerX + sideWidth / 2, chartBottom + 14)
      context.fillText('Spread', centerX, chartTop - 10)

      context.save()
      context.translate(10, height / 2)
      context.rotate(-Math.PI / 2)
      context.fillText('Cumulative quantity', 0, 0)
      context.restore()

      context.textAlign = 'left'
      context.fillText('more depth', padding, chartTop)
      context.fillText('less depth', padding, chartBottom - 12)

      drawSide(bidRows, 'bid', '#16a34a', 'rgba(22, 163, 74, 0.16)')
      drawSide(askRows, 'ask', '#dc2626', 'rgba(220, 38, 38, 0.16)')

      animationRef.current = window.requestAnimationFrame(draw)
    }

    animationRef.current = window.requestAnimationFrame(draw)

    return () => {
      window.cancelAnimationFrame(animationRef.current)
    }
  }, [])

  function handlePointerMove(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - rect.left
    const isBidSide = x < rect.width / 2
    const rows = isBidSide ? targetRowsRef.current.bids : targetRowsRef.current.asks
    const sideWidth = rect.width / 2
    const distanceFromCenter = Math.abs(x - rect.width / 2)
    const index = Math.round((distanceFromCenter / sideWidth) * (rows.length - 1))
    const nearest = nearestRow(rows, index)

    setHoverPoint(nearest ? { ...nearest, side: isBidSide ? 'bid' : 'ask' } : null)
  }

  return (
    <section className="panel depth-chart">
      <div className="panel-header">
        <h2>Depth</h2>
        <span>
          {hoverPoint
            ? `${hoverPoint.side} ${hoverPoint.price.toFixed(2)} / ${hoverPoint.cumulative.toFixed(4)}`
            : 'Hover for level'}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        onPointerLeave={() => setHoverPoint(null)}
        onPointerMove={handlePointerMove}
      />
      <DepthLadder asks={asks} bids={bids} />
    </section>
  )
}