import http from 'k6/http'
import ws from 'k6/ws'
import { check, sleep } from 'k6'
import { Counter, Rate } from 'k6/metrics'

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']
const HTTP_BASE_URL = __ENV.HTTP_BASE_URL || 'http://host.docker.internal:8000'
const WS_BASE_URL = __ENV.WS_BASE_URL || 'ws://host.docker.internal:8000'
const TEST_DURATION_SECONDS = Number(__ENV.TEST_DURATION_SECONDS || 60)
const MAX_VUS = Number(__ENV.MAX_VUS || 200)
const SNAPSHOT_RETRY_SLEEP_SECONDS = Number(__ENV.SNAPSHOT_RETRY_SLEEP_SECONDS || 5)

function stagesForMaxVus(maxVus) {
  if (maxVus <= 200) {
    return [
      { duration: '30s', target: 25 },
      { duration: '1m', target: 100 },
      { duration: '1m', target: 200 },
      { duration: '30s', target: 0 },
    ]
  }

  return [
    { duration: '30s', target: 100 },
    { duration: '1m', target: 250 },
    { duration: '1m', target: 500 },
    { duration: '1m', target: maxVus },
    { duration: '1m', target: maxVus },
    { duration: '1m', target: 0 },
  ]
}

const snapshotFailures = new Counter('snapshot_failures_total')
const snapshotSuccess = new Rate('snapshot_success')
const wsMessages = new Counter('ws_messages_total')
const wsDeltaBatches = new Counter('ws_delta_batches_total')
const wsResyncs = new Counter('ws_resync_required_total')
const wsConnectFailures = new Counter('ws_connect_failures_total')
const wsConnected = new Rate('ws_connected')

export const options = {
  scenarios: {
    websocket_spike: {
      executor: 'ramping-vus',
      stages: stagesForMaxVus(MAX_VUS),
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    snapshot_success: ['rate>0.95'],
    snapshot_failures_total: ['count<20'],
    ws_connected: ['rate>0.95'],
    ws_connect_failures_total: ['count<20'],
    ws_resync_required_total: ['count<50'],
  },
}

function symbolForVu() {
  return SYMBOLS[(__VU - 1) % SYMBOLS.length]
}

export default function () {
  const symbol = symbolForVu()
  const snapshotResponse = http.get(`${HTTP_BASE_URL}/snapshot/${symbol}`)
  const url = `${WS_BASE_URL}/ws/orderbook/${symbol}`

  const snapshotOk = check(snapshotResponse, {
    'snapshot status is 200': (res) => res.status === 200,
    'snapshot has order book arrays': (res) => {
      try {
        const body = res.json()
        return Array.isArray(body.bids) && Array.isArray(body.asks)
      } catch {
        return false
      }
    },
  })

  snapshotSuccess.add(snapshotOk)

  if (!snapshotOk) {
    snapshotFailures.add(1)
    wsConnectFailures.add(1)
    wsConnected.add(false)
    sleep(SNAPSHOT_RETRY_SLEEP_SECONDS)
    return
  }

  const response = ws.connect(url, null, (socket) => {
    socket.on('open', () => {
      wsConnected.add(true)
    })

    socket.on('message', (rawMessage) => {
      wsMessages.add(1)

      try {
        const message = JSON.parse(rawMessage)

        if (message.type === 'delta_batch') {
          wsDeltaBatches.add(1)
        }

        if (message.type === 'resync_required') {
          wsResyncs.add(1)
        }
      } catch {
        // Ignore non-JSON messages during load tests.
      }
    })

    socket.on('error', () => {
      wsConnectFailures.add(1)
      wsConnected.add(false)
    })

    socket.setTimeout(() => {
      socket.close()
    }, TEST_DURATION_SECONDS * 1000)
  })

  check(response, {
    'websocket status is 101': (res) => res && res.status === 101,
  })

  if (!response || response.status !== 101) {
    wsConnectFailures.add(1)
    wsConnected.add(false)
  }

  sleep(1)
}
