import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_round_trip_without_credentials(tmp_path):
    async def run():
        env = {
            k: v for k, v in os.environ.items() if not k.startswith(("FLYREL_", "BROKERBRIDGE_"))
        }
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
            command=sys.executable, args=["-m", "flyrel.cli", "serve"], env=env
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "Flyrel"
                tools = {t.name for t in (await session.list_tools()).tools}
                assert {"propose_order", "confirm_order", "get_quotes", "kill_switch"} <= tools
                assert "set_policy" not in tools and "get_history" not in tools
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
