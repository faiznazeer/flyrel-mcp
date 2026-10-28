# Architecture

`models.py` defines immutable validated models using decimal monetary values. Canonical symbols
are `NSE:RELIANCE`, `BSE:RELIANCE`, or `US:AAPL`. The US prefix identifies a market, not a listing
venue. This starter supports cash equities; identifiers for derivatives, corporate actions,
dual listings and delisted instruments need a richer instrument registry later.

`adapters/base.py` describes the broker read interface. Each adapter advertises capabilities;
the service rejects unsupported operations. History tools are registered only when a connected
adapter offers history. External adapters use a shared GET-only HTTP helper with fixed broker
hosts, timeouts, sanitized transport errors and no order-write methods. Broker response schemas
are mapped into normalized models. The paper adapter supplies fixed, clearly labelled fixtures.

`service.py` constructs adapters from local configuration and reloads policy before decisions.
There is one credential set per broker in this version. Multiple accounts at the same broker,
OAuth enrollment, refresh workflows, and account-level routing are not implemented.

`store.py` persists local sandbox proposals, order results, halt state and audit metadata in
SQLite. Confirmation validates token hash and TTL, checks an idempotency key, rechecks current
policy, sums outstanding order notional in the relevant currency, and creates one open synthetic
order atomically. Cancellation releases that synthetic outstanding notional. No fills, leverage,
cash accounting or market-hour enforcement are modelled.

`server.py` exposes stdio MCP tools using the official MCP Python SDK's supported v1 maintenance API. Mutation
tools can address only the local `paper` broker. The wrapper records started/succeeded/failed
metadata without arguments. SDK input validation occurs before invocation, so rejected protocol
inputs are not an exhaustive audit trail. External adapters are closed when the server exits.

Policy limits are sandbox controls, not a compliance engine. A real live execution design needs
independent approval authentication, exchange-aware instrument identity, account routing, broker
reconciliation, risk checks, order state transitions, rate limits and credential lifecycle support.
