from functools import wraps
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import AwareDatetime, Field

from brokerbridge.adapters.base import Interval
from brokerbridge.config import Settings
from brokerbridge.models import OrderRequest, Symbol, currency_for
from brokerbridge.service import Service


def create_server(settings: Settings | None = None) -> tuple[FastMCP, Service]:
    service = Service(settings or Settings())
    mcp = FastMCP(
        "BrokerBridge",
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
        """List configured brokers, supported markets, and capability flags."""
        return [
            {
                "id": a.id,
                "markets": a.markets,
                "environment": a.environment,
                "capabilities": sorted(a.capabilities),
            }
            for a in service.adapters.values()
        ]

    @tool
    def get_capabilities(broker_id: str) -> list[str]:
        """Get the capabilities of one configured broker."""
        return sorted(service.adapter(broker_id, "accounts").capabilities)

    @tool
    def list_accounts(broker_id: str) -> list[dict[str, Any]]:
        """Read accounts; synthetic, broker-paper and live balances are labelled separately."""
        return [
            a.model_dump(mode="json") for a in service.adapter(broker_id, "accounts").accounts()
        ]

    @tool
    def get_quotes(
        broker_id: str, symbols: Annotated[list[Symbol], Field(min_length=1, max_length=50)]
    ) -> list[dict[str, Any]]:
        """Read quotes for canonical equity symbols. Paper quotes are fixed synthetic fixtures."""
        return [
            q.model_dump(mode="json") for q in service.adapter(broker_id, "quotes").quotes(symbols)
        ]

    if any("history" in a.capabilities for a in service.adapters.values()):

        @tool
        def get_history(
            broker_id: str,
            symbol: Symbol,
            interval: Interval,
            start: AwareDatetime,
            end: AwareDatetime,
        ) -> list[dict[str, Any]]:
            """Read raw equity bars for timezone-aware bounds; requires broker data entitlement."""
            if (end - start).total_seconds() > 31 * 86400:
                raise ValueError("Request at most 31 days per call")
            return [
                b.model_dump(mode="json")
                for b in service.adapter(broker_id, "history").history(symbol, interval, start, end)
            ]

    @tool
    def get_positions(broker_id: str) -> list[dict[str, Any]]:
        """Read broker positions. Do not add this collection to holdings without reconciliation."""
        return [
            p.model_dump(mode="json") for p in service.adapter(broker_id, "positions").positions()
        ]

    @tool
    def get_holdings(broker_id: str) -> list[dict[str, Any]]:
        """Read holdings. Alpaca holdings alias positions; Kite holdings are a separate view."""
        return [
            p.model_dump(mode="json") for p in service.adapter(broker_id, "holdings").holdings()
        ]

    @tool
    def get_portfolio_summary() -> dict[str, Any]:
        """Read separate broker position snapshots by currency; no FX conversion or netting."""
        snapshots = []
        for broker_id in service.adapters:
            adapter = service.adapter(broker_id, "positions")
            positions = adapter.positions()
            # Kite delivery positions can overlap holdings; expose separate views until reconciled.
            holdings = adapter.holdings() if broker_id == "kite" else []
            totals = {}
            for p in positions:
                if p.market_value is None:
                    raise ValueError("Cannot total unpriced positions")
                totals[p.currency] = totals.get(p.currency, 0) + p.market_value
            snapshots.append(
                {
                    "broker_id": broker_id,
                    "environment": adapter.environment,
                    "positions_value_by_currency": {c: str(v) for c, v in totals.items()},
                    "positions": [p.model_dump(mode="json") for p in positions],
                    "holdings_separate_view": [p.model_dump(mode="json") for p in holdings],
                }
            )
        return {
            "brokers": snapshots,
            "complete_consolidated_nav": False,
            "note": "Positions only. No cash, FX, or Kite holding/position reconciliation.",
        }

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
    def list_orders(broker_id: str = "paper") -> dict[str, Any]:
        """Read local paper orders, Alpaca open orders, or Kite's current-day order book."""
        adapter = service.adapter(broker_id, "orders")
        orders = service.store.orders() if broker_id == "paper" else adapter.orders()
        return {
            "scope": {"paper": "all local", "alpaca": "open", "kite": "current day"}[broker_id],
            "orders": [o.model_dump(mode="json") for o in orders],
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
