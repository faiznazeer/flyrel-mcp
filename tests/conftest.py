import json
import os
from pathlib import Path

import httpx
import pytest

from flyrel.adapters.alpaca import AlpacaAdapter
from flyrel.adapters.kite import KiteAdapter


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith("FLYREL_"):
            monkeypatch.delenv(name)


@pytest.fixture
def broker_contract():
    adapters = []

    def make(broker_id, *, paper=True):
        payload = json.loads(
            (Path(__file__).parent / "fixtures" / "brokers" / f"{broker_id}.json").read_text()
        )
        calls = []

        def handler(request):
            assert request.method == "GET"
            calls.append(request)
            path = request.url.path
            if broker_id == "kite":
                assert request.url.host == "api.kite.trade"
                assert request.headers["Authorization"] == "token synthetic-key:synthetic-token"
                routes = {
                    "/user/profile": "profile",
                    "/portfolio/positions": "positions",
                    "/portfolio/holdings": "holdings",
                    "/orders": "orders",
                    "/quote": "quotes",
                    "/instruments/historical/123/day": "history",
                }
                if path == "/instruments/NSE":
                    return httpx.Response(200, text=payload["instruments"])
                return httpx.Response(200, json=payload[routes[path]])
            account_host = "paper-api.alpaca.markets" if paper else "api.alpaca.markets"
            assert request.headers["APCA-API-KEY-ID"] == "synthetic-key"
            assert request.headers["APCA-API-SECRET-KEY"] == "synthetic-secret"
            if path.startswith("/v2/stocks/"):
                assert request.url.host == "data.alpaca.markets"
                if path.endswith("/bars"):
                    assert request.url.params["adjustment"] == "raw"
                    assert request.url.params["feed"] == "iex"
                    return httpx.Response(
                        200, json=payload["history"][request.url.params.get("page_token", "")]
                    )
                return httpx.Response(200, json=payload["quotes"])
            assert request.url.host == account_host
            routes = {
                "/v2/account": "account",
                "/v2/positions": "positions",
                "/v2/orders": "orders",
            }
            if path == "/v2/orders":
                assert request.url.params["status"] == "open"
            return httpx.Response(200, json=payload[routes[path]])

        transport = httpx.MockTransport(handler)
        adapter = (
            KiteAdapter("synthetic-key", "synthetic-token", transport=transport)
            if broker_id == "kite"
            else AlpacaAdapter(
                "synthetic-key", "synthetic-secret", paper=paper, transport=transport
            )
        )
        adapters.append(adapter)
        return adapter, payload, calls

    yield make
    for adapter in adapters:
        adapter.close()
