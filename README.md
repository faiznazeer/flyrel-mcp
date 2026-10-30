# Flyrel MCP

A self-hosted Python foundation for working with multiple brokers through one MCP server.
Initial markets: India and US cash equities. Initial adapters: Zerodha Kite and Alpaca.

**Status: early foundation, not a trading product.** External brokers are read-only. All
order mutations stay in a local synthetic sandbox. No live-order implementation or enable-live
flag exists. No broker credentials are needed to run the demo.

## Product direction

Flyrel is experimenting with an independent security, permissions and approval layer for agentic
investing/trading. The customer segment is undecided. Candidates include companies building
trading agents, brokers, quant firms if relevant needs emerge, and individual or multi-account
traders. There is no committed audience order or decision to sell exclusively to companies.

The intended promise is explicitly limited trading permissions with independent approval and
verifiable enforcement. Broker connectivity and portfolio reports support that workflow. The
interface, deployment model, buyer and end user remain discovery questions. Reddit research can
inform user needs; company integration, ownership and purchasing needs require separate evidence.
Flyrel does not promise guaranteed profits, loss-free trading or "100% security".

The current local setup does not provide that independent boundary: agents with shell access can
read credentials and change policy/state. Protected credentials, agent-resistant policy controls,
independent approval and broker execution remain future work. Agreement on product direction
does not authorize external execution or change the read-only adapters.

See the [product decision](docs/product-direction.md), [roadmap](docs/roadmap.md), and
[neutral community research drafts](docs/community-research.md).

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/faiznazeer/flyrel-mcp.git
cd flyrel-mcp
uv sync --locked
uv run flyrel check
uv run flyrel serve
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

For a credential-free multi-account portfolio walkthrough, run `uv run flyrel demo-portfolio`
or call `get_demo_portfolio` from MCP. It shows four invented accounts with explicit synthetic
labels, separate broker holdings, fractional/short positions and an unpriced position. The
fixtures are fixed at January 1, 2026. The CLI demo loads no credentials, connects to no broker
and writes no local state. Follow the [offline walkthrough](docs/workflow-validation.md#offline-walkthrough).

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
endpoint and IEX stock data; `FLYREL_ALPACA_PAPER=false` selects a live **read-only** account
snapshot. It does not enable trading. Automated adapter tests use mocked HTTP. User-authorized
Alpaca paper-account read checks passed on October 29, 2026 for account access, positions,
holdings, open orders and an IEX quote. Kite Personal account/holding/position/day-order reads
also passed that day, and the owner reported that available holding values matched the UI.
Populated Alpaca and Kite position/order mappings, historical data, and private UI checks of the
new performance fields remain pending. See the dated validation record for the exact scope.

Run `uv run flyrel verify-brokers` to explicitly make read-only API checks for both brokers
(or add `--broker kite` / `--broker alpaca`). The report includes status and row counts, omits
account details, and creates no local state. Missing credentials or failed checks return exit
code 1. Optional `--history-start` and `--history-end` add daily-bar checks. Follow the
[broker validation checklist](docs/broker-validation.md) for private broker-UI comparison and
the [workflow validation guide](docs/workflow-validation.md) for the first user sessions.

Multiple accounts at the same broker use named credential connections in
`FLYREL_BROKER_CONNECTIONS`. Read tools accept `connection_id` and require it when a broker has
multiple configured connections. Broker-returned account IDs, broker IDs and environments stay
separate from those local names. See [multiple accounts and local instruments](docs/multi-account.md).

Portfolio snapshots preserve currencies and broker views. The starter does not report consolidated
NAV: it excludes cash and FX conversion, and keeps Kite holdings separate to avoid silently
double-counting delivery positions. Alpaca holdings alias positions. Unsupported non-equity
positions fail explicitly rather than disappearing from a purported complete portfolio.

For a current-holdings review, call `get_holdings_summary` or run:

```bash
uv run flyrel holdings-summary --broker kite
```

This uses account/holding reads only, including on Kite Personal. It shows holding count, market
value and broker-reported unrealized P&L per account/currency, with explicit missing-data flags.
Per-holding daily price changes are distinct from monetary daily P&L: Kite provides the former;
Alpaca also supplies daily unrealized P&L. The existing portfolio summary includes holding metrics
separately from position values. No historical return, account-growth calculation or NAV is
implied. See [holdings performance](docs/holdings-performance.md).

Snapshots now include per-account values and flag duplicate accounts exposed by different
connections. A currency with an unpriced position has a null full position value, alongside an
explicit partial priced value. Neither is consolidated NAV. The optional local instrument
registry assigns user-maintained IDs; unknown symbols stay unregistered rather than receiving
guessed identities. Registry metadata is not a live broker instrument master.

## Local policy and state

Default sandbox allow-list: `US:AAPL`, `NSE:RELIANCE`. Per-order caps: USD 1,000 / INR 100,000.
Open-order aggregate caps: USD 5,000 / INR 500,000. Proposal TTL: 120 seconds. Values are checked
again at confirmation under a SQLite write transaction. Persistent idempotency keys reject
conflicting payloads and make confirmation retries return the existing order within token TTL.

```bash
uv run flyrel set-policy examples/policy.json
uv run flyrel halt
uv run flyrel resume
```

Policy modification and resume are local CLI operations, never MCP tools. The kill switch blocks
new local orders; it does not cancel outstanding orders or affect broker accounts. Both proposal
and confirmation are callable by an agent, so **two calls do not establish human approval**.
A separately authenticated human approval channel is future work before remote execution.

State lives in ignored `.state/`: `flyrel.sqlite3` holds proposals/orders/audit metadata,
alongside optional `policy.json`.
New state directories/files use restrictive permissions. Tokens are stored as hashes. Tool audit
records store action/outcome metadata, not credentials, confirmation tokens, arguments, or account
responses. This is a local diagnostic log, not a tamper-proof compliance or replay archive.
Protect local files: any agent with shell access can change local policy and state.

## Development

The minimal public waitlist page lives in [`website/`](website/README.md). It includes email
capture and a searchable, regional broker multi-select, backed by a separate Cloudflare Worker
and D1 database. Broker selections measure interest; they do not expand implemented integrations
or authorize broker execution. See its README for local development, checks and deployment.

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
