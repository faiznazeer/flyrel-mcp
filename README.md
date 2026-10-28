# BrokerBridge MCP

A self-hosted Python foundation for working with multiple brokers through one MCP server.
Initial markets: India and US cash equities. Initial adapters: Zerodha Kite and Alpaca.

**Status: early foundation, not a trading product.** External brokers are read-only. All
order mutations stay in a local synthetic sandbox. No live-order implementation or enable-live
flag exists. No broker credentials are needed to run the demo.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/faiznazeer/brokerbridge-mcp.git
cd brokerbridge-mcp
uv sync --locked
uv run brokerbridge check
uv run brokerbridge serve
```

`serve` speaks MCP over stdio and waits for a client. Application output must not be written
to stdout while serving. See [MCP client configuration](examples/mcp.json); replace the example
absolute project path with your checkout. The `uv --directory` argument also ensures the correct
`.env` and state directory are used when the client starts elsewhere.

Try these tools from your MCP client:

1. `list_brokers` and `get_policy`.
2. `get_quotes` with `{"broker_id":"paper","symbols":["US:AAPL","NSE:RELIANCE"]}`.
3. `propose_order` with the request in [examples/paper-order.json](examples/paper-order.json).
4. `confirm_order` with the returned token, then `list_orders`.
5. `cancel_order` with that order ID, or `kill_switch` to block new sandbox orders.

The demo quotes are **fixed synthetic fixtures dated January 1, 2026**, not current prices.
Paper orders remain open until cancelled; they never fill, change positions, reserve real cash,
or reach an external broker. Only whole-share BUY limit orders are supported. This is an order
lifecycle sandbox, not a realistic execution, P&L, or backtesting simulator.

## Optional broker connections

Copy `.env.example` to `.env` and configure your own keys locally. Never put keys in chat,
issues, examples, or commits. The server reads `.env` but does not create tokens or perform login.

| Adapter | Credentials | Implemented access | Order execution |
| --- | --- | --- | --- |
| `paper` | None | Synthetic accounts/quotes, empty positions/holdings, persisted local orders | Local sandbox only |
| `kite` | API key + current access token | Profile, quotes, raw history, cash-equity positions/holdings, day order book | None |
| `alpaca` | Key + secret | Account, quotes, raw history, US equity positions, open orders | None |

Kite tokens must be obtained/renewed through the broker's supported login flow. Market data and
historical access depend on broker entitlements. Alpaca defaults to the broker's paper account
endpoint and IEX stock data; `BROKERBRIDGE_ALPACA_PAPER=false` selects a live **read-only** account
snapshot. It does not enable trading. External adapter tests use mocked HTTP; no real account
has been connected or verified for this initial commit.

Portfolio snapshots preserve currencies and broker views. The starter does not report consolidated
NAV: it excludes cash and FX conversion, and keeps Kite holdings separate to avoid silently
double-counting delivery positions. Alpaca holdings alias positions. Unsupported non-equity
positions fail explicitly rather than disappearing from a purported complete portfolio.

## Local policy and state

Default sandbox allow-list: `US:AAPL`, `NSE:RELIANCE`. Per-order caps: USD 1,000 / INR 100,000.
Open-order aggregate caps: USD 5,000 / INR 500,000. Proposal TTL: 120 seconds. Values are checked
again at confirmation under a SQLite write transaction. Persistent idempotency keys reject
conflicting payloads and make confirmation retries return the existing order within token TTL.

```bash
uv run brokerbridge set-policy examples/policy.json
uv run brokerbridge halt
uv run brokerbridge resume
```

Policy modification and resume are local CLI operations, never MCP tools. The kill switch blocks
new local orders; it does not cancel outstanding orders or affect broker accounts. Both proposal
and confirmation are callable by an agent, so **two calls do not establish human approval**.
A separately authenticated human approval channel is future work before remote execution.

State lives in ignored `.state/`: SQLite proposals/orders/audit metadata and optional `policy.json`.
New state directories/files use restrictive permissions. Tokens are stored as hashes. Tool audit
records store action/outcome metadata, not credentials, confirmation tokens, arguments, or account
responses. This is a local diagnostic log, not a tamper-proof compliance or replay archive.
Protect local files: any agent with shell access can change local policy and state.

## Development

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
```

CI runs lint, format checks, tests (including a real MCP stdio client/server round trip), and
package builds on Python 3.12 and 3.13. See [architecture](docs/architecture.md),
[tool inventory](docs/tools.md), [roadmap](docs/roadmap.md), and
[regulatory research](docs/regulatory-notes.md).

## Scope and regulation

Self-hosting and bring-your-own keys are deployment choices, not regulatory exemptions. There is
no compliance certification or automated India/US compliance engine in this release. Review the
dated primary sources in the regulatory notes and your broker's requirements before expanding to
order routing, distributing strategies, or operating a hosted service.

MIT licensed. Not affiliated with Zerodha, Alpaca, or any exchange. This software does not provide
investment advice.
