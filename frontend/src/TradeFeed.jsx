import { useEffect, useState } from 'react'

const API_BASE_URL = 'http://localhost:8000'
const WS_BASE_URL = 'ws://localhost:8000'

function formatPrice(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 8,
    minimumFractionDigits: 2,
  })
}

function formatQty(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 6,
  })
}

export function TradeFeed({ symbol }) {
  const [status, setStatus] = useState('connecting')
  const [trades, setTrades] = useState([])

  useEffect(() => {
    if (!symbol) {
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
  }, [symbol])

  return (
    <section className="panel trade-feed">
      <div className="panel-header">
        <h2>Trades</h2>
        <span>{status}</span>
      </div>

      <div className="trade-list">
        {trades.length ? (
          trades.map((trade, index) => (
            <div className={trade.side === 'sell' ? 'sell' : 'buy'} key={`${trade.timestamp}-${index}`}>
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
