import { useCallback, useEffect, useRef, useState } from 'react'

const API_BASE_URL = 'http://localhost:8000'
const WS_BASE_URL = 'ws://localhost:8000'

function rowsToMap(rows = []) {
  return new Map(rows.map((row) => [String(row.price), row.qty]))
}

function mapToRows(levels, side) {
  const rows = Array.from(levels.entries()).map(([price, qty]) => ({
    price: Number(price),
    qty: Number(qty),
  }))

  rows.sort((a, b) => (side === 'bid' ? b.price - a.price : a.price - b.price))

  return rows.slice(0, 25)
}

export function useOrderBook() {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [status, setStatus] = useState('disconnected')
  const [bids, setBids] = useState([])
  const [asks, setAsks] = useState([])
  const [changedLevels, setChangedLevels] = useState(new Set())
  const [renderMs, setRenderMs] = useState(0)
  const [updatesPerSecond, setUpdatesPerSecond] = useState(0)
  const [lastDelta, setLastDelta] = useState(null)
  const [error, setError] = useState('')

  const wsRef = useRef(null)
  const bookRef = useRef({ bids: new Map(), asks: new Map() })
  const deltaBufferRef = useRef([])
  const frameRef = useRef(null)
  const updateCountRef = useRef(0)
  const updatesTimerRef = useRef(null)
  const changeTimerRef = useRef(null)

  const flushDeltas = useCallback(() => {
    const start = performance.now()
    const bufferedDeltas = deltaBufferRef.current
    deltaBufferRef.current = []
    frameRef.current = null

    if (!bufferedDeltas.length) {
      return
    }

    const changed = new Set()

    for (const delta of bufferedDeltas) {
      const sideKey = delta.side === 'bid' ? 'bids' : 'asks'
      const priceKey = String(delta.price)

      changed.add(`${delta.side}:${priceKey}`)

      if (Number(delta.qty) === 0) {
        bookRef.current[sideKey].delete(priceKey)
      } else {
        bookRef.current[sideKey].set(priceKey, delta.qty)
      }
    }

    setBids(mapToRows(bookRef.current.bids, 'bid'))
    setAsks(mapToRows(bookRef.current.asks, 'ask'))
    setChangedLevels(changed)
    setLastDelta(bufferedDeltas[bufferedDeltas.length - 1])
    setRenderMs(performance.now() - start)

    if (changeTimerRef.current) {
      window.clearTimeout(changeTimerRef.current)
    }

    changeTimerRef.current = window.setTimeout(() => {
      setChangedLevels(new Set())
    }, 220)
  }, [])

  const scheduleFlush = useCallback(() => {
    if (frameRef.current) {
      return
    }

    frameRef.current = window.requestAnimationFrame(flushDeltas)
  }, [flushDeltas])

  const connect = useCallback(
    async (nextSymbol) => {
      const normalizedSymbol = nextSymbol.toUpperCase()

      if (wsRef.current) {
        wsRef.current.close()
      }

      setSymbol(normalizedSymbol)
      setStatus('connecting')
      setError('')
      setBids([])
      setAsks([])
      setLastDelta(null)
      setChangedLevels(new Set())
      deltaBufferRef.current = []
      bookRef.current = { bids: new Map(), asks: new Map() }

      try {
        const snapshotResponse = await fetch(`${API_BASE_URL}/snapshot/${normalizedSymbol}`)

        if (!snapshotResponse.ok) {
          throw new Error(`Snapshot request failed: ${snapshotResponse.status}`)
        }

        const snapshot = await snapshotResponse.json()

        if (snapshot && typeof snapshot === 'object' && Array.isArray(snapshot.bids)) {
          bookRef.current = {
            bids: rowsToMap(snapshot.bids),
            asks: rowsToMap(snapshot.asks),
          }

          setBids(mapToRows(bookRef.current.bids, 'bid'))
          setAsks(mapToRows(bookRef.current.asks, 'ask'))
        }

        const ws = new WebSocket(`${WS_BASE_URL}/ws/orderbook/${normalizedSymbol}`)
        wsRef.current = ws

        ws.onopen = () => {
          if (wsRef.current !== ws) {
            return
          }

          setStatus('connected')
        }

        ws.onmessage = (event) => {
          if (wsRef.current !== ws) {
            return
          }

          const message = JSON.parse(event.data)

          if (message.type === 'snapshot' && message.data) {
            bookRef.current = {
              bids: rowsToMap(message.data.bids),
              asks: rowsToMap(message.data.asks),
            }
            setBids(mapToRows(bookRef.current.bids, 'bid'))
            setAsks(mapToRows(bookRef.current.asks, 'ask'))
            return
          }

          if (message.type !== 'delta' || !message.data) {
            return
          }

          deltaBufferRef.current.push(message.data)
          updateCountRef.current += 1
          scheduleFlush()
        }

        ws.onerror = () => {
          if (wsRef.current !== ws) {
            return
          }

          setStatus('error')
          setError('WebSocket connection failed')
        }

        ws.onclose = () => {
          if (wsRef.current !== ws) {
            return
          }

          setStatus('disconnected')
        }
      } catch (connectError) {
        setStatus('error')
        setError(connectError.message)
      }
    },
    [scheduleFlush],
  )

  useEffect(() => {
    updatesTimerRef.current = window.setInterval(() => {
      setUpdatesPerSecond(updateCountRef.current)
      updateCountRef.current = 0
    }, 1000)

    return () => {
      window.clearInterval(updatesTimerRef.current)

      if (changeTimerRef.current) {
        window.clearTimeout(changeTimerRef.current)
      }

      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current)
      }

      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return {
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
  }
}
