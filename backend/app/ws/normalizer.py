from typing import Literal

def normalize_delta(raw: dict) -> list[dict]:
    """
    Map a raw Binance depthUpdate message to a flat list of
    { side, price, qty, timestamp } dicts.
    Entries with qty == 0 are deletions — included but flagged via qty=0.
    """
    timestamp = raw["E"]  # event time in ms

    rows = []

    for price_str, qty_str in raw.get("b", []):
        rows.append({
            "side":      "bid",
            "price":     float(price_str),
            "qty":       float(qty_str),
            "timestamp": timestamp,
        })

    for price_str, qty_str in raw.get("a", []):
        rows.append({
            "side":      "ask",
            "price":     float(price_str),
            "qty":       float(qty_str),
            "timestamp": timestamp,
        })

    return rows