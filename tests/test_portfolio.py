import json
import sys
from datetime import UTC, datetime

import httpx
import pytest

from flyrel import cli
from flyrel.demo import demo_portfolio, demo_registry
from flyrel.models import Account, Position
from flyrel.portfolio import portfolio_report, portfolio_snapshot


def snapshot(
    *,
    account_id="synthetic-account",
    broker_id="alpaca",
    environment="synthetic",
    connection_id="demo",
    currency="USD",
    position_changes=None,
):
    account = Account(
        broker_id=broker_id, account_id=account_id, currency=currency, environment=environment
    )
    position = Position.model_validate(
        {
            "broker_id": broker_id,
            "account_id": account_id,
            "environment": environment,
            "symbol": "US:AAPL",
            "currency": currency,
            "quantity": "2.5",
            "average_price": "80",
            "market_value": "250",
            "product": "equity",
            **(position_changes or {}),
        }
    )
    return portfolio_snapshot(
        connection_id=connection_id,
        broker_id=broker_id,
        environment=environment,
        accounts=[account],
        positions=[position],
        holdings=[],
        registry=demo_registry(),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_synthetic_workflow_keeps_all_accounts_separate_and_unpriced_values_visible():
    report = demo_portfolio()
    assert report == demo_portfolio()
    assert report["synthetic"] and not report["complete_consolidated_nav"]
    assert len(report["brokers"]) == 4
    assert len({a["accounts"][0]["account_id"] for a in report["brokers"]}) == 4
    first, second, third, fourth = report["brokers"]
    assert first["positions_value_by_currency"] == {"INR": "-2000"}
    assert first["holdings_separate_view"][0]["market_value"] == "3000"
    assert second["positions_value_by_currency"] == {"INR": "1000"}
    assert third["positions_value_by_currency"] == {"USD": "-275"}
    assert third["holdings_relationship"] == "alias_of_positions"
    assert fourth["positions_value_by_currency"] == {"USD": None}
    assert fourth["priced_positions_value_by_currency"] == {"USD": "200"}
    assert not fourth["positions_value_complete"] and fourth["unpriced_position_count"] == 1
    assert fourth["positions"][1]["market_value"] is None
    assert fourth["accounts"][0]["positions_value_by_currency"] == {"USD": None}
    assert all(s["environment"] == "synthetic" for s in report["brokers"])
    assert all(
        p["synthetic"] and p["instrument_metadata_synthetic"]
        for s in report["brokers"]
        for p in s["positions"] + s["holdings_separate_view"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"account_id": "wrong-account"},
        {"currency": "INR"},
        {"environment": "live"},
        {"broker_id": "kite"},
    ],
)
def test_portfolio_rejects_cross_account_currency_environment_or_broker_contamination(change):
    with pytest.raises(ValueError):
        snapshot(position_changes=change)


def test_same_account_identifier_at_different_brokers_is_not_a_duplicate():
    report = portfolio_report([snapshot(), snapshot(connection_id="paper-demo", broker_id="paper")])
    assert report["duplicate_accounts"] == []
    assert {s["accounts"][0]["account_ref"]["broker_id"] for s in report["brokers"]} == {
        "alpaca",
        "paper",
    }


def test_unregistered_instrument_is_retained_without_fabricating_identity_or_value():
    result = snapshot(position_changes={"symbol": "US:UNKNOWN", "market_value": None})
    row = result["positions"][0]
    assert row["symbol"] == "US:UNKNOWN" and row["instrument_id"] is None
    assert result["positions_value_by_currency"] == {"USD": None}
    assert result["priced_positions_value_by_currency"] == {}


def test_cli_demo_requires_neither_settings_nor_http_and_writes_no_state(
    tmp_path, monkeypatch, capsys
):
    def forbidden(*_, **__):
        pytest.fail("Synthetic workflow must not load credentials or make network calls")

    monkeypatch.setattr(cli, "Settings", forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["flyrel", "demo-portfolio"])
    cli.main()
    report = json.loads(capsys.readouterr().out)
    assert report["synthetic"] and len(report["brokers"]) == 4
    assert list(tmp_path.iterdir()) == []
