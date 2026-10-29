from datetime import UTC, datetime
from pathlib import Path

from flyrel.adapters import external_adapter
from flyrel.adapters.paper import PaperAdapter
from flyrel.config import Settings
from flyrel.instruments import InstrumentRegistry
from flyrel.models import Policy, currency_for
from flyrel.portfolio import (
    account_ref,
    holdings_snapshot,
    label_rows,
    portfolio_report,
    portfolio_snapshot,
)
from flyrel.store import Store


class ConnectionSelectionError(ValueError):
    """Public routing guidance that contains no account or credential details."""


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.registry = InstrumentRegistry.load(settings.instrument_registry_file)
        self.store = Store(settings.state_dir)
        self.adapters = {"paper": PaperAdapter()}
        try:
            for broker_id in ("kite", "alpaca"):
                for connection_id in settings.connection_ids(broker_id):
                    adapter = external_adapter(settings, connection_id)
                    if adapter is not None:
                        self.adapters[connection_id] = adapter
        except Exception:
            self.close()
            raise

    @property
    def policy_path(self) -> Path:
        return self.settings.state_dir / "policy.json"

    def policy(self) -> Policy:
        # Reload before each decision; malformed policy fails closed.
        return (
            Policy.model_validate_json(self.policy_path.read_text())
            if self.policy_path.exists()
            else Policy()
        )

    def connection(self, broker_id: str, capability: str, connection_id: str | None = None):
        if connection_id is None:
            candidates = [key for key, a in self.adapters.items() if a.id == broker_id]
            if not candidates:
                raise ConnectionSelectionError("Broker is not configured; use list_brokers")
            if len(candidates) != 1:
                raise ConnectionSelectionError(
                    "Select connection_id when a broker has multiple connections; use list_brokers"
                )
            connection_id = candidates[0]
        adapter = self.adapters.get(connection_id)
        if adapter is None or adapter.id != broker_id:
            raise ConnectionSelectionError("Connection does not belong to the requested broker")
        if capability not in adapter.capabilities:
            raise ValueError(f"Broker does not support {capability}")
        return connection_id, adapter

    def adapter(self, broker_id: str, capability: str, connection_id: str | None = None):
        return self.connection(broker_id, capability, connection_id)[1]

    def read(self, broker_id: str, operation: str, connection_id: str | None = None, *args):
        connection_id, adapter = self.connection(broker_id, operation, connection_id)
        accounts = None
        if operation == "orders" and broker_id == "paper":
            rows = self.store.orders()
        else:
            rows = getattr(adapter, operation)(*args)
        if operation in {"positions", "holdings", "orders"}:
            accounts = adapter.accounts()
            if not accounts:
                raise ValueError("No account returned for this connection")
            label_rows(
                accounts,
                broker_id=broker_id,
                connection_id=connection_id,
                environment=adapter.environment,
                registry=self.registry,
            )
        result = label_rows(
            rows,
            broker_id=broker_id,
            connection_id=connection_id,
            environment=adapter.environment,
            registry=self.registry,
            accounts=accounts if operation in {"positions", "holdings"} else None,
        )
        if operation == "orders":
            for row in result:
                matching = [a for a in accounts if a.currency == currency_for(row["symbol"])]
                if len(matching) != 1:
                    raise ValueError("Cannot associate an order with exactly one account")
                row["account_id"] = matching[0].account_id
                row["account_ref"] = account_ref(
                    broker_id, matching[0].account_id, adapter.environment
                )
        return result

    def holdings_summary(self, broker_id: str, connection_id: str | None = None):
        connection_id, adapter = self.connection(broker_id, "holdings", connection_id)
        return holdings_snapshot(
            connection_id=connection_id,
            broker_id=broker_id,
            environment=adapter.environment,
            accounts=adapter.accounts(),
            holdings=adapter.holdings(),
            registry=self.registry,
            observed_at=datetime.now(UTC),
        )

    def portfolio(self, connection_ids: list[str] | None = None):
        selected = list(self.adapters) if connection_ids is None else connection_ids
        if not selected or len(set(selected)) != len(selected):
            raise ConnectionSelectionError("Select at least one unique connection")
        if any(key not in self.adapters for key in selected):
            raise ConnectionSelectionError("Unknown portfolio connection; use list_brokers")
        snapshots = []
        for connection_id in selected:
            adapter = self.adapters[connection_id]
            snapshots.append(
                portfolio_snapshot(
                    connection_id=connection_id,
                    broker_id=adapter.id,
                    environment=adapter.environment,
                    accounts=adapter.accounts(),
                    positions=adapter.positions(),
                    holdings=adapter.holdings() if adapter.id == "kite" else [],
                    registry=self.registry,
                    observed_at=datetime.now(UTC),
                )
            )
        return portfolio_report(snapshots)

    def close(self):
        for adapter in self.adapters.values():
            adapter.close()
