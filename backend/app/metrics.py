from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


orderbook_updates_total = Counter(
    "orderbook_updates_total",
    "Total order book deltas received from Redis pub/sub.",
    ["symbol", "side"],
)

connected_clients = Gauge(
    "connected_clients",
    "Current connected WebSocket clients.",
    ["symbol"],
)

backpressure_events_total = Counter(
    "backpressure_events_total",
    "Total backpressure events detected for WebSocket clients.",
    ["symbol"],
)

redis_zrangebyscore_duration_ms = Histogram(
    "redis_zrangebyscore_duration_ms",
    "Redis sorted-set range read duration in milliseconds.",
    ["symbol", "side"],
)


def record_orderbook_update(symbol: str, side: str):
    orderbook_updates_total.labels(symbol=symbol.upper(), side=side).inc()


def set_connected_clients(symbol: str, count: int):
    connected_clients.labels(symbol=symbol.upper()).set(count)


def record_backpressure_event(symbol: str):
    backpressure_events_total.labels(symbol=symbol.upper()).inc()


def observe_redis_zrange(symbol: str, side: str, duration_ms: float):
    redis_zrangebyscore_duration_ms.labels(symbol=symbol.upper(), side=side).observe(duration_ms)


def render_prometheus_metrics():
    return generate_latest(), CONTENT_TYPE_LATEST
