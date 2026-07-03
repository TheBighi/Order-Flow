import { useState } from 'react'
import { DepthChart } from './DepthChart.jsx'
import { MetricsPanel } from './MetricsPanel.jsx'
import { OrderBook } from './OrderBook.jsx'
import { TradeFeed } from './TradeFeed.jsx'
import { useOrderBook } from './useOrderBook.js'
import './App.css'

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']

function App() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT')
  const {
    asks,
    bids,
    changedLevels,
    connect,
    error,
    lastDelta,
    renderMs,
    status,
    symbol,
    updatesPerSecond,
  } = useOrderBook()

  function handleSymbolConnect() {
    connect(selectedSymbol)
  }

  return (
    <main className="app-shell">
      <section className="top-bar">
        <div>
          <h1>Order Book</h1>
          <p>{symbol}</p>
        </div>

        <div className="symbol-controls">
          <select
            aria-label="Symbol"
            value={selectedSymbol}
            onChange={(event) => setSelectedSymbol(event.target.value)}
          >
            {SYMBOLS.map((nextSymbol) => (
              <option key={nextSymbol} value={nextSymbol}>
                {nextSymbol}
              </option>
            ))}
          </select>

          <button type="button" onClick={handleSymbolConnect}>
            Connect
          </button>
        </div>
      </section>

      {error ? <p className="error-banner">{error}</p> : null}

      <section className="dashboard-grid">
        <OrderBook asks={asks} bids={bids} changedLevels={changedLevels} />
        <DepthChart asks={asks} bids={bids} />
        <MetricsPanel
          renderMs={renderMs}
          status={status}
          symbol={symbol}
          updatesPerSecond={updatesPerSecond}
        />
        <TradeFeed symbol={symbol} />
      </section>

      <section className="panel latest-delta">
        <div className="panel-header">
          <h2>Latest Delta</h2>
          <span>{lastDelta ? lastDelta.side : 'waiting'}</span>
        </div>
        <pre>{lastDelta ? JSON.stringify(lastDelta, null, 2) : 'No delta received yet'}</pre>
      </section>
    </main>
  )
}

export default App
