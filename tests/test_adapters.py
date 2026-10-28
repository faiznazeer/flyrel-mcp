from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from brokerbridge.adapters.alpaca import AlpacaAdapter
from brokerbridge.adapters.http import BrokerReadError
from brokerbridge.adapters.kite import KiteAdapter


def test_alpaca_quotes_history_pagination_and_read_only():
    calls = []

    def handler(r):
        assert r.method == "GET"
        calls.append(r)
        if r.url.path.endswith("quotes/latest"):
            return httpx.Response(
                200,
                json={"quotes": {"AAPL": {"bp": 99.9, "ap": 100.1, "t": "2026-01-01T12:00:00Z"}}},
            )
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json={"id": "account-1", "cash": "1000"})
        return httpx.Response(
            200,
            json={
                "bars": [
                    {"t": "2026-01-01T12:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 20}
                ],
                "next_page_token": None if "page_token" in r.url.params else "page-two",
            },
        )

    a = AlpacaAdapter("test-key", "test-secret", transport=httpx.MockTransport(handler))
    try:
        assert a.accounts()[0].environment == "paper"
        assert a.quotes(["US:AAPL"])[0].bid == Decimal("99.9")
        bars = a.history(
            "US:AAPL", "1Day", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)
        )
        assert len(bars) == 2
        assert calls[-1].url.params["page_token"] == "page-two"
        assert "paper_orders" not in a.capabilities
    finally:
        a.close()


def test_kite_normalization_and_indian_history_timezone():
    calls = []

    def handler(r):
        assert r.method == "GET"
        assert r.headers["X-Kite-Version"] == "3"
        calls.append(r)
        if r.url.path == "/instruments/NSE":
            return httpx.Response(200, text="instrument_token,tradingsymbol\n123,RELIANCE\n")
        if "/historical/" in r.url.path:
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"candles": [["2026-01-01T09:15:00+0530", 1000, 1010, 990, 1005, 50]]},
                },
            )
        return httpx.Response(
            200, json={"status": "success", "data": {"NSE:RELIANCE": {"last_price": 1000}}}
        )

    a = KiteAdapter("test-key", "test-token", transport=httpx.MockTransport(handler))
    try:
        q = a.quotes(["NSE:RELIANCE"])[0]
        assert q.currency == "INR" and q.last == Decimal("1000") and q.timestamp is None
        bars = a.history(
            "NSE:RELIANCE",
            "1Day",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        )
        assert len(bars) == 1
        assert calls[-1].url.params["from"] == "2026-01-01 05:30:00"
        holdings = a.normalize(
            [
                {
                    "exchange": "NSE",
                    "tradingsymbol": "RELIANCE",
                    "quantity": 2,
                    "t1_quantity": 1,
                    "average_price": 900,
                    "last_price": 1000,
                    "product": "CNC",
                }
            ],
            "account-1",
        )
        assert holdings[0].quantity == 3 and holdings[0].market_value == 3000
        with pytest.raises(ValueError, match="unsupported"):
            a.normalize([{"exchange": "NFO"}], "account-1")
    finally:
        a.close()


def test_broker_error_body_never_exposed():
    a = AlpacaAdapter(
        "test",
        "secret",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"message": "sensitive-response-body"})
        ),
    )
    try:
        with pytest.raises(BrokerReadError) as caught:
            a.accounts()
        assert "401" in str(caught.value)
        assert "sensitive-response-body" not in str(caught.value)
    finally:
        a.close()
