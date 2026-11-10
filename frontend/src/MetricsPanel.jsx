import { useEffect, useState } from 'react'
import { API_BASE_URL } from './config'

function parseConnectedClients(metricsText, symbol) {
  const pattern = new RegExp(`connected_clients\\{symbol="${symbol}"\\} ([0-9.]+)`)
  const match = metricsText.match(pattern)

  return match ? Number(match[1]) : 0
}

function parseBackpressureClients(metricsText, symbol) {
  const pattern = new RegExp(`backpressure_clients\\{symbol="${symbol}"\\} ([0-9.]+)`)
  const match = metricsText.match(pattern)

  return match ? Number(match[1]) : 0
}

function parseMaxQueueDepth(metricsText, symbol) {
  const pattern = new RegExp(
    `backpressure_queue_depth\\{symbol="${symbol}",client_id="[^"]+"\\} ([0-9.]+)`,
    'g',
  )
  const matches = [...metricsText.matchAll(pattern)]

  if (!matches.length) {
    return 0
  }

  return Math.max(...matches.map((match) => Number(match[1])))
}

function formatBackpressure(localStatus, warningClients, maxQueueDepth) {
  if (localStatus !== 'ok') {
    return localStatus
  }

  if (warningClients > 0) {
    return `${warningClients} warning`
  }

  if (maxQueueDepth > 0) {
    return `queued ${maxQueueDepth}`
  }

  return 'ok'
}

function backpressureClass(localStatus, warningClients, maxQueueDepth) {
  if (localStatus === 'failed') {
    return 'failed'
  }

  if (localStatus !== 'ok' || warningClients > 0 || maxQueueDepth > 0) {
    return 'warning'
  }

  return 'ok'
}

export function MetricsPanel({
  backpressureStatus,
  renderMs,
  status,
  symbol,
  updatesPerSecond,
}) {
  const [connectedClients, setConnectedClients] = useState(0)
  const [backpressureClients, setBackpressureClients] = useState(0)
  const [maxQueueDepth, setMaxQueueDepth] = useState(0)
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
        setBackpressureClients(parseBackpressureClients(text, symbol))
        setMaxQueueDepth(parseMaxQueueDepth(text, symbol))
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
          <dd
            className={`backpressure-state ${backpressureClass(
              backpressureStatus,
              backpressureClients,
              maxQueueDepth,
            )}`}
          >
            {formatBackpressure(backpressureStatus, backpressureClients, maxQueueDepth)}
          </dd>
        </div>
      </dl>
    </section>
  )
}
