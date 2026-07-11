# Order flow

Real-time crypto order book and trade-flow dashboard built around Binance market data, FastAPI WebSockets, Redis, React, Prometheus, Grafana, and k6.
 
This project is a live market-data pipeline. It ingests Binance depth and trade streams, keeps the current order book in Redis, fans updates out to browser clients, renders the top-of-book and cumulative depth in React, and exposes enough metrics to understand how the system behaves under load.

## What It Does

- Streams live Binance order book deltas and trades for `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, and `XRPUSDT`.
- Builds a sequence-safe local order book by loading the Binance REST snapshot and applying only aligned WebSocket deltas.
- Stores bid/ask levels in Redis sorted sets with companion quantity hashes for fast top-N reads.
- Publishes normalized deltas and trades through Redis Pub/Sub.
- Serves REST snapshots (of the symbol current state) and WebSocket streams from FastAPI.
- Coalesces order book deltas into 100ms batches so the frontend receives useful updates without being spammed by every raw exchange event.
- Detects slow WebSocket clients with per-client queues and sends a `resync_required` message instead of letting stale updates pile up forever.
- Renders an order book, cumulative depth chart, latest delta panel, trade feed, and client-side render/update metrics in React.
- Exposes Prometheus metrics and ships with Grafana provisioning for backend health and pipeline visibility.
- Includes a k6 WebSocket spike test for concurrent virtual users.

## Project Highlights

The core of the project is the end-to-end handling of live, high-frequency data:

- **Correct market-data sync:** `backend/app/ws/ws_consumer.py` starts with a Binance REST depth snapshot, buffers live events while the snapshot loads, validates update sequence IDs, and resyncs when a gap appears.
- **Fast top-of-book reads:** Redis sorted sets keep prices ordered, while hashes preserve quantities. Snapshots read the best bids/asks without scanning the full book.
- **Async fan-out:** FastAPI runs ingestion, Redis subscription, and coalesced broadcasting as background asyncio tasks instead of tying them to request lifetimes.
- **Backpressure behavior:** each client has a bounded async send queue. If the queue fills, the server clears stale messages and asks that client to reload a fresh snapshot.
- **Frontend frame control:** `useOrderBook.js` buffers incoming deltas and applies them on `requestAnimationFrame`, which keeps rendering responsive during bursts.
- **Observable by default:** the app tracks update counts, connected clients, queue depth, backpressure events, Redis read latency, snapshot cache hits/misses, and Binance reconnects.
- Load testing results
| Max VUs | Snapshot success | WS connect success | Backpressure resyncs | WS messages/sec | Snapshot p95 |
| --- | --- | --- | --- | --- | --- |
| 200 | 100% | 100% | 0 | ~518 | ~3.12ms |
| 500 | 97.74% | 95.81% | 0 | ~1207 | ~3.92ms |
## Images

### Frontend orderbook
![Orderbook](https://raw.githubusercontent.com/TheBighi/TheBighi/refs/heads/main/images/Screenshot%202026-07-09%20165150.png)

### Grafana (UV 200 3m10s test)
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

## Local Backend Development

Docker is the default path. If you want to run the backend directly with Python while coding, stop the Docker backend first because both use port `8000`.

```powershell
docker compose stop backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The local backend defaults to Redis at `redis://:qwerty@localhost:6379`. In Docker, Compose sets:

```text
REDIS_URL=redis://:${REDIS_PASS}@redis:6379
```

Avoid `--reload` during load tests. Reload mode is useful while coding, but it adds a reloader process and makes stress-test results noisier.

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
