import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from flyrel import service as service_module
from flyrel.config import Settings
from flyrel.server import create_server


def test_stdio_round_trip_without_credentials(tmp_path):
    async def run():
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLYREL_")}
        env.update(
            {
                "FLYREL_STATE_DIR": str(tmp_path / "state"),
                "FLYREL_KITE_API_KEY": "",
                "FLYREL_KITE_ACCESS_TOKEN": "",
                "FLYREL_ALPACA_API_KEY": "",
                "FLYREL_ALPACA_SECRET_KEY": "",
            }
        )
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "flyrel.cli", "serve"], env=env, cwd=tmp_path
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "Flyrel"
                tools = {t.name for t in (await session.list_tools()).tools}
                assert {"propose_order", "confirm_order", "get_quotes", "kill_switch"} <= tools
                assert "set_policy" not in tools and "get_history" not in tools
                holdings = await session.call_tool("get_holdings_summary", {"broker_id": "paper"})
                assert not holdings.isError
                assert holdings.structuredContent["synthetic"]
                assert (
                    holdings.structuredContent["accounts"][0]["holdings_summary"]["holding_count"]
                    == 0
                )
                demo = await session.call_tool("get_demo_portfolio", {})
                assert not demo.isError and demo.structuredContent["synthetic"]
                assert len(demo.structuredContent["brokers"]) == 4
                assert demo.structuredContent["brokers"][-1]["positions_value_by_currency"] == {
                    "USD": None
                }
                quotes = await session.call_tool(
                    "get_quotes", {"broker_id": "paper", "symbols": ["US:AAPL"]}
                )
                assert not quotes.isError
                assert '"synthetic": true' in quotes.content[0].text
                proposal = await session.call_tool(
                    "propose_order",
                    {
                        "request": {
                            "symbol": "US:AAPL",
                            "quantity": 1,
                            "limit_price": "100",
                            "idempotency_key": "stdio-demo-order",
                        }
                    },
                )
                assert not proposal.isError
                token = proposal.structuredContent["confirmation_token"]
                order = await session.call_tool("confirm_order", {"token": token})
                assert not order.isError
                assert order.structuredContent["environment"] == "synthetic"
                assert (await session.call_tool("kill_switch", {})).isError is False
                rejected = await session.call_tool(
                    "propose_order",
                    {
                        "request": {
                            "symbol": "US:AAPL",
                            "quantity": 1,
                            "limit_price": "100",
                            "idempotency_key": "stdio-second-order",
                        }
                    },
                )
                assert rejected.isError

    asyncio.run(run())


def test_portfolio_summary_keeps_currencies_environments_and_holdings_separate(
    tmp_path, monkeypatch, broker_contract
):
    adapters = {b: broker_contract(b)[0] for b in ("kite", "alpaca")}
    monkeypatch.setattr(service_module, "external_adapter", lambda _, b: adapters[b])
    mcp, service = create_server(Settings(_env_file=None, state_dir=tmp_path))

    async def run():
        _, result = await mcp.call_tool("get_portfolio_summary", {})
        assert result["complete_consolidated_nav"] is False
        snapshots = {b["broker_id"]: b for b in result["brokers"]}
        assert snapshots["paper"]["environment"] == "synthetic"
        assert snapshots["kite"]["environment"] == "live"
        assert snapshots["alpaca"]["environment"] == "paper"
        assert snapshots["kite"]["positions_value_by_currency"] == {"INR": "-2000.30"}
        assert snapshots["alpaca"]["positions_value_by_currency"] == {"USD": "-275.00"}
        assert len(snapshots["kite"]["holdings_separate_view"]) == 1
        assert snapshots["alpaca"]["holdings_separate_view"] == []
        assert (
            snapshots["kite"]["accounts"][0]["holdings_summary"]["market_value"]["value"]
            == "3000.45"
        )
        assert snapshots["alpaca"]["accounts"][0]["holdings_summary"]["holding_count"] == 2
        assert (
            snapshots["alpaca"]["accounts"][0]["holdings_summary"]["day_unrealized_pnl"]["value"]
            == "-1.5"
        )
        assert snapshots["kite"]["positions"][0]["account_id"] == "synthetic-kite-account"

    try:
        asyncio.run(run())
    finally:
        service.close()
