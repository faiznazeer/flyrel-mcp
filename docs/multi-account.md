# Multiple accounts and local instrument identities

These features can be developed and rehearsed without credentials. Real broker connections still
require their own authorized keys, and account correctness remains unverified until the private
broker checks are completed. External adapters expose only GET requests.

## Connections and accounts

A connection is a locally named credential set. An account identity is the broker-returned
`(broker_id, account_id, environment)` tuple, exposed as `account_ref`. A connection name does not
replace an account ID or change the broker identity. Two connections may expose the same account;
the portfolio report flags that duplication. The same account ID string at different brokers or
in paper/live environments represents different identities.

The existing flat `.env` variables configure default `kite` and `alpaca` connections. Additional
credential sets go in the JSON array `FLYREL_BROKER_CONNECTIONS` in your ignored local `.env`.
The following is a format example with intentionally nonworking synthetic placeholders:

```dotenv
FLYREL_BROKER_CONNECTIONS='[
  {
    "connection_id": "us-core",
    "broker_id": "alpaca",
    "environment": "paper",
    "api_key": "SYNTHETIC_EXAMPLE_NOT_A_KEY",
    "secret_key": "SYNTHETIC_EXAMPLE_NOT_A_SECRET",
    "feed": "iex"
  },
  {
    "connection_id": "in-core",
    "broker_id": "kite",
    "environment": "live",
    "api_key": "SYNTHETIC_EXAMPLE_NOT_A_KEY",
    "access_token": "SYNTHETIC_EXAMPLE_NOT_A_TOKEN"
  }
]'
```

Keep actual values private; do not paste them into ordinary chat or commit the resulting `.env`.
Each named Kite connection requires a key and access token and uses environment `live`. Named
Alpaca connections require a key, secret and explicit `paper` or `live` environment. Named entries
do not inherit credentials from the flat variables. Names must be unique lowercase identifiers
starting with a letter, using letters, digits, underscores or hyphens, at most 40 characters.
`paper`, `kite` and `alpaca` are reserved. Invalid combinations fail before requests.

Flat and named connections can coexist. Leave the flat broker credentials blank if you intend
to use only named connections; otherwise both connections will be registered. Changing the
Alpaca environment selects an account read endpoint and never enables order execution.

Discover names with `list_brokers`. If a broker has multiple connections, specify one in each
broker read, for example:

```json
{"broker_id": "alpaca", "connection_id": "us-core"}
```

Use that input for `list_accounts`, `get_positions`, `get_holdings` or `list_orders`. Quotes also
require `symbols`; history requires its usual symbol, interval and bounds. An omitted selection
is accepted only for a broker with exactly one configured connection. A connection associated
with a different broker is rejected, with no fallback to another account.

`get_portfolio_summary` accepts optional `connection_ids`, such as `["us-core", "in-core"]`.
Its existing `brokers` collection now contains one snapshot per selected connection. Snapshots
retain separate accounts and currencies; `duplicate_accounts` flags repeated account identities.
Only per-connection/account values are returned. Nothing sums accounts, currencies or environments
into a consolidated exposure or NAV.

For a currency with any unpriced position, `positions_value_by_currency` is null for that currency
and `positions_value_complete` is false. `priced_positions_value_by_currency` is explicitly the
partial sum of records that have broker-supplied values. All positions remain visible. Cash is
excluded. Kite holdings stay separate; Alpaca holdings alias positions and are not added again.
Observation timestamps describe retrieval, not synchronized pricing or a guarantee of freshness.

## Local instrument catalog

Set `FLYREL_INSTRUMENT_REGISTRY_FILE` to a locally maintained JSON catalog. A minimal format example:

```json
{
  "instruments": [
    {
      "instrument_id": "my-local-aapl-id",
      "symbol": "US:AAPL",
      "name": "User-maintained AAPL record",
      "currency": "USD",
      "asset_class": "equity",
      "venue": null,
      "broker_symbols": {"alpaca": "AAPL"},
      "source": "local",
      "synthetic": false
    }
  ]
}
```

Choose local IDs deliberately and retain them when updating metadata. They are not ISINs,
exchange-issued IDs or proof that two listings represent the same security. NSE and BSE records
require the corresponding venue and remain separate. `US:` identifies a market; a US listing
venue can be entered explicitly, but none is inferred. Current broker symbol mappings match the
adapters' canonical cash-equity conventions; broker instrument tokens are not cached here.
An entry or mapping does not establish current broker availability, entitlement or tradeability.

The catalog is validated at service startup; duplicate references and conflicting currency,
market or synthetic labels fail closed. `search_instruments` searches only that local file.
`resolve_instrument` accepts a registered ID or exact canonical symbol and can require a broker
mapping. Without a catalog, search is empty and reads still work with null `instrument_id`.
Unknown identities are not fabricated. Metadata source/synthetic labels are returned separately
from quote/position data labels; a synthetic catalog entry never turns broker values into a
verified instrument identity.

For an entirely synthetic catalog in this checkout, explicitly choose
`src/flyrel/data/demo-instruments.json`. This is also the catalog included in `demo-portfolio`.
The demo does not change the service's configured registry. Broker-master synchronization,
symbol lifecycles, corporate-action linking, cross-listing reconciliation and FX remain future work.
