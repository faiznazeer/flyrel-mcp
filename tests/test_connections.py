import asyncio
import json

import pytest
from pydantic import ValidationError

from flyrel import service as service_module
from flyrel.adapters import external_adapter
from flyrel.config import BrokerConnection, Settings
from flyrel.demo import demo_registry
from flyrel.models import OrderRequest
from flyrel.server import create_server
from flyrel.service import ConnectionSelectionError, Service


def named_connection(connection_id, *, broker_id="alpaca", environment="paper"):
    return {
        "connection_id": connection_id,
        "broker_id": broker_id,
        "environment": environment,
        "api_key": "synthetic-only-key",
        **(
            {"access_token": "synthetic-only-token"}
            if broker_id == "kite"
            else {"secret_key": "synthetic-only-secret"}
        ),
    }


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_named_connections_load_privately_without_replacing_default_credentials(
    tmp_path, monkeypatch, source
):
    connections = [named_connection("us-main"), named_connection("us-live", environment="live")]
    env_file = tmp_path / ".env"
    if source == "environment":
        monkeypatch.setenv("FLYREL_BROKER_CONNECTIONS", json.dumps(connections))
    else:
        env_file.write_text(
            "FLYREL_BROKER_CONNECTIONS='" + json.dumps(connections, indent=2) + "'\n"
        )
    settings = Settings(
        _env_file=env_file,
        alpaca_api_key="synthetic-default-key",
        alpaca_secret_key="synthetic-default-secret",
    )
    assert settings.connection_ids("alpaca") == ["alpaca", "us-main", "us-live"]
    assert settings.connection_profile("us-live") == ("alpaca", "live", "iex")
    assert settings.broker_connections[0].secret_key.get_secret_value() == "synthetic-only-secret"
    assert "synthetic-only-secret" not in repr(settings)
    assert "synthetic-only-key" not in repr(settings)


@pytest.mark.parametrize(
    "change",
    [
        {"connection_id": "paper"},
        {"connection_id": "kite"},
        {"connection_id": "alpaca"},
        {"connection_id": "bad/name"},
        {"api_key": ""},
        {"secret_key": ""},
        {"access_token": "wrong-broker-token"},
        {"environment": "synthetic"},
    ],
)
def test_invalid_connection_cannot_start_or_expose_credentials(change):
    with pytest.raises(ValidationError) as caught:
        BrokerConnection.model_validate({**named_connection("us-main"), **change})
    assert "synthetic-only-secret" not in str(caught.value)
    assert "synthetic-only-key" not in str(caught.value)


def test_duplicate_aliases_and_kite_paper_environment_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        Settings(
            _env_file=None, broker_connections=[named_connection("same"), named_connection("same")]
        )
    with pytest.raises(ValidationError, match="live account reads"):
        BrokerConnection.model_validate(named_connection("in-main", broker_id="kite"))


@pytest.mark.parametrize(
    "broker_id,environment", [("kite", "live"), ("alpaca", "paper"), ("alpaca", "live")]
)
def test_named_factory_preserves_broker_environment_and_has_no_execution(broker_id, environment):
    settings = Settings(
        _env_file=None,
        broker_connections=[
            named_connection("selected", broker_id=broker_id, environment=environment)
        ],
    )
    adapter = external_adapter(settings, "selected")
    try:
        assert adapter.id == broker_id and adapter.environment == environment
        assert "paper_orders" not in adapter.capabilities
        assert not hasattr(adapter, "place_order")
    finally:
        adapter.close()


@pytest.fixture
def two_accounts(tmp_path, monkeypatch, broker_contract):
    first, first_data, first_calls = broker_contract("alpaca")
    second, second_data, second_calls = broker_contract("alpaca", paper=False)
    first_data["account"]["id"] = "account-one"
    second_data["account"]["id"] = "account-two"
    second_data["positions"][0]["qty"] = "3.5"
    adapters = {"us-main": first, "us-second": second}
    monkeypatch.setattr(service_module, "external_adapter", lambda _, key: adapters.get(key))
    settings = Settings(
        _env_file=None,
        state_dir=tmp_path,
        broker_connections=[
            named_connection("us-main"),
            named_connection("us-second", environment="live"),
        ],
    )
    return settings, adapters, [first_data, second_data], [first_calls, second_calls]


def test_ambiguous_or_wrong_broker_selection_makes_no_requests(two_accounts):
    settings, _, _, calls = two_accounts
    service = Service(settings)
    try:
        with pytest.raises(ConnectionSelectionError, match="Select connection_id"):
            service.read("alpaca", "positions")
        with pytest.raises(ConnectionSelectionError, match="requested broker"):
            service.read("kite", "positions", "us-main")
        assert calls == [[], []]
        rows = service.read("alpaca", "positions", "us-second")
        assert rows[0]["quantity"] == "3.5"
        assert rows[0]["account_ref"] == {
            "broker_id": "alpaca",
            "account_id": "account-two",
            "environment": "live",
        }
        assert rows[0]["connection_id"] == "us-second" and rows[0]["currency"] == "USD"
        assert rows[0]["instrument_id"] is None
        assert not calls[0] and calls[1]
        orders = service.read("alpaca", "orders", "us-main")
        assert orders[0]["account_id"] == "account-one"
        assert orders[0]["environment"] == "paper"
    finally:
        service.close()


def test_holdings_summary_requires_explicit_connection_and_routes_correctly(two_accounts):
    settings, _, _, calls = two_accounts
    service = Service(settings)
    try:
        with pytest.raises(ConnectionSelectionError, match="Select connection_id"):
            service.holdings_summary("alpaca")
        with pytest.raises(ConnectionSelectionError, match="requested broker"):
            service.holdings_summary("kite", "us-main")
        assert calls == [[], []]
        report = service.holdings_summary("alpaca", "us-second")
        assert report["accounts"][0]["account_ref"]["account_id"] == "account-two"
        assert report["connection_id"] == "us-second" and report["environment"] == "live"
        assert not calls[0] and calls[1]
    finally:
        service.close()


def test_same_broker_same_account_string_in_distinct_environments_is_not_duplicate(two_accounts):
    settings, _, payloads, _ = two_accounts
    payloads[1]["account"]["id"] = payloads[0]["account"]["id"]
    service = Service(settings)
    try:
        report = service.portfolio(["us-main", "us-second"])
        assert report["duplicate_accounts"] == []
        assert [s["environment"] for s in report["brokers"]] == ["paper", "live"]
        assert all(
            s["accounts"][0]["account_ref"]["account_id"] == "account-one"
            for s in report["brokers"]
        )
        assert report["complete_consolidated_nav"] is False
    finally:
        service.close()


def test_synthetic_instrument_metadata_does_not_relabel_broker_paper_values(two_accounts):
    settings, _, _, _ = two_accounts
    service = Service(settings)
    service.registry = demo_registry()
    try:
        row = service.read("alpaca", "positions", "us-main")[0]
        assert row["environment"] == "paper" and row["synthetic"] is False
        assert row["instrument_id"] == "sample-us-aapl"
        assert row["instrument_identity_source"] == "synthetic-fixture"
        assert row["instrument_metadata_synthetic"] is True
    finally:
        service.close()


def test_same_account_on_two_connections_is_flagged_without_cross_connection_total(
    tmp_path, monkeypatch, broker_contract
):
    adapters = {name: broker_contract("alpaca")[0] for name in ("first", "second")}
    monkeypatch.setattr(service_module, "external_adapter", lambda _, key: adapters.get(key))
    settings = Settings(
        _env_file=None,
        state_dir=tmp_path,
        broker_connections=[named_connection("first"), named_connection("second")],
    )
    service = Service(settings)
    try:
        report = service.portfolio(["first", "second"])
        assert report["duplicate_accounts"] == [
            {
                "account_ref": {
                    "broker_id": "alpaca",
                    "account_id": "synthetic-alpaca-account",
                    "environment": "paper",
                },
                "connection_ids": ["first", "second"],
            }
        ]
        assert "positions_value_by_currency" not in report
    finally:
        service.close()


def test_mcp_connections_expose_routing_guidance_and_route_account_reads(two_accounts):
    settings, _, _, _ = two_accounts
    mcp, service = create_server(settings)

    async def run():
        _, discovery = await mcp.call_tool("list_brokers", {})
        assert {c["connection_id"] for c in discovery["result"]} == {
            "paper",
            "us-main",
            "us-second",
        }
        with pytest.raises(Exception, match="Select connection_id"):
            await mcp.call_tool("get_positions", {"broker_id": "alpaca"})
        _, selected = await mcp.call_tool(
            "get_positions", {"broker_id": "alpaca", "connection_id": "us-second"}
        )
        assert selected["result"][0]["account_ref"]["account_id"] == "account-two"

    try:
        asyncio.run(run())
    finally:
        service.close()


@pytest.mark.parametrize("change", [{"broker_id": "us-main"}, {"connection_id": "us-main"}])
def test_named_read_connection_cannot_be_used_for_order_execution(change):
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(
            {
                "symbol": "US:AAPL",
                "quantity": 1,
                "limit_price": "100",
                "idempotency_key": "synthetic-idempotency",
                **change,
            }
        )
