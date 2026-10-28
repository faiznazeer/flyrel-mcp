# MCP tools in v0.1

| Tool | Scope |
| --- | --- |
| `list_brokers` | Configured connections, market and capability discovery |
| `get_capabilities` | One broker's supported operations |
| `list_accounts` | One broker's accounts; environment explicitly labelled |
| `get_quotes` | Up to 50 canonical equity symbols per request |
| `get_history` | Optional, registered for Kite/Alpaca; 1Min/1Hour/1Day, raw bars, at most 31 days |
| `get_positions` | Broker-specific normalized positions |
| `get_holdings` | Separate broker view; may overlap positions |
| `get_portfolio_summary` | Position snapshots per broker and currency; explicitly incomplete NAV |
| `get_policy` | Local sandbox limits and halt state |
| `propose_order` | Validate a BUY limit request; issue expiring sandbox token |
| `confirm_order` | Persist an open local order; no external execution |
| `list_orders` | All local orders, Alpaca open snapshot, or Kite day book |
| `get_order_status` | Local sandbox order only |
| `cancel_order` | Local sandbox order only |
| `kill_switch` | Block new sandbox orders persistently |

Local CLI only: `set-policy FILE`, `halt`, `resume`, `check`, `serve`.
There is no agent-accessible `set_policy` or remote execution API.

Planned rather than stubbed: instrument search, backtest strategy registry, `run_backtest`,
`compare_backtests`, independently approved broker-paper execution, live order routing,
and market-specific compliance services. Unsupported features do not appear as working tools.
