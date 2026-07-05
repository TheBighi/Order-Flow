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
    disconnect,
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

  function handleDisconnect() {
    disconnect()
  }

  const displaySymbol = symbol.replace('USDT', '/USDT')
  const displayPrice = lastDelta
    ? Number(lastDelta.price).toLocaleString(undefined, {
        maximumFractionDigits: 2,
        minimumFractionDigits: 2,
      })
    : '--'
  const priceDirection = lastDelta?.side === 'ask' ? 'down' : 'up'
  const deltaValue = lastDelta
    ? Number(lastDelta.qty).toLocaleString(undefined, {
        maximumFractionDigits: 6,
      })
    : '--'

  return (
    <main className="terminal-shell">
      <header className="terminal-topbar">
        <div className="brand-cluster">
          <span className="brand-mark">~</span>
          <strong>ORDERFLOW</strong>
        </div>

        <div className="market-strip">
          <select
            aria-label="Symbol"
            value={selectedSymbol}
            onChange={(event) => setSelectedSymbol(event.target.value)}
          >
            {SYMBOLS.map((nextSymbol) => (
              <option key={nextSymbol} value={nextSymbol}>
                {nextSymbol.replace('USDT', '/USDT')}
              </option>
            ))}
          </select>
          <span className={`last-price ${priceDirection}`}>
            {displayPrice} {lastDelta ? `${lastDelta.side} ${deltaValue}` : 'waiting'}
          </span>
        </div>

        <div className="connection-actions">
          <span className={`status-pill ${status}`}>
            <span />
            {status}
          </span>
          <button className="connect-button" type="button" onClick={handleSymbolConnect}>
            Connect
          </button>
          <button className="disconnect-button" type="button" onClick={handleDisconnect}>
            Disconnect
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">{error}</p> : null}

      <section className="terminal-grid">
        <OrderBook asks={asks} bids={bids} changedLevels={changedLevels} />

        <section className="center-column">
          <DepthChart asks={asks} bids={bids} />

          <section className="terminal-panel latest-delta">
            <div className="panel-header">
              <h2>Latest Delta</h2>
              <span>{lastDelta ? new Date(lastDelta.timestamp).toLocaleTimeString() : displaySymbol}</span>
            </div>
            <div className="delta-grid">
              <div>
                <span>{lastDelta ? `${lastDelta.side} delta` : 'waiting'}</span>
                <strong className={lastDelta?.side === 'ask' ? 'ask' : 'bid'}>
                  {lastDelta ? Number(lastDelta.price).toLocaleString() : '--'}
                </strong>
              </div>
              <div>
                <span>Delta change</span>
                <strong className={lastDelta?.side === 'ask' ? 'ask' : 'bid'}>{deltaValue}</strong>
              </div>
            </div>
          </section>

          <MetricsPanel
            renderMs={renderMs}
            status={status}
            symbol={symbol}
            updatesPerSecond={updatesPerSecond}
          />
        </section>

        <TradeFeed key={symbol} symbol={symbol} />
      </section>
    </main>
  )
}

export default App
