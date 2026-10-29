# Read-only broker validation

Prepared October 29, 2026 for the cross-broker portfolio workflow. User-authorized Alpaca
paper-account API checks passed at 16:27 UTC on that date: account access, positions, holdings,
open orders and one IEX quote. Credentials were used temporarily for verification. No account
responses or credentials were saved in the project. Populated-portfolio mapping, historical data,
Kite account checks and private broker-UI reconciliation remain unverified. Committed fixtures
remain synthetic contract examples, not account recordings.

## Run connectivity and mapping checks

Configure credentials privately using the existing `.env.example` names. For an actual portfolio
comparison, choose the Alpaca account environment deliberately: the default is broker-paper;
`FLYREL_ALPACA_PAPER=false` selects live account reads only. Kite reads are labelled live. API keys
can have broader broker permissions, but Flyrel uses only GET requests and implements no external
order mutation. Do not place credentials in command arguments, commits or ordinary chat.

```bash
uv run flyrel verify-brokers
uv run flyrel verify-brokers --broker kite
uv run flyrel verify-brokers --broker alpaca
uv run flyrel verify-brokers --broker alpaca --connection us-core
uv run flyrel verify-brokers --history-start 2026-10-19T00:00:00+00:00 --history-end 2026-10-23T00:00:00+00:00
```

The command reads accounts, positions, holdings, orders, and one sample quote (`NSE:RELIANCE` or
`US:AAPL`). Optional timezone-aware history bounds add daily bars, at most 31 days. Choose dates
appropriate to the broker's data entitlement. No history request is sent by default.

For named accounts, configure [multiple connections](multi-account.md) privately. A selected broker
checks all its configured connections, or use repeated `--connection ID` arguments to select them.
The JSON report includes connection, broker, environment, currency, feed, check time, status and row counts.
It omits account IDs, balances, security positions, order details and raw responses, and writes
no state or fixture files. Exit code 0 means every selected API check passed; 1 means a broker is
missing, misconfigured or failed; invalid arguments use exit code 2. A failure stops further reads
for that connection, while remaining connections are still checked. No automatic retries or token renewal
are attempted. An empty collection verifies connectivity and shape only, not populated mappings.

`check` remains an offline configuration inspection. `verify-brokers` is an opt-in local CLI,
not an MCP tool. A passing report does not verify economic correctness or broker UI parity.

## Compare with broker UI privately

- Confirm account identity, connection, environment and currency before comparing any records. A broker-paper
  account is not the local synthetic sandbox.
- Compare quantities, average prices, signed market values, product labels and quote times for
  representative equity records. Include fractional/short positions if naturally present; do
  not create trades to generate test cases. A missing Kite quote timestamp stays unknown.
- Check Kite delivery holdings, unsettled quantity and net positions as distinct views. Check
  that Alpaca holdings alias positions. Neither comparison establishes combined NAV.
- Compare Kite's day order book with that view in Kite, and Alpaca's open orders with that view
  in Alpaca. A full 500-row Alpaca order response fails as potentially incomplete.
- Check historical timestamps and known corporate-action windows against broker-provided bars.
  Flyrel applies no local adjustment. A split-like synthetic example tests preservation of input,
  not the broker's real adjustment policy or corporate-action accounting.
- Record unexplained differences and missing entitlements. Unsupported segments must fail
  explicitly. Resolve discrepancies before declaring an adapter verified.

## Contract examples and future recorded fixtures

`tests/fixtures/brokers/*.json` contain invented account/order identifiers and invented market
values, with explicit synthetic provenance. Tests cover both Alpaca environments, fractional and
short positions, Kite unsettled holdings and timezone conversion, raw Alpaca requests, paginated
history, auth/access failures, rate limits and incomplete order snapshots. Pagination rejects
repeated tokens, more than 100 pages or more than 50,000 bars; no partial success is returned.

For future authorized recordings, work only in ignored `.state/`; do not enable HTTP debug logs.
Prefer minimal hand-authored schema examples. If a real response is needed to reproduce a bug,
keep the original private, then construct a minimal synthetic example outside the recording.
Replace identifiers, names, balances, quantities, prices, timestamps and opaque pagination tokens;
remove headers, login/session fields, URLs with credentials and all unrelated response fields.
Review it manually before committing. Record origin type, source documentation date, scenario and
expected mapping; never describe a synthetic example as a captured production response. There is
no automatic recorder or sanitizer in this release.

## Dated contract references

Checked against first-party documentation October 29, 2026:

- [Kite errors](https://kite.trade/docs/connect/v3/exceptions/): expired sessions use 403 and rate
  limiting uses 429. Both stop the verification run for that broker.
- [Kite portfolio](https://kite.trade/docs/connect/v3/portfolio/): separate holdings and net/day
  position collections; current mappings use holdings and net positions.
- [Kite history](https://kite.trade/docs/connect/v3/historical/): instrument-token lookup and
  timestamped candles. No additional corporate-action normalization is implemented locally.
- [Alpaca single-symbol bars](https://docs.alpaca.markets/us/reference/stockbarsingle-1): follow
  `next_page_token` even on short pages; Flyrel explicitly requests `adjustment=raw` and its
  configured feed. The documentation distinguishes invalid authentication, forbidden access,
  and throttling; the report groups 401/403 as `auth_or_access` without guessing the cause.

## Milestone completion record

- [x] Workflow protocol and pass/fail criteria prepared.
- [x] Metadata-only read verification command and synthetic contract coverage implemented.
- [ ] Authorized Kite account checks and private UI comparison completed.
- [x] Authorized Alpaca paper-account API connectivity/normalization checks completed October 29, 2026.
- [ ] Alpaca populated-portfolio mappings, history and private UI comparison completed.
- [ ] Corporate-action/entitlement edge cases checked against actual broker data.
- [ ] Any necessary sanitized reproductions reviewed and added with honest provenance.
- [ ] User sessions completed and a continue/change/stop decision recorded.

Read-only API access, user validation and later execution authorization are separate milestones.
