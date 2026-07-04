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


def normalize_trade(raw: dict) -> dict:
    """
    Map a raw Binance trade message to
    { trade_id, price, qty, side, timestamp }.

    Binance field `m` means buyer is maker. If buyer is maker, the taker
    sold into resting bids, so display it as a sell. Otherwise display buy.
    """
    return {
        "trade_id": raw["t"],
        "price": float(raw["p"]),
        "qty": float(raw["q"]),
        "side": "sell" if raw["m"] else "buy",
        "timestamp": raw["T"],
    }
