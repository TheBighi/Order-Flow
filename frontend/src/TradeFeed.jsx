import { useEffect, useState } from 'react'

const WS_BASE_URL = 'ws://localhost:8000'

export function TradeFeed({ symbol }) {
  const [status, setStatus] = useState('not connected')
  const [trades, setTrades] = useState([])

  useEffect(() => {
    if (!symbol) {
      return undefined
    }

    const ws = new WebSocket(`${WS_BASE_URL}/ws/trades/${symbol}`)

    ws.onopen = () => {
      setStatus('connected')
    }

    ws.onmessage = (event) => {
      const trade = JSON.parse(event.data)
      setTrades((currentTrades) => [trade, ...currentTrades.slice(0, 49)])
    }

    ws.onerror = () => {
      setStatus('trades channel unavailable')
    }

    ws.onclose = () => {
      setStatus('not connected')
    }

    return () => {
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
              <span>{trade.price}</span>
              <span>{trade.qty}</span>
            </div>
          ))
        ) : (
          <p className="empty-state">Trade WebSocket is not built on the backend yet.</p>
        )}
      </div>
    </section>
  )
}
