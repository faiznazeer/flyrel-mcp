# MCP tools in v0.1

| Tool | Scope |
| --- | --- |
| `list_brokers` | One row per connection: `connection_id`, actual `broker_id`/`id`, environment, markets and capabilities; no credentials |
| `get_capabilities` | One connection's supported operations |
| `list_accounts` | Broker-returned account IDs with structured `account_ref`, connection, currency and environment |
| `search_instruments` | Search configured local instrument metadata; optional broker filter; 1–100 results |
| `resolve_instrument` | Resolve a registered local ID or canonical symbol; optionally require an explicit broker mapping |
| `get_quotes` | Up to 50 canonical equity symbols per request, labelled with connection, currency and environment |
| `get_history` | Optional, registered for Kite/Alpaca; labelled 1Min/1Hour/1Day broker bars (Alpaca raw), at most 31 days; Alpaca capped at 100 pages/50,000 bars |
| `get_positions` | Normalized positions with account references; optional Alpaca broker performance; no historical returns |
| `get_holdings` | Account-labelled holdings with optional broker P&L/daily price change; may overlap positions |
| `get_holdings_summary` | Per-account/currency holding counts, value and broker P&L with missing-data flags; accounts/holdings reads only; no NAV/history |
| `get_portfolio_summary` | Optional `connection_ids`; separate position values and account holding summaries, missing-data flags and duplicate-account warnings; no consolidated NAV |
| `get_demo_portfolio` | Fixed synthetic four-account walkthrough and sample instrument metadata; no external reads |
| `get_policy` | Local sandbox limits and halt state |
| `propose_order` | Validate a BUY limit request; issue expiring sandbox token |
| `confirm_order` | Persist an open local order; no external execution |
| `list_orders` | Account/connection-labelled local orders, Alpaca open snapshot, or Kite day book |
| `get_order_status` | Local sandbox order only |
| `cancel_order` | Local sandbox order only |
| `kill_switch` | Block new sandbox orders persistently |

Broker read tools accept optional `connection_id`. It is required when the requested broker has
multiple configured connections; a connection for another broker is rejected. Market-data reads
identify the connection/environment but do not invent a broker account association. Account refs
are structured `(broker_id, account_id, environment)` identities. Connection aliases do not replace
actual broker IDs. Mutation tools continue to address only the single local `paper` sandbox.

Registry search/resolution never makes a broker request. Without a configured registry search
returns no entries; unknown instruments remain readable with null `instrument_id`. Instrument
metadata has its own source/synthetic labels, separate from quote or position provenance.

Local CLI: `set-policy FILE`, `halt`, `resume`, `check`, `verify-brokers`, `demo-portfolio`, `serve`,
and `holdings-summary --broker BROKER [--connection ID]`.
Policy modification/resume and broker verification remain CLI-only operations.
`check` makes no broker requests. `verify-brokers` explicitly reads external accounts, positions,
holdings, orders and sample quotes, with optional daily history, and prints metadata only. It
does not record snapshots or imply broker-UI reconciliation. See [validation](broker-validation.md).
It checks every configured connection for selected brokers; `--connection ID` narrows the selection.
`demo-portfolio` prints fixed synthetic examples without loading settings or writing state.
There is no agent-accessible `set_policy` or remote execution API.

`holdings-summary` prints actual holding details, unlike metadata-only `verify-brokers`.
The [holdings performance guide](holdings-performance.md) defines each field and broker mapping.
Kite daily price change is not daily monetary P&L; its populated `day_unrealized_pnl` metric is
unknown. Alpaca daily unrealized P&L is broker-reported. Neither is historical account return.

The [product direction](product-direction.md) prioritizes independently enforced permissions and
authenticated approval as a future design. Credential isolation, agent-resistant policy controls,
broker reconciliation and external execution are not implemented by this inventory. Agreement on
that direction does not authorize broker order methods; broker-paper and live execution each
require a separate milestone.

Historical portfolio returns, broker-master discovery and strategy backtesting remain future
work, prioritized by workflow evidence. No `run_backtest`, `compare_backtests`, external trading
or compliance-enforcement tool is registered. Unsupported features do not appear as working tools.
