"""Fixed, invented multi-account examples; never construct an external adapter."""

from datetime import UTC, datetime
from importlib.resources import files

from flyrel.instruments import InstrumentCatalog, InstrumentRegistry
from flyrel.models import Account, Position
from flyrel.portfolio import portfolio_report, portfolio_snapshot

FIXTURE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def demo_registry() -> InstrumentRegistry:
    catalog = InstrumentCatalog.model_validate_json(
        files("flyrel").joinpath("data/demo-instruments.json").read_text()
    )
    return InstrumentRegistry(catalog.instruments)


def _positions(account: Account, rows: list) -> list[Position]:
    return [
        Position(
            broker_id=account.broker_id,
            account_id=account.account_id,
            currency=account.currency,
            environment="synthetic",
            symbol=symbol,
            quantity=quantity,
            average_price=average,
            market_value=value,
            product=product,
        )
        for symbol, quantity, average, value, product in rows
    ]


def demo_portfolio() -> dict:
    registry = demo_registry()
    snapshots = []
    scenarios = [
        (
            "demo-kite-main",
            "kite",
            "synthetic-kite-main",
            "INR",
            [("NSE:RELIANCE", "-2", "1010", "-2000", "MIS")],
            [("NSE:RELIANCE", "3", "900", "3000", "CNC")],
        ),
        (
            "demo-kite-second",
            "kite",
            "synthetic-kite-second",
            "INR",
            [("NSE:RELIANCE", "1", "900", "1000", "CNC")],
            [],
        ),
        (
            "demo-alpaca-main",
            "alpaca",
            "synthetic-alpaca-main",
            "USD",
            [
                ("US:AAPL", "1.25", "80", "125", "equity"),
                ("US:MSFT", "-2", "210", "-400", "equity"),
            ],
            [],
        ),
        (
            "demo-alpaca-second",
            "alpaca",
            "synthetic-alpaca-second",
            "USD",
            [("US:AAPL", "2", "80", "200", "equity"), ("US:MSFT", "1", "210", None, "equity")],
            [],
        ),
    ]
    for connection_id, broker_id, account_id, currency, raw_positions, raw_holdings in scenarios:
        account = Account(
            broker_id=broker_id, account_id=account_id, currency=currency, environment="synthetic"
        )

        snapshots.append(
            portfolio_snapshot(
                connection_id=connection_id,
                broker_id=broker_id,
                environment="synthetic",
                accounts=[account],
                positions=_positions(account, raw_positions),
                holdings=_positions(account, raw_holdings),
                registry=registry,
                observed_at=FIXTURE_TIME,
            )
        )
    return {
        **portfolio_report(snapshots),
        "synthetic": True,
        "source": "fixed synthetic workflow fixtures; no broker connection",
        "fixture_timestamp": FIXTURE_TIME.isoformat(),
        "instrument_catalog": [i.model_dump(mode="json") for i in registry.search("")],
        "validation_status": "synthetic walkthrough only; real-user/account validation pending",
    }
