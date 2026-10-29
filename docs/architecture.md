# Architecture

`models.py` defines immutable validated models using decimal monetary values. Canonical symbols
are `NSE:RELIANCE`, `BSE:RELIANCE`, or `US:AAPL`. The US prefix identifies a market, not a listing
venue. `instruments.py` loads an optional user-maintained JSON registry with explicit local IDs,
symbols, currencies, optional US listing venues, NSE/BSE venues and broker symbol mappings. The
default registry is empty. Unknown symbols retain null IDs. Duplicate/ambiguous IDs and conflicting
market/currency/mapping labels fail validation. NSE and BSE listings remain distinct; no security
equivalence, symbol-change history, corporate-action linking or derivatives registry is implied.

`PositionPerformance` preserves optional broker snapshot prices and P&L. Kite holdings map P&L
and daily per-unit price changes; Kite net-position P&L is not treated as unrealized holding P&L.
Alpaca positions preserve unrealized and daily unrealized P&L, converting fractional daily price
change into percentage points. Missing fields remain unknown, and price timestamps are not
invented. `portfolio.py` summarizes holding records per account/currency with complete versus
partial sums. Alpaca aliases are counted once; Kite holdings remain separate from net positions.
The holdings-only service/CLI/MCP path makes no quote, historical or order requests. See the
[field definitions](holdings-performance.md). None of these snapshot metrics is NAV or historical
personal portfolio return.

`adapters/base.py` describes the broker read interface. Each adapter advertises capabilities;
the service rejects unsupported operations. History tools are registered only when a connected
adapter offers history. External adapters use a shared GET-only HTTP helper with fixed broker
hosts, timeouts, sanitized transport errors and no order-write methods. Broker response schemas
are mapped into normalized models. The paper adapter supplies fixed, clearly labelled fixtures.

`service.py` constructs adapters from local configuration and reloads policy before decisions.
Flat credential fields define the default Kite/Alpaca connections. `broker_connections` adds named
credential sets, including multiple accounts at one broker. Adapter dictionary keys are connection
IDs; adapter IDs and returned broker account IDs are unchanged. Read routing rejects ambiguity and
broker/connection mismatches before requests. Account refs contain broker ID, actual account ID
and environment. `portfolio.py` validates account/currency ownership, retains separate connection
and account snapshots, flags duplicate account identities, and distinguishes partial priced value
from a null full value when pricing is incomplete. Observed times are retrieval times, not proof
of synchronized or fresh broker valuations. No cash, FX, cross-account netting or Kite holdings
reconciliation is implemented. OAuth enrollment and refresh workflows remain unimplemented.

`verification.py` powers the opt-in local `verify-brokers` command. It shares adapter construction
with the service but creates no SQLite state and exposes no new MCP tool. Its report contains
metadata only; raw account responses and schema-validation errors are never printed. It stops
reads on the first failure for each connection without automatic retries, then checks the next.
Alpaca history pagination has cycle detection, a 100-page bound and a 50,000-bar bound.

`demo.py` builds deterministic synthetic portfolio snapshots with the same normalization and
valuation helpers. The CLI demo runs before settings are loaded and creates no state. Its MCP
equivalent is a separately labelled tool; it never inserts accounts into external adapter routing.
Sample instrument metadata is packaged under `data/` and used only by the demo unless explicitly
chosen as a local registry. Workflow rehearsal is not real-user or real-account validation.

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

## Proposed independent execution boundary — not implemented

The [product direction](product-direction.md) calls for a separately protected service between
an agent and broker actions. The agent would submit typed intents without access to broker
credentials, signing keys or policy administration. Human authorization would come through an
independently authenticated channel and bind exact account/environment/instrument/order content,
expiry and policy version. Model-generated claims of consent would not authorize submission.

Future enforcement would recheck permissions and broker state, persist intent and reconcile
broker results. Unknown outcomes would pause the affected submission scope until resolved;
local idempotency alone would not imply exactly-once broker execution. Opaque MCP tool forwarding
would not bypass typed broker mapping or authorization. All supported mutation routes would need
explicit controls, including modifications, cancellations and halt/resume behavior.

This requires an actual isolation/deployment boundary: a process that can read `.env` or edit
local policy/state can bypass today's controls. Current adapters remain GET-only. The target
design is neither an implemented guarantee nor authorization to add broker order methods.
Broker-paper and live execution each require their own separately authorized milestone.
