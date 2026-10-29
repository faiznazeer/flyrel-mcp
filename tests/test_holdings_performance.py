import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from flyrel import cli
from flyrel import service as service_module
from flyrel.config import Settings
from flyrel.demo import demo_registry
from flyrel.models import Account, Position, PositionPerformance
from flyrel.portfolio import holding_metrics, holdings_snapshot
from flyrel.server import create_server


def holding(**changes):
    return Position.model_validate(
        {
            "broker_id": "kite",
            "account_id": "synthetic-account",
            "environment": "live",
            "symbol": "NSE:RELIANCE",
            "currency": "INR",
            "quantity": "3",
            "average_price": "900.25",
            "market_value": "3000.45",
            "product": "CNC",
            "performance": {
                "source": "kite_holdings",
                "unrealized_pnl": "299.70",
                "day_price_change": "-9.85",
                "day_price_change_percent": "-0.9752475247524752",
            },
            **changes,
        }
    )


def test_missing_performance_and_price_do_not_become_zero_or_inferred_profit():
    result = holding_metrics([holding(), holding(market_value=None, performance=None)])
    assert result["holding_count"] == 2
    assert result["market_value"] == {
        "value": None,
        "known_value": "3000.45",
        "complete": False,
        "missing_count": 1,
    }
    assert result["unrealized_pnl"] == {
        "value": None,
        "known_value": "299.70",
        "complete": False,
        "missing_count": 1,
    }
    # Daily price change times quantity is NOT broker-reported daily monetary P&L.
    assert result["day_unrealized_pnl"] == {
        "value": None,
        "known_value": "0",
        "complete": False,
        "missing_count": 2,
    }


def test_reported_zero_pnl_and_empty_holdings_are_distinct_from_missing_data():
    zero = holding(performance={"source": "kite_holdings", "unrealized_pnl": "0"})
    assert holding_metrics([zero])["unrealized_pnl"] == {
        "value": "0",
        "known_value": "0",
        "complete": True,
        "missing_count": 0,
    }
    result = holding_metrics([])
    assert result["holding_count"] == 0
    assert result["market_value"]["value"] == "0"
    assert result["day_unrealized_pnl"]["complete"] is True


def test_gains_losses_and_fractional_values_sum_as_decimals_not_float():
    rows = [
        holding(performance={"source": "kite_holdings", "unrealized_pnl": "-0.2"}),
        holding(performance={"source": "kite_holdings", "unrealized_pnl": "0.3"}),
    ]
    assert holding_metrics(rows)["unrealized_pnl"]["value"] == "0.1"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_broker_performance_fails_validation(value):
    with pytest.raises(ValidationError):
        PositionPerformance(source="kite_holdings", unrealized_pnl=value)


def test_kite_positions_pnl_is_not_mislabeled_as_holdings_unrealized_pnl(broker_contract):
    adapter, payload, _ = broker_contract("kite")
    payload["positions"]["data"]["net"][0]["pnl"] = 987
    assert adapter.positions()[0].performance is None


@pytest.mark.parametrize("broker_id", ["kite", "alpaca"])
def test_absent_optional_broker_fields_remain_unknown_without_computation(
    broker_contract, broker_id
):
    adapter, payload, _ = broker_contract(broker_id)
    if broker_id == "kite":
        row = payload["holdings"]["data"][0]
        fields = ("last_price", "pnl", "day_change", "day_change_percentage")
    else:
        row = payload["positions"][0]
        fields = ("unrealized_pl", "unrealized_intraday_pl", "change_today")
    for field in fields:
        row.pop(field)
    result = adapter.holdings()[0]
    assert result.performance.unrealized_pnl is None
    assert result.performance.day_unrealized_pnl is None
    assert result.performance.day_price_change_percent is None
    if broker_id == "kite":
        assert result.market_value is None


def test_snapshot_groups_accounts_and_currencies_without_exposing_cash_or_global_totals():
    first = Account(
        broker_id="kite", account_id="synthetic-account", environment="live", currency="INR"
    )
    second = first.model_copy(update={"account_id": "synthetic-second", "cash": Decimal("999")})
    report = holdings_snapshot(
        connection_id="in-main",
        broker_id="kite",
        environment="live",
        accounts=[first, second],
        holdings=[holding()],
        registry=demo_registry(),
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert report["complete_consolidated_nav"] is False
    assert report["holdings_relationship"] == "separate_unreconciled"
    assert "market_value" not in report and "unrealized_pnl" not in report
    assert [a["holdings_summary"]["holding_count"] for a in report["accounts"]] == [1, 0]
    assert all("cash" not in a for a in report["accounts"])
    row = report["holdings"][0]
    assert row["connection_id"] == "in-main" and row["currency"] == "INR"
    assert row["account_ref"] == {
        "broker_id": "kite",
        "account_id": "synthetic-account",
        "environment": "live",
    }
    assert row["synthetic"] is False and row["instrument_metadata_synthetic"] is True


def test_holdings_only_snapshot_rejects_wrong_account_or_environment():
    account = Account(
        broker_id="kite", account_id="synthetic-account", environment="live", currency="INR"
    )
    for change in ({"account_id": "wrong"}, {"environment": "paper"}, {"currency": "USD"}):
        with pytest.raises(ValueError):
            holdings_snapshot(
                connection_id="kite",
                broker_id="kite",
                environment="live",
                accounts=[account],
                holdings=[holding(**change)],
                registry=demo_registry(),
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
            )


def test_mcp_holdings_summary_needs_only_account_and_holdings_reads(
    tmp_path, monkeypatch, broker_contract
):
    adapter, _, calls = broker_contract("kite")
    monkeypatch.setattr(
        service_module, "external_adapter", lambda _, key: adapter if key == "kite" else None
    )
    mcp, service = create_server(Settings(_env_file=None, state_dir=tmp_path))

    async def run():
        _, result = await mcp.call_tool("get_holdings_summary", {"broker_id": "kite"})
        summary = result["accounts"][0]["holdings_summary"]
        assert summary["holding_count"] == 1
        assert summary["market_value"]["value"] == "3000.45"
        assert summary["unrealized_pnl"]["value"] == "299.7"
        assert summary["day_unrealized_pnl"]["value"] is None
        assert result["holdings"][0]["performance"]["day_price_change"] == "-9.85"
        assert result["holdings"][0]["performance"]["price_timestamp"] is None
        assert {r.url.path for r in calls} == {"/user/profile", "/portfolio/holdings"}
        assert all(r.method == "GET" for r in calls)
        with service.store.db() as db:
            audit = db.execute(
                "SELECT action, outcome FROM audit WHERE action = 'get_holdings_summary'"
            ).fetchall()
        assert audit == [
            ("get_holdings_summary", "started"),
            ("get_holdings_summary", "succeeded"),
        ]

    try:
        asyncio.run(run())
    finally:
        service.close()


def test_alpaca_alias_is_summarized_once_with_signed_pnl(tmp_path, monkeypatch, broker_contract):
    adapter, _, calls = broker_contract("alpaca")
    monkeypatch.setattr(
        service_module, "external_adapter", lambda _, key: adapter if key == "alpaca" else None
    )
    mcp, service = create_server(Settings(_env_file=None, state_dir=tmp_path))

    async def run():
        _, result = await mcp.call_tool("get_holdings_summary", {"broker_id": "alpaca"})
        summary = result["accounts"][0]["holdings_summary"]
        assert summary["holding_count"] == 2
        assert summary["market_value"]["value"] == "-275.00"
        assert summary["unrealized_pnl"]["value"] == "45.34375"
        assert summary["day_unrealized_pnl"]["value"] == "-1.5"
        assert result["holdings_relationship"] == "alias_of_positions"
        assert result["environment"] == "paper" and result["synthetic"] is False
        assert sum(r.url.path == "/v2/positions" for r in calls) == 1

    try:
        asyncio.run(run())
    finally:
        service.close()


@pytest.mark.parametrize("fail", [False, True])
def test_cli_summary_outputs_report_or_sanitized_error_and_closes_adapter(
    tmp_path, monkeypatch, capsys, broker_contract, fail
):
    adapter, _, calls = broker_contract("kite")
    monkeypatch.setattr(
        service_module, "external_adapter", lambda _, key: adapter if key == "kite" else None
    )
    monkeypatch.setattr(cli, "Settings", lambda: Settings(_env_file=None, state_dir=tmp_path))
    monkeypatch.setattr(sys, "argv", ["flyrel", "holdings-summary", "--broker", "kite"])
    if fail:

        def private_failure():
            raise ValueError("private-broker-payload")

        monkeypatch.setattr(adapter, "holdings", private_failure)
        with pytest.raises(SystemExit) as caught:
            cli.main()
        assert caught.value.code == 1
        output = capsys.readouterr()
        assert not output.out and "private-broker-payload" not in output.err
        assert "Holdings read failed" in output.err
    else:
        cli.main()
        report = json.loads(capsys.readouterr().out)
        assert report["accounts"][0]["holdings_summary"]["unrealized_pnl"]["value"] == "299.7"
        assert all(r.url.path in {"/portfolio/holdings", "/user/profile"} for r in calls)
    assert adapter.client.is_closed
