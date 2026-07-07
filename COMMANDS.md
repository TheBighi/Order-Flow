# Start/stop Docker

sudo docker compose up -d
<br>
sudo docker compose down -v

# Start backend and frontend

root/backend: python -m app.main
<br>
root/frontend: npm run dev

# URLs

Backend: http://127.0.0.1:8000<br>
Frontend: http://127.0.0.1:5167<br>
Prometheus: http://127.0.0.1:9090<br>
Grafana: http://127.0.0.1:3000

# Grafana queries

## Order Book Updates/sec
sum by (symbol) (rate(orderbook_updates_total[1m]))
## Connected Clients
connected_clients
## Backpressure Events/sec
sum by (symbol) (rate(backpressure_events_total[1m]))
## Max Queue Depth
max by (symbol) (backpressure_queue_depth)
## Redis p95 Latency
histogram_quantile(0.95, sum by (le, symbol) (rate(redis_zrangebyscore_duration_ms_bucket[5m])))