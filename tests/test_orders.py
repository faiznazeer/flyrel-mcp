from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from pydantic import ValidationError

from brokerbridge.models import OrderRequest, Policy
from brokerbridge.store import Store


def request(**changes):
    return OrderRequest.model_validate(
        {
            "symbol": "US:AAPL",
            "quantity": 2,
            "limit_price": "100",
            "idempotency_key": "example-key-01",
            **changes,
        }
    )


def test_persistent_idempotency_and_cancel(tmp_path):
    store = Store(tmp_path)
    token = store.propose(request(), Policy())["confirmation_token"]
    first = store.confirm(token, Policy())
    reopened = Store(tmp_path)
    assert reopened.confirm(token, Policy()) == first
    assert len(reopened.orders()) == 1
    assert reopened.cancel(first.order_id).status == "cancelled"
    assert reopened.confirm(token, Policy()).status == "cancelled"


def test_concurrent_confirmation_is_once(tmp_path):
    store = Store(tmp_path)
    token = store.propose(request(), Policy())["confirmation_token"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        orders = list(pool.map(lambda _: store.confirm(token, Policy()), range(8)))
    assert len({o.order_id for o in orders}) == 1
    assert len(store.orders()) == 1


def test_idempotency_conflict(tmp_path):
    store = Store(tmp_path)
    a = store.propose(request(), Policy())
    b = store.propose(request(quantity=3), Policy())
    store.confirm(a["confirmation_token"], Policy())
    with pytest.raises(ValueError, match="conflicts"):
        store.confirm(b["confirmation_token"], Policy())


def test_expiry_and_token_hashing(tmp_path, monkeypatch):
    store = Store(tmp_path)
    monkeypatch.setattr("brokerbridge.store.time.time", lambda: 100)
    token = store.propose(request(), Policy())["confirmation_token"]
    assert token.encode() not in store.path.read_bytes()
    monkeypatch.setattr("brokerbridge.store.time.time", lambda: 221)
    with pytest.raises(ValueError, match="expired"):
        store.confirm(token, Policy())


@pytest.mark.parametrize("change", [{"symbol": "US:MSFT"}, {"quantity": 11}])
def test_policy_rejects_symbol_and_notional(tmp_path, change):
    with pytest.raises(ValueError):
        Store(tmp_path).propose(request(**change), Policy())


def test_kill_switch_survives_restart_and_rechecks_confirmation(tmp_path):
    store = Store(tmp_path)
    token = store.propose(request(), Policy())["confirmation_token"]
    store.halt()
    with pytest.raises(ValueError, match="disabled"):
        Store(tmp_path).confirm(token, Policy())
    store.resume()
    assert store.confirm(token, Policy()).status == "open"


def test_policy_rechecked_and_outstanding_orders_reserved(tmp_path):
    store = Store(tmp_path)
    policy = Policy(max_open_value={"USD": Decimal("300"), "INR": Decimal("500000")})
    a = store.propose(request(), policy)
    b = store.propose(request(idempotency_key="example-key-02"), policy)
    store.confirm(a["confirmation_token"], policy)
    with pytest.raises(ValueError, match="aggregate"):
        store.confirm(b["confirmation_token"], policy)
    store.cancel(store.orders()[0].order_id)
    with pytest.raises(ValueError, match="disabled"):
        store.confirm(b["confirmation_token"], Policy(read_only=True))
    assert store.confirm(b["confirmation_token"], policy).status == "open"


def test_currency_limits_are_independent(tmp_path):
    store = Store(tmp_path)
    store.confirm(store.propose(request(), Policy())["confirmation_token"], Policy())
    indian = request(symbol="NSE:RELIANCE", limit_price="1000", idempotency_key="indian-key-01")
    assert (
        store.confirm(store.propose(indian, Policy())["confirmation_token"], Policy()).symbol
        == "NSE:RELIANCE"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"broker_id": "kite"},
        {"quantity": 0},
        {"quantity": 1.5},
        {"limit_price": "NaN"},
        {"limit_price": "Infinity"},
        {"side": "sell"},
        {"symbol": "AAPL"},
        {"unknown": True},
    ],
)
def test_unsupported_or_invalid_requests(change):
    with pytest.raises(ValidationError):
        request(**change)
