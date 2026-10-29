# Read-only holdings performance

Use `get_holdings_summary` from an MCP client:

```json
{"broker_id":"kite"}
```

Or run the local CLI:

```bash
uv run flyrel holdings-summary --broker kite
uv run flyrel holdings-summary --broker alpaca --connection us-core
```

Select `connection_id` (CLI: `--connection`) when a broker has multiple connections. The
summary reads only accounts and holdings, not quote, history or order endpoints. It works with
Kite Personal account access. External adapters remain GET-only. The CLI prints actual holding
details to stdout; unlike `verify-brokers`, its output is not a metadata-only diagnostic report.
No account responses are written to state or audit records by the summary command.

## Fields and meaning

The response retains broker, connection, account reference, environment, currency, instrument
metadata and synthetic labels. `accounts[].holdings_summary` contains:

- `holding_count`: the number of broker holding records, not a deduplicated count of securities.
- `market_value`: signed value of those holdings in the account's currency.
- `unrealized_pnl`: the sum of broker-reported current-holding unrealized P&L.
- `day_unrealized_pnl`: the sum of broker-reported daily unrealized monetary P&L, when available.

Each monetary metric has `value`, `known_value`, `complete` and `missing_count`. If any record
lacks the metric, `value` is null, `complete` is false, and `known_value` is explicitly a partial
sum. A reported zero is retained. An empty account has count zero and zero sums over its empty
holding collection; these are not an account balance or NAV. Accounts and currencies are never
combined into one total.

Each holding has optional `performance` fields: `source`, `last_price`, `previous_close`,
`unrealized_pnl`, `day_unrealized_pnl`, `day_price_change`, `day_price_change_percent` and
`price_timestamp`. Percentage values are percentage points: `1` means 1%, not 100%.
Missing fields remain null. No P&L is inferred from average cost or market value. Nonfinite
broker values fail validation instead of entering a total.

`observed_at` is retrieval time. Neither broker position/holding response supplies a price
timestamp for the fields mapped here, so `price_timestamp` remains null; retrieval does not
prove that prices are current or synchronized. `source` names the broker response mapping,
not a separate market-data entitlement or certification of synthetic test examples.

## Broker mappings

Mappings checked against primary sources October 29, 2026:

- [Kite holdings](https://kite.trade/docs/connect/v3/portfolio/): `pnl` becomes
  `unrealized_pnl`; `last_price` and `close_price` remain per-unit prices; `day_change` and
  `day_change_percentage` become per-unit daily price change and percentage change. Kite does
  not provide daily monetary holding P&L here: `day_unrealized_pnl` stays null for populated
  Kite holdings. Do not multiply day price change by current quantity and call it actual daily
  trading P&L: quantities may have changed during the day. Kite net-position `pnl` is deliberately
  not mapped as holding unrealized P&L because it can include realized results.
- [Alpaca position fields](https://alpaca.markets/sdks/python/api_reference/trading/models.html#position)
  and the [official position object](https://github.com/alpacahq/alpaca-docs/blob/master/content/api-references/broker-api/trading/positions.md):
  `unrealized_pl` and `unrealized_intraday_pl` become their respective monetary fields.
  `current_price`/`lastday_price` remain per-unit prices. `change_today` is a fraction and is
  multiplied by 100 for `day_price_change_percent`. Short-position P&L signs are preserved;
  an increasing price can coexist with a daily unrealized loss. Alpaca holdings alias positions
  and are counted once, including in the existing portfolio summary.

Kite delivery holdings remain separate from net positions. The new summary never adds those
views together or reconciles unsettled quantities, collateral or corporate actions beyond the
existing adapter mapping. `get_portfolio_summary` now includes the same holding metrics in each
account, alongside its existing position-only values. These are separate metrics, not additive.

## Scope

This is a snapshot of current holdings. It excludes realized gains, distributions, fees, cash,
cash flows and FX. It is not lifetime total return, 1-month/3-month portfolio return, account
growth, or consolidated NAV. Historical personal portfolio performance requires valuation and
cash-flow/transaction history and remains future work. A market-price history subscription alone
does not supply that account history.

Tests use invented contract examples, including unsettled holdings, fractional and short
positions, missing values and signed P&L. An empty broker-paper account verifies the empty case,
not real populated-account economic correctness.
