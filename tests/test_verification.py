import json
import sys
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from flyrel import cli, verification
from flyrel.adapters import external_adapter
from flyrel.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        state_dir=tmp_path / "must-not-exist",
        kite_api_key="",
        kite_access_token="",
        alpaca_api_key="",
        alpaca_secret_key="",
        alpaca_paper=True,
    )


def test_missing_credentials_report_both_brokers_without_creating_state(settings):
    report = verification.verify_brokers(settings, ["kite", "alpaca"])
    assert report["passed"] is False
    assert [r["status"] for r in report["brokers"]] == ["not_configured", "not_configured"]
    assert not settings.state_dir.exists()


def test_partial_credentials_report_configuration_failure(settings):
    settings.kite_api_key = SecretStr("synthetic-key")
    report = verification.verify_brokers(settings, ["kite"])
    assert report["brokers"][0]["status"] == "configuration_error"


def test_verification_checks_both_brokers_without_exposing_portfolio(
    settings, broker_contract, monkeypatch
):
    adapters = {b: broker_contract(b)[0] for b in ("kite", "alpaca")}
    monkeypatch.setattr(verification, "external_adapter", lambda _, b: adapters[b])
    report = verification.verify_brokers(
        settings,
        ["kite", "alpaca"],
        history_start=datetime(2026, 1, 5, tzinfo=UTC),
        history_end=datetime(2026, 1, 7, tzinfo=UTC),
    )
    assert report["passed"] and report["read_only"]
    assert report["live_execution_implemented"] is False
    assert [(b["broker_id"], b["environment"], b["currency"]) for b in report["brokers"]] == [
        ("kite", "live", "INR"),
        ("alpaca", "paper", "USD"),
    ]
    assert all(len(b["checks"]) == 6 for b in report["brokers"])
    serialized = json.dumps(report)
    for private in ("synthetic-kite-account", "synthetic-alpaca-account", "1234.56", "3000.45"):
        assert private not in serialized
    assert not settings.state_dir.exists()
    assert all(a.client.is_closed for a in adapters.values())


@pytest.mark.parametrize("status,reason", [(401, "auth_or_access"), (429, "rate_limited")])
def test_verification_stops_failed_broker_but_checks_other_broker(
    settings, broker_contract, monkeypatch, status, reason
):
    kite, _, kite_calls = broker_contract("kite")
    alpaca, _, alpaca_calls = broker_contract("alpaca")
    kite.client.close()
    kite.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(status, text="secret-broker-response")
        )
    )
    monkeypatch.setattr(
        verification, "external_adapter", lambda _, b: {"kite": kite, "alpaca": alpaca}[b]
    )
    report = verification.verify_brokers(settings, ["kite", "alpaca"])
    assert not report["passed"]
    assert len(report["brokers"][0]["checks"]) == 1
    assert report["brokers"][0]["checks"][0]["reason"] == reason
    assert report["brokers"][1]["status"] == "passed"
    assert not kite_calls and alpaca_calls
    assert "secret-broker-response" not in json.dumps(report)


def test_invalid_broker_schema_is_sanitized_and_client_closed(
    settings, broker_contract, monkeypatch
):
    adapter, payload, _ = broker_contract("alpaca")
    payload["account"]["cash"] = "private-invalid-value"
    monkeypatch.setattr(verification, "external_adapter", lambda *_: adapter)
    report = verification.verify_brokers(settings, ["alpaca"])
    assert report["brokers"][0]["checks"][0]["reason"] == "response_validation"
    assert "private-invalid-value" not in json.dumps(report)
    assert adapter.client.is_closed


def test_empty_positions_are_successful_reads_not_verified_holdings(
    settings, broker_contract, monkeypatch
):
    adapter, payload, _ = broker_contract("alpaca")
    payload["positions"] = []
    monkeypatch.setattr(verification, "external_adapter", lambda *_: adapter)
    report = verification.verify_brokers(settings, ["alpaca"])
    assert report["passed"]
    assert report["brokers"][0]["checks"][1] == {
        "operation": "positions",
        "status": "passed",
        "count": 0,
    }
    assert "reconciliation is still required" in report["scope"]


@pytest.mark.parametrize(
    "invalid",
    [
        {"brokers": []},
        {"brokers": ["paper"]},
        {"history_start": datetime(2026, 1, 5, tzinfo=UTC)},
        {"history_start": datetime(2026, 1, 5), "history_end": datetime(2026, 1, 7)},
        {
            "history_start": datetime(2026, 1, 5, tzinfo=UTC),
            "history_end": datetime(2026, 3, 7, tzinfo=UTC),
        },
    ],
)
def test_invalid_request_makes_no_connections(settings, monkeypatch, invalid):
    def forbidden(*_):
        pytest.fail("Invalid request must not construct adapters")

    monkeypatch.setattr(verification, "external_adapter", forbidden)
    args = {"brokers": ["kite"], **invalid}
    with pytest.raises(ValueError):
        verification.verify_brokers(settings, **args)


@pytest.mark.parametrize("passed", [True, False])
def test_cli_verification_exit_status(settings, monkeypatch, capsys, passed):
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "verify_brokers", lambda *_, **__: {"passed": passed})
    monkeypatch.setattr(sys, "argv", ["flyrel", "verify-brokers", "--broker", "kite"])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == (0 if passed else 1)
    assert json.loads(capsys.readouterr().out) == {"passed": passed}


def test_shared_factory_keeps_live_read_only_mapping_and_partial_config_checks(settings):
    settings.alpaca_api_key = SecretStr("synthetic-key")
    settings.alpaca_secret_key = SecretStr("synthetic-secret")
    settings.alpaca_paper = False
    adapter = external_adapter(settings, "alpaca")
    try:
        assert adapter.environment == "live"
        assert adapter.base == "https://api.alpaca.markets"
        assert "paper_orders" not in adapter.capabilities
    finally:
        adapter.close()
    settings.alpaca_secret_key = SecretStr("")
    with pytest.raises(ValueError, match="both Alpaca"):
        external_adapter(settings, "alpaca")


def test_verification_checks_all_named_accounts_and_can_select_just_one(
    tmp_path, monkeypatch, broker_contract
):
    settings = Settings(
        _env_file=None,
        state_dir=tmp_path / "no-state",
        broker_connections=[
            {
                "connection_id": "us-first",
                "broker_id": "alpaca",
                "environment": "paper",
                "api_key": "synthetic-key",
                "secret_key": "synthetic-secret",
            },
            {
                "connection_id": "us-second",
                "broker_id": "alpaca",
                "environment": "live",
                "api_key": "synthetic-key",
                "secret_key": "synthetic-secret",
            },
        ],
    )

    def factory(_, key):
        return broker_contract("alpaca", paper=key == "us-first")[0]

    monkeypatch.setattr(verification, "external_adapter", factory)
    report = verification.verify_brokers(settings, ["alpaca"])
    assert report["passed"]
    assert [(r["connection_id"], r["environment"]) for r in report["brokers"]] == [
        ("us-first", "paper"),
        ("us-second", "live"),
    ]
    selected = verification.verify_brokers(settings, ["alpaca"], connection_ids=["us-second"])
    assert selected["passed"] and len(selected["brokers"]) == 1
    for secret in ("synthetic-key", "synthetic-secret", "synthetic-alpaca-account"):
        assert secret not in json.dumps(report)
    assert not settings.state_dir.exists()


@pytest.mark.parametrize("connections", [["missing"], ["alpaca"], [], ["kite", "kite"]])
def test_bad_connection_selection_makes_no_requests(settings, monkeypatch, connections):
    def forbidden(*_):
        pytest.fail("Invalid routing must fail before constructing adapters")

    monkeypatch.setattr(verification, "external_adapter", forbidden)
    with pytest.raises(ValueError):
        verification.verify_brokers(settings, ["kite"], connection_ids=connections)
