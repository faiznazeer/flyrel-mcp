from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from flyrel.adapters.alpaca import AlpacaAdapter
from flyrel.adapters.http import BrokerReadError
from flyrel.adapters.kite import KiteAdapter

START = datetime(2026, 1, 5, tzinfo=UTC)
END = datetime(2026, 1, 7, tzinfo=UTC)


@pytest.mark.parametrize("paper", [True, False])
def test_alpaca_portfolio_contract_keeps_fractional_short_and_environment(broker_contract, paper):
    adapter, _, _ = broker_contract("alpaca", paper=paper)
    account = adapter.accounts()[0]
    positions = adapter.positions()
    assert account.cash == Decimal("1234.56")
    assert positions[0].quantity == Decimal("1.25")
    assert positions[0].average_price == Decimal("80.125")
    assert positions[1].quantity == -2
    assert positions[1].market_value == Decimal("-400.50")
    assert all(p.account_id == account.account_id and p.currency == "USD" for p in positions)
    assert all(p.environment == ("paper" if paper else "live") for p in positions)
    assert adapter.holdings() == positions
    assert positions[0].performance.unrealized_pnl == Decimal("25.34375")
    assert positions[0].performance.day_price_change_percent == Decimal("2.032520325203252")
    assert positions[1].performance.day_price_change_percent == Decimal("1.008827")
    # A rising asset price is a loss for this short position. Preserve broker P&L signs.
    assert positions[1].performance.day_unrealized_pnl == Decimal("-4.0")
    assert positions[1].performance.unrealized_pnl == Decimal("20.0")
    assert positions[1].performance.price_timestamp is None
    order = adapter.orders()[0]
    assert order.side == "sell" and order.status == "partially_filled"
    assert order.quantity == Decimal("0.25") and order.limit_price is None
    assert order.environment == account.environment


def test_kite_portfolio_contract_keeps_separate_views_and_unsettled_quantity(broker_contract):
    adapter, _, _ = broker_contract("kite")
    account = adapter.accounts()[0]
    position = adapter.positions()[0]
    holding = adapter.holdings()[0]
    assert account.cash is None
    assert position.quantity == -2 and position.product == "MIS"
    assert position.market_value == Decimal("-2000.30")
    assert holding.quantity == 3 and holding.product == "CNC"
    assert holding.market_value == Decimal("3000.45")
    assert position.account_id == holding.account_id == account.account_id
    assert holding.broker_id == "kite" and holding.environment == "live"
    assert holding.currency == "INR"
    assert holding.performance.source == "kite_holdings"
    assert holding.performance.unrealized_pnl == Decimal("299.7")
    assert holding.performance.day_price_change == Decimal("-9.85")
    assert holding.performance.day_price_change_percent == Decimal("-0.9752475247524752")
    assert holding.performance.previous_close == Decimal("1010")
    assert holding.performance.day_unrealized_pnl is None
    assert holding.performance.price_timestamp is None
    assert position.performance is None
    order = adapter.orders()[0]
    assert order.status == "COMPLETE" and order.side == "sell"
    assert order.environment == "live"


@pytest.mark.parametrize("broker_id", ["kite", "alpaca"])
def test_split_like_price_jump_is_preserved_without_local_adjustment(broker_contract, broker_id):
    adapter, _, calls = broker_contract(broker_id)
    symbol = "NSE:RELIANCE" if broker_id == "kite" else "US:AAPL"
    bars = adapter.history(symbol, "1Day", START, END)
    assert len(bars) == 2
    assert bars[0].close == bars[1].close * 2
    assert bars[0].volume * 2 == bars[1].volume
    assert all(b.timestamp.tzinfo is not None for b in bars)
    if broker_id == "alpaca":
        assert calls[-1].url.params["page_token"] == "synthetic-next"
    else:
        assert calls[-1].url.params["from"] == "2026-01-05 05:30:00"


@pytest.mark.parametrize("broker_id,status", [("kite", 403), ("alpaca", 401), ("alpaca", 403)])
def test_auth_and_access_errors_are_sanitized_and_not_retried(broker_id, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"message": "private-account-detail"})

    cls = KiteAdapter if broker_id == "kite" else AlpacaAdapter
    adapter = cls("synthetic-key", "synthetic-secret", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(BrokerReadError) as caught:
            adapter.accounts()
        assert caught.value.code == "auth_or_access"
        assert caught.value.status_code == status
        assert "private-account-detail" not in str(caught.value)
        assert len(calls) == 1
    finally:
        adapter.close()


@pytest.mark.parametrize("cls", [KiteAdapter, AlpacaAdapter])
def test_rate_limit_stops_without_retry_or_response_leak(cls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "60"}, text="private-error")

    adapter = cls("synthetic-key", "synthetic-secret", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(BrokerReadError) as caught:
            adapter.accounts()
        assert caught.value.code == "rate_limited" and len(calls) == 1
        assert "private-error" not in str(caught.value)
    finally:
        adapter.close()


@pytest.mark.parametrize("tokens,expected_calls", [(["A", "A"], 2), (["A", "B", "A"], 3)])
def test_alpaca_detects_pagination_cycles_even_on_empty_pages(tokens, expected_calls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"bars": [], "next_page_token": tokens[len(calls) - 1]})

    adapter = AlpacaAdapter("key", "secret", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError, match="repeated a token"):
            adapter.history("US:AAPL", "1Day", START, END)
        assert len(calls) == expected_calls
    finally:
        adapter.close()


def test_alpaca_bounds_endless_unique_empty_pages():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"bars": None, "next_page_token": str(len(calls))})

    adapter = AlpacaAdapter("key", "secret", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError, match="exceeded 100 pages"):
            adapter.history("US:AAPL", "1Day", START, END)
        assert len(calls) == 100
    finally:
        adapter.close()


@pytest.mark.parametrize("operation", ["positions", "orders"])
def test_alpaca_rejects_non_equities_instead_of_returning_partial_snapshot(
    broker_contract, operation
):
    adapter, payload, _ = broker_contract("alpaca")
    payload[operation].append({"asset_class": "crypto"})
    with pytest.raises(ValueError, match="unsupported"):
        getattr(adapter, operation)()


def test_alpaca_full_order_page_fails_as_potentially_truncated(broker_contract):
    adapter, payload, _ = broker_contract("alpaca")
    payload["orders"] *= 500
    with pytest.raises(ValueError, match="truncated"):
        adapter.orders()
