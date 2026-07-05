import { useEffect, useState } from 'react'

const API_BASE_URL = 'http://localhost:8000'

function parseConnectedClients(metricsText, symbol) {
  const pattern = new RegExp(`connected_clients\\{symbol="${symbol}"\\} ([0-9.]+)`)
  const match = metricsText.match(pattern)

  return match ? Number(match[1]) : 0
}

export function MetricsPanel({ renderMs, status, symbol, updatesPerSecond }) {
  const [connectedClients, setConnectedClients] = useState(0)
  const [metricsStatus, setMetricsStatus] = useState('idle')

  useEffect(() => {
    let isMounted = true

    async function loadMetrics() {
      try {
        const response = await fetch(`${API_BASE_URL}/metrics`)
        const text = await response.text()

        if (!isMounted) {
          return
        }

        setConnectedClients(parseConnectedClients(text, symbol))
        setMetricsStatus('live')
      } catch {
        if (isMounted) {
          setMetricsStatus('unavailable')
        }
      }
    }

    loadMetrics()
    const interval = window.setInterval(loadMetrics, 2000)

    return () => {
      isMounted = false
      window.clearInterval(interval)
    }
  }, [symbol])

  return (
    <section className="terminal-panel metrics-panel">
      <div className="panel-header">
        <h2>Metrics</h2>
        <span>{metricsStatus}</span>
      </div>

      <dl>
        <div>
          <dt>Status</dt>
          <dd>{status}</dd>
        </div>
        <div>
          <dt>Updates/sec</dt>
          <dd>{updatesPerSecond}</dd>
        </div>
        <div>
          <dt>Render ms</dt>
          <dd>{renderMs.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Clients</dt>
          <dd>{connectedClients}</dd>
        </div>
        <div>
          <dt>Backpressure</dt>
          <dd>not built</dd>
        </div>
      </dl>
    </section>
  )
}
