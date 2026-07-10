from app.ws.normalizer import normalize_delta, normalize_trade


def test_normalize_delta_flattens_bid_and_ask_updates():
    raw = {
        "E": 1710000000123,
        "b": [["70000.10", "0.2500"], ["69999.00", "0"]],
        "a": [["70001.20", "1.5000"]],
    }

    rows = normalize_delta(raw)

    assert rows == [
        {
            "side": "bid",
            "price": 70000.10,
            "qty": 0.25,
            "timestamp": 1710000000123,
        },
        {
            "side": "bid",
            "price": 69999.00,
            "qty": 0.0,
            "timestamp": 1710000000123,
        },
        {
            "side": "ask",
            "price": 70001.20,
            "qty": 1.5,
            "timestamp": 1710000000123,
        },
    ]


def test_normalize_delta_tolerates_missing_sides():
    raw = {"E": 1710000000456, "b": [["100.00", "2.5"]]}

    assert normalize_delta(raw) == [
        {
            "side": "bid",
            "price": 100.0,
            "qty": 2.5,
            "timestamp": 1710000000456,
        }
    ]


def test_normalize_trade_marks_buyer_maker_as_sell():
    raw = {"t": 123, "p": "70000.50", "q": "0.0100", "m": True, "T": 1710000000789}

    assert normalize_trade(raw) == {
        "trade_id": 123,
        "price": 70000.5,
        "qty": 0.01,
        "side": "sell",
        "timestamp": 1710000000789,
    }


def test_normalize_trade_marks_non_buyer_maker_as_buy():
    raw = {"t": 124, "p": "70001.00", "q": "0.0200", "m": False, "T": 1710000000790}

    assert normalize_trade(raw)["side"] == "buy"
