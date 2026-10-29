from functools import wraps
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import AwareDatetime, Field

from flyrel.adapters.base import Interval
from flyrel.config import Settings
from flyrel.demo import demo_portfolio
from flyrel.models import OrderRequest, Symbol, currency_for
from flyrel.service import ConnectionSelectionError, Service


def create_server(settings: Settings | None = None) -> tuple[FastMCP, Service]:
    service = Service(settings or Settings())
    mcp = FastMCP(
        "Flyrel",
        instructions=(
            "External brokers are read-only. Paper tools use synthetic local state. "
            "Two calls do not prove human approval. Synthetic quotes are not market data."
        ),
    )

    def tool(fn):
        @wraps(fn)
        def audited(*args, **kwargs):
            service.store.audit(fn.__name__, "started")
            try:
                result = fn(*args, **kwargs)
            except ConnectionSelectionError as exc:
                service.store.audit(fn.__name__, "failed")
                raise ValueError(str(exc)) from None
            except Exception:
                service.store.audit(fn.__name__, "failed")
                raise ValueError(
                    "Operation failed; verify inputs, policy, credentials and broker "
                    "availability. External broker details are not logged."
                ) from None
            service.store.audit(fn.__name__, "succeeded")
            return result

        return mcp.tool()(audited)

    @tool
    def list_brokers() -> list[dict[str, Any]]:
        """List connections with broker IDs, environments and capabilities; no credentials."""
        return [
            {
                "id": a.id,
                "broker_id": a.id,
                "connection_id": connection_id,
                "markets": a.markets,
                "environment": a.environment,
                "capabilities": sorted(a.capabilities),
            }
            for connection_id, a in service.adapters.items()
        ]

    @tool
    def get_capabilities(broker_id: str, connection_id: str | None = None) -> list[str]:
        """Get read capabilities; select connection_id when a broker has multiple connections."""
        return sorted(service.adapter(broker_id, "accounts", connection_id).capabilities)

    @tool
    def list_accounts(broker_id: str, connection_id: str | None = None) -> list[dict[str, Any]]:
        """Read account identities/balances; select connection_id for multi-account brokers."""
        return service.read(broker_id, "accounts", connection_id)

    @tool
    def search_instruments(
        query: Annotated[str, Field(max_length=100)] = "",
        broker_id: Literal["kite", "alpaca", "paper"] | None = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> list[dict[str, Any]]:
        """Search the configured local instrument registry; no broker lookup or live master."""
        return [i.model_dump(mode="json") for i in service.registry.search(query, broker_id, limit)]

    @tool
    def resolve_instrument(
        identifier: Annotated[str, Field(min_length=1, max_length=100)],
        broker_id: Literal["kite", "alpaca", "paper"] | None = None,
    ) -> dict[str, Any]:
        """Resolve a local ID or canonical symbol; optionally require an explicit broker mapping."""
        return service.registry.resolve(identifier, broker_id).model_dump(mode="json")

    @tool
    def get_quotes(
        broker_id: str,
        symbols: Annotated[list[Symbol], Field(min_length=1, max_length=50)],
        connection_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read labelled quotes; select connection_id for multiple accounts. Paper is synthetic."""
        return service.read(broker_id, "quotes", connection_id, symbols)

    if any("history" in a.capabilities for a in service.adapters.values()):

        @tool
        def get_history(
            broker_id: str,
            symbol: Symbol,
            interval: Interval,
            start: AwareDatetime,
            end: AwareDatetime,
            connection_id: str | None = None,
        ) -> list[dict[str, Any]]:
            """Read labelled bars, <=31 days; Alpaca raw, capped at 100 pages/50,000 bars."""
            if (end - start).total_seconds() > 31 * 86400:
                raise ValueError("Request at most 31 days per call")
            return service.read(broker_id, "history", connection_id, symbol, interval, start, end)

    @tool
    def get_positions(broker_id: str, connection_id: str | None = None) -> list[dict[str, Any]]:
        """Read labelled positions; Alpaca includes broker performance, never account returns."""
        return service.read(broker_id, "positions", connection_id)

    @tool
    def get_holdings(broker_id: str, connection_id: str | None = None) -> list[dict[str, Any]]:
        """Read holdings with optional broker P&L/daily price change; not historical returns."""
        return service.read(broker_id, "holdings", connection_id)

    @tool
    def get_holdings_summary(broker_id: str, connection_id: str | None = None) -> dict[str, Any]:
        """Read holding counts/value/P&L per account/currency; flag missing data. No quotes/NAV.

        Select connection_id for multi-account brokers. Kite daily price change is not daily
        monetary P&L. Alpaca holdings alias positions. No history or account-growth calculation.
        """
        return service.holdings_summary(broker_id, connection_id)

    @tool
    def get_portfolio_summary(
        connection_ids: Annotated[list[str], Field(min_length=1, max_length=50)] | None = None,
    ) -> dict[str, Any]:
        """Read separate position/holding summaries per account; flag missing data. No FX/NAV."""
        return service.portfolio(connection_ids)

    @tool
    def get_demo_portfolio() -> dict[str, Any]:
        """Read fixed synthetic multi-account examples; no external reads or actual account data."""
        return demo_portfolio()

    @tool
    def get_policy() -> dict[str, Any]:
        """Read local paper limits and halt state. Policy changes require the local CLI."""
        return {
            "policy": service.policy().model_dump(mode="json"),
            "halted": service.store.halted(),
            "live_execution_implemented": False,
        }

    @tool
    def propose_order(request: OrderRequest) -> dict[str, Any]:
        """Validate a synthetic BUY limit order and return an expiring confirmation token."""
        result = service.store.propose(request, service.policy())
        result["currency"] = currency_for(request.symbol)
        return result

    @tool
    def confirm_order(
        token: Annotated[str, Field(min_length=20, max_length=100)],
    ) -> dict[str, Any]:
        """Confirm a local sandbox proposal. Creates an open synthetic order that never fills."""
        return service.store.confirm(token, service.policy()).model_dump(mode="json")

    @tool
    def list_orders(broker_id: str = "paper", connection_id: str | None = None) -> dict[str, Any]:
        """Read account-labelled local, Alpaca open or Kite day orders; select connection_id."""
        return {
            "scope": {"paper": "all local", "alpaca": "open", "kite": "current day"}[broker_id],
            "orders": service.read(broker_id, "orders", connection_id),
        }

    @tool
    def get_order_status(order_id: str) -> dict[str, Any]:
        """Read one local sandbox order. External broker status lookup is not implemented."""
        for order in service.store.orders():
            if order.order_id == order_id:
                return order.model_dump(mode="json")
        raise ValueError("Unknown paper order")

    @tool
    def cancel_order(order_id: str, broker_id: Literal["paper"] = "paper") -> dict[str, Any]:
        """Cancel one synthetic local order. Cannot cancel orders at an external broker."""
        return service.store.cancel(order_id).model_dump(mode="json")

    @tool
    def kill_switch() -> dict[str, Any]:
        """Persistently block new local paper orders. Does not cancel orders or affect brokers."""
        return service.store.halt()

    return mcp, service
