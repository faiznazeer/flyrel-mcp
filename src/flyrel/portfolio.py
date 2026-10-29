"""Position-only snapshots with explicit account boundaries and missing-value reporting."""

from datetime import datetime
from decimal import Decimal

from flyrel.instruments import InstrumentRegistry
from flyrel.models import Account, AccountIdentity, Position, currency_for


def account_ref(broker_id: str, account_id: str, environment: str) -> dict:
    return AccountIdentity(
        broker_id=broker_id, account_id=account_id, environment=environment
    ).model_dump(mode="json")


def label_rows(
    rows: list,
    *,
    broker_id: str,
    connection_id: str,
    environment: str,
    registry: InstrumentRegistry,
    accounts: list[Account] | None = None,
) -> list[dict]:
    account_currencies = {(a.account_id, a.currency) for a in accounts or []}
    output = []
    for model in rows:
        row = model.model_dump(mode="json")
        if row.get("broker_id", broker_id) != broker_id:
            raise ValueError("Broker identity changed during read")
        if row.get("environment", environment) != environment:
            raise ValueError("Environment identity changed during read")
        if row.get("synthetic", environment == "synthetic") != (environment == "synthetic"):
            raise ValueError("Synthetic data label does not match the connection environment")
        if "symbol" in row:
            currency = currency_for(row["symbol"])
            if row.get("currency", currency) != currency:
                raise ValueError("Symbol currency does not match its supported market")
            row.setdefault("currency", currency)
        if "account_id" in row and accounts is not None:
            if (row["account_id"], row["currency"]) not in account_currencies:
                raise ValueError("Position account/currency does not match discovered accounts")
        row.update(
            broker_id=broker_id,
            connection_id=connection_id,
            environment=environment,
            synthetic=environment == "synthetic",
        )
        if "account_id" in row:
            row["account_ref"] = account_ref(broker_id, row["account_id"], environment)
        if "symbol" in row:
            row = registry.annotate(row)
        output.append(row)
    return output


def position_values(positions: list[Position]) -> dict:
    priced = {}
    unpriced = set()
    missing = 0
    for position in positions:
        if position.market_value is None:
            missing += 1
            unpriced.add(position.currency)
        else:
            priced[position.currency] = (
                priced.get(position.currency, Decimal(0)) + position.market_value
            )
    currencies = set(priced) | unpriced
    return {
        "positions_value_by_currency": {
            currency: None if currency in unpriced else str(priced[currency])
            for currency in sorted(currencies)
        },
        "priced_positions_value_by_currency": {c: str(v) for c, v in sorted(priced.items())},
        "positions_value_complete": missing == 0,
        "unpriced_position_count": missing,
    }


def portfolio_snapshot(
    *,
    connection_id: str,
    broker_id: str,
    environment: str,
    accounts: list[Account],
    positions: list[Position],
    holdings: list[Position],
    registry: InstrumentRegistry,
    observed_at: datetime,
) -> dict:
    if not accounts or len({(a.account_id, a.currency) for a in accounts}) != len(accounts):
        raise ValueError("Accounts must be nonempty and unique within a connection")
    context = dict(
        broker_id=broker_id,
        connection_id=connection_id,
        environment=environment,
        registry=registry,
    )
    account_rows = label_rows(accounts, **context)
    position_rows = label_rows(positions, **context, accounts=accounts)
    holding_rows = label_rows(holdings, **context, accounts=accounts)
    return {
        "connection_id": connection_id,
        "broker_id": broker_id,
        "environment": environment,
        "synthetic": environment == "synthetic",
        "observed_at": observed_at.isoformat(),
        "accounts": [
            {
                **{k: v for k, v in account.items() if k != "cash"},
                **position_values(
                    [
                        p
                        for p in positions
                        if p.account_id == account["account_id"]
                        and p.currency == account["currency"]
                    ]
                ),
            }
            for account in account_rows
        ],
        **position_values(positions),
        "positions": position_rows,
        "holdings_separate_view": holding_rows,
        "holdings_relationship": "alias_of_positions"
        if broker_id == "alpaca"
        else "separate_unreconciled"
        if broker_id == "kite"
        else "empty_local_sandbox",
    }


def portfolio_report(snapshots: list[dict]) -> dict:
    identities = {}
    for snapshot in snapshots:
        for account in snapshot["accounts"]:
            ref = AccountIdentity.model_validate(account["account_ref"])
            identities.setdefault(ref, set()).add(snapshot["connection_id"])
    return {
        "brokers": snapshots,
        "duplicate_accounts": [
            {"account_ref": ref.model_dump(mode="json"), "connection_ids": sorted(connections)}
            for ref, connections in identities.items()
            if len(connections) > 1
        ],
        "complete_consolidated_nav": False,
        "note": "Separate connection/account position snapshots. No cash, FX, cross-account "
        "netting, or Kite holding/position reconciliation. Duplicate connections are flagged.",
    }
