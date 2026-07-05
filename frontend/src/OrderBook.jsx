function formatPrice(value) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 8,
    minimumFractionDigits: 2,
  })
}

function formatQty(value) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 4,
  })
}

function LevelRows({ changedLevels, levels, maxQty, side }) {
  return levels.map((level) => {
    const changeKey = `${side}:${level.price}`
    const isChanged = changedLevels.has(changeKey)
    const barWidth = `${Math.max(2, (Number(level.qty) / maxQty) * 100)}%`

    return (
      <div className={`book-row ${side} ${isChanged ? 'changed' : ''}`} key={changeKey}>
        <span className="book-depth-bar" style={{ width: barWidth }} />
        <span className="book-price">{formatPrice(level.price)}</span>
        <span className="book-qty">{formatQty(level.qty)}</span>
      </div>
    )
  })
}

export function OrderBook({ asks, bids, changedLevels }) {
  const bestBid = bids[0]?.price
  const bestAsk = asks[0]?.price
  const spread = bestBid && bestAsk ? bestAsk - bestBid : null
  const midpoint = bestBid && bestAsk ? (bestAsk + bestBid) / 2 : null
  const spreadBps = spread && midpoint ? (spread / midpoint) * 10000 : null
  const visibleAsks = asks.slice(0, 20)
  const visibleBids = bids.slice(0, 20)
  const maxQty = Math.max(
    1,
    ...visibleAsks.map((level) => Number(level.qty)),
    ...visibleBids.map((level) => Number(level.qty)),
  )

  return (
    <section className="terminal-panel order-book">
      <div className="panel-header">
        <h2>Order Book</h2>
        <span>
          {spreadBps === null
            ? 'Spread pending'
            : `Spread ${formatPrice(spread)} (${spreadBps.toFixed(2)} bps)`}
        </span>
      </div>

      <div className="book-grid">
        <div className="book-side ask-side">
          <h3>Asks</h3>
          <div className="book-labels">
            <span>Price</span>
            <span>Qty</span>
          </div>
          <LevelRows
            changedLevels={changedLevels}
            levels={visibleAsks}
            maxQty={maxQty}
            side="ask"
          />
        </div>

        <div className="book-side bid-side">
          <h3>Bids</h3>
          <div className="book-labels">
            <span>Price</span>
            <span>Qty</span>
          </div>
          <LevelRows
            changedLevels={changedLevels}
            levels={visibleBids}
            maxQty={maxQty}
            side="bid"
          />
        </div>
      </div>
    </section>
  )
}
