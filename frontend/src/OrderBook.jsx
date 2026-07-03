function formatPrice(value) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 8,
    minimumFractionDigits: 2,
  })
}

function formatQty(value) {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: 6,
  })
}

function LevelRows({ changedLevels, levels, side }) {
  return levels.map((level) => {
    const changeKey = `${side}:${level.price}`
    const isChanged = changedLevels.has(changeKey)

    return (
      <tr className={isChanged ? 'changed' : ''} key={changeKey}>
        <td className={side}>{formatPrice(level.price)}</td>
        <td>{formatQty(level.qty)}</td>
      </tr>
    )
  })
}

export function OrderBook({ asks, bids, changedLevels }) {
  const bestBid = bids[0]?.price
  const bestAsk = asks[0]?.price
  const spread = bestBid && bestAsk ? bestAsk - bestBid : null
  const midpoint = bestBid && bestAsk ? (bestAsk + bestBid) / 2 : null
  const spreadBps = spread && midpoint ? (spread / midpoint) * 10000 : null

  return (
    <section className="panel order-book">
      <div className="panel-header">
        <h2>Order Book</h2>
        <span>
          {spreadBps === null
            ? 'Spread pending'
            : `Spread ${formatPrice(spread)} (${spreadBps.toFixed(2)} bps)`}
        </span>
      </div>

      <div className="book-grid">
        <div>
          <h3>Asks</h3>
          <table>
            <thead>
              <tr>
                <th>Price</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              <LevelRows changedLevels={changedLevels} levels={asks} side="ask" />
            </tbody>
          </table>
        </div>

        <div>
          <h3>Bids</h3>
          <table>
            <thead>
              <tr>
                <th>Price</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              <LevelRows changedLevels={changedLevels} levels={bids} side="bid" />
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
