# Orderflow

Real-time crypto order book and trade-flow dashboard built around Binance 
market data, FastAPI WebSockets, Redis, React, Prometheus, Grafana, and k6.

This project is a live market-data pipeline. It ingests Binance depth and 
trade streams, keeps the current order book in Redis, fans updates out to 
browser clients, renders the top-of-book and cumulative depth in React, and 
exposes enough metrics to understand how the system behaves under load.

> 200 concurrent clients · 518 WebSocket messages/sec ·  0 backpressure 
> resyncs · 3.12ms snapshot p95 delay · under k6 spike load test

## What It Does

- Streams live Binance order book and trade data for `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, and `XRPUSDT`.
- Builds a sequence-safe local order book from REST snapshots and WebSocket deltas.
- Stores market data in Redis and publishes updates via Pub/Sub.
- Serves REST snapshots and real-time WebSocket streams with FastAPI.
- Batches updates every 100ms and handles slow clients with automatic resyncs.
- Displays an order book, depth chart, trade feed, and performance metrics in React.
- Monitors the system with Prometheus, Grafana, and k6 load testing.

## Project Highlights

The core of the project is the end-to-end handling of live, high-frequency data:

- **Market-data sync:** Starts from a Binance REST snapshot, applies buffered WebSocket events, validates sequence IDs, and resyncs on gaps.
- **Fast reads:** Uses Redis sorted sets and hashes for efficient top-of-book snapshots.
- **Async architecture:** Handles ingestion, Redis subscriptions, and broadcasting with background asyncio tasks.
- **Backpressure handling:** Uses bounded client queues and triggers resyncs when clients fall behind.
- **Frontend performance:** Batches order book updates with `requestAnimationFrame` for smooth rendering.
- **Monitoring:** Tracks Redis latency, backpressure events, cache performance, clients, and Binance reconnects in Grafana.
- **Load testing results:**

| Max VUs | Snapshot success | WS connect success | Backpressure resyncs | WS messages/sec | Snapshot p95 delay |
| --- | --- | --- | --- | --- | --- |
| 200 | 100% | 100% | 0 | ~518 | ~3.12ms |
| 500 | 97.74% | 95.81% | 0 | ~1207 | ~3.92ms |
## Images

### Frontend orderbook
![Orderbook](https://raw.githubusercontent.com/TheBighi/TheBighi/refs/heads/main/images/Screenshot%202026-07-09%20165150.png)

### Grafana, 200 concurrent WebSocket clients
Showing live update throughput, connected clients, Redis read latency under k6 spike load etc.
![Grafana](https://raw.githubusercontent.com/TheBighi/TheBighi/refs/heads/main/images/Screenshot%202026-07-09%20165712.png)

## Architecture

![Architecture](https://raw.githubusercontent.com/TheBighi/TheBighi/refs/heads/main/images/Architecture.png)

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend API | FastAPI, Uvicorn |
| Streaming | Python `websockets`, FastAPI WebSockets |
| Data source | Binance REST and WebSocket APIs |
| State/cache | Redis sorted sets, hashes, lists, Pub/Sub |
| Frontend | React 19, Vite |
| Visualization | Custom React components and Canvas depth chart |
| Metrics | `prometheus_client`, Prometheus, Grafana |
| Load testing | k6 |
| Local infra | Docker Compose |

## Project Structure

```text
backend/
  Dockerfile                    FastAPI backend container image
  app/
    main.py                    FastAPI app, lifespan tasks, REST and WS routes
    clients/redis_client.py     Redis order book, trade, snapshot helpers
    metrics.py                  Prometheus counters, gauges, histograms
    ws/
      ws_consumer.py            Binance snapshot/delta synchronization
      ws_connector.py           Binance WebSocket connectors with reconnects
      normalizer.py             Binance payload normalization
      redis_subscriber.py       Redis Pub/Sub to server fan-out
      coalesce.py               100ms order book delta batching
      backpressure.py           Per-client bounded outbound queues
      connection_manager.py     Symbol-scoped WebSocket registry

frontend/
  src/
    App.jsx                     Dashboard shell and symbol selection
    useOrderBook.js             Snapshot load, WS handling, RAF delta flushing
    OrderBook.jsx               Bid/ask ladder
    DepthChart.jsx              Cumulative depth visualization
    TradeFeed.jsx               Recent live trades
    MetricsPanel.jsx            Client-side status and render metrics

grafana/                        Provisioned datasource and dashboard
load-test/                      k6 WebSocket spike test and recorded results
docker-compose.yml              Backend, Redis, Prometheus, Grafana, k6 profile
prometheus.yml                  Prometheus scrape config
```

## API Surface

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Backend health check |
| `GET /snapshot/{symbol}` | Top 25 bids and asks from Redis |
| `WS /ws/orderbook/{symbol}` | Batched order book deltas and resync signals |
| `GET /trades/{symbol}` | Recent 50 trades from Redis |
| `WS /ws/trades/{symbol}` | Live trade stream |
| `GET /metrics` | Prometheus metrics |

Supported symbols are currently `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, and `XRPUSDT`.

## Quick Start

The easiest way to run the backend infrastructure is Docker Compose.

```powershell
docker compose up -d --build
```

This starts:

- FastAPI backend on `http://localhost:8000`
- Redis on `localhost:6379`
- Prometheus on `http://localhost:9090`
- Grafana on `http://localhost:3333`

Grafana is provisioned automatically with the Orderflow backend dashboard.

### Start The Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite prints the frontend URL, usually:

```text
http://localhost:5173
```

Open it, choose a symbol, and click `Connect`.

### Useful URLs

| Service | URL |
| --- | --- |
| Frontend | `http://localhost:5173` |
| Backend | `http://localhost:8000` |
| Backend metrics | `http://localhost:8000/metrics` |
| Prometheus | `http://localhost:9090` |
| Grafana | `http://localhost:3333` |

### Stop Everything

```powershell
docker compose down
```

This stops the containers but keeps Redis, Prometheus, and Grafana volumes.

### Rebuild After Backend Changes

```powershell
docker compose up -d --build backend
```

Use this after changing backend Python files, `requirements.txt`, or `backend/Dockerfile`.

## Monitoring

Prometheus scrapes the backend `/metrics` endpoint. Grafana is provisioned from the files under `grafana/`.

Useful PromQL queries:

```promql
sum by (symbol) (rate(orderbook_updates_total[1m]))
connected_clients
sum by (symbol) (rate(backpressure_events_total[1m]))
max by (symbol) (backpressure_queue_depth)
histogram_quantile(0.95, sum by (le, symbol) (rate(redis_zrangebyscore_duration_ms_bucket[5m])))
sum by (symbol) (rate(snapshot_cache_hits_total[1m]))
sum by (symbol) (rate(snapshot_cache_misses_total[1m]))
```

The snapshot cache panels show how often `/snapshot/{symbol}` reused a short in-memory response instead of reading Redis again. Hits are cache saves. Misses are Redis reads.

## Backend Tests

The backend includes a small pytest suite that checks core behavior without requiring Redis, Docker, or Binance network access.

Run it from the repository root:

```powershell
python -m pytest
```

Current tests cover:

| Test file | Coverage |
| --- | --- |
| `backend/tests/test_normalizer.py` | Binance depth and trade payload normalization, including delete levels and buy/sell trade direction. |
| `backend/tests/test_coalesce.py` | Order book delta coalescing, verifying that repeated updates for the same symbol/side/price keep the latest value. |
| `backend/tests/test_redis_client.py` | Redis order book writes, delete cleanup, pub/sub payloads, and best bid/ask snapshot reads using a fake Redis client. |

## Load Testing

Run the k6 spike test through the Compose profile:

```powershell
docker compose --profile loadtest run --rm k6
```

The test opens WebSocket clients across the supported symbols, verifies snapshots, counts WebSocket messages, and tracks resync events.

You can tune the size of the run:

```powershell
docker compose --profile loadtest run --rm -e MAX_VUS=500 k6
```

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_VUS` | `200` | Peak virtual users |
| `TEST_DURATION_SECONDS` | `60` | How long each WebSocket session stays open |
| `SNAPSHOT_RETRY_SLEEP_SECONDS` | `5` | Sleep after a failed snapshot before retrying |
| `HTTP_BASE_URL` | `http://backend:8000` in Compose | Snapshot target |
| `WS_BASE_URL` | `ws://backend:8000` in Compose | WebSocket target |

Recorded results in `load-test/results.md`:

| Max VUs | Snapshot success | WS connect success | Backpressure resyncs | WS messages/sec | Snapshot p95 |
| --- | --- | --- | --- | --- | --- |
| 200 | 100% | 100% | 0 | ~518 | ~3.12ms |
| 500 | 97.74% | 95.81% | 0 | ~1207 | ~3.92ms |

## Notes
 
- Redis is configured with the local password `${REDIS_PASS}` in `docker-compose.yml`.
- The Docker backend connects to Redis through the Compose service name `redis`.
- The frontend still runs outside Docker and talks to `localhost:8000`.
- The backend starts Binance consumers lazily per symbol when a snapshot or WebSocket request arrives.
- Snapshot responses use a short in-memory cache to avoid hammering Redis during connection spikes.

## What's Next

- **Kafka event log:** replace Redis Pub/Sub with Kafka to get durable 
  replay — historical order book state could be reconstructed from any 
  point in time, and multiple independent consumers could subscribe without 
  contention.
