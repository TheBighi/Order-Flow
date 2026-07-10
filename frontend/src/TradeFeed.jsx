import { useEffect, useState } from 'react'

const BACKEND_URL = import.meta.env.BACKEND_URL

const API_BASE_URL = 'http://' + BACKEND_URL
const WS_BASE_URL = 'ws://' + BACKEND_URL

function formatPrice(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 8,
    minimumFractionDigits: 2,
  })
}

function formatQty(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 4,
  })
}

function formatTime(timestamp) {
  if (!timestamp) {
    return '--:--:--'
  }

  return new Date(timestamp).toLocaleTimeString(undefined, {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function TradeFeed({ enabled, symbol }) {
  const [status, setStatus] = useState('not connected')
  const [trades, setTrades] = useState([])

  useEffect(() => {
    if (!enabled || !symbol) {
      return undefined
    }

    let isCurrent = true

    async function loadRecentTrades() {
      try {
        const response = await fetch(`${API_BASE_URL}/trades/${symbol}`)
        const snapshot = await response.json()

        if (isCurrent && Array.isArray(snapshot.trades)) {
          setTrades(snapshot.trades)
        }
      } catch {
        // The WebSocket snapshot below can still fill this panel.
      }
    }

    loadRecentTrades()

    const ws = new WebSocket(`${WS_BASE_URL}/ws/trades/${symbol}`)

    ws.onopen = () => {
      if (!isCurrent) {
        return
      }

      setStatus('connected')
    }

    ws.onmessage = (event) => {
      if (!isCurrent) {
        return
      }

      const message = JSON.parse(event.data)

      if (message.type === 'trade_snapshot' && Array.isArray(message.data)) {
        setTrades(message.data)
        return
      }

      if (message.type === 'trade' && message.data) {
        setTrades((currentTrades) => [message.data, ...currentTrades.slice(0, 49)])
      }
    }

    ws.onerror = () => {
      if (isCurrent) {
        setStatus('trades channel unavailable')
      }
    }

    ws.onclose = () => {
      if (isCurrent) {
        setStatus('not connected')
      }
    }

    return () => {
      isCurrent = false
      ws.close()
    }
  }, [enabled, symbol])

  const displayStatus = enabled
    ? status === 'not connected'
      ? 'connecting'
      : status
    : 'not connected'
  const visibleTrades = enabled ? trades : []

  return (
    <section className="terminal-panel trade-feed">
      <div className="panel-header">
        <h2>Live Trades</h2>
        <span className={displayStatus === 'connected' ? 'live-dot' : ''}>{displayStatus}</span>
      </div>

      <div className="trade-heading">
        <span>Time</span>
        <span>Price</span>
        <span>Qty</span>
      </div>

      <div className="trade-list">
        {visibleTrades.length ? (
          visibleTrades.map((trade, index) => (
            <div
              className={trade.side === 'sell' ? 'sell' : 'buy'}
              key={`${trade.timestamp}-${index}`}
            >
              <span>{formatTime(trade.timestamp)}</span>
              <span>{formatPrice(trade.price)}</span>
              <span>{formatQty(trade.qty)}</span>
            </div>
          ))
        ) : (
          <p className="empty-state">Waiting for trades</p>
        )}
      </div>
    </section>
  )
}
