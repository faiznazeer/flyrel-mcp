# Roadmap

The product hypothesis is that consistent data, cross-broker risk and independently enforced
controls can add value beyond a broker's own connector. A thin wrapper alone does not establish
that advantage. Validate workflows with users who hold accounts at more than one broker.

## Foundation delivered

- Normalized cash-equity models, capability discovery and stdio MCP server.
- Kite and Alpaca GET-only adapters; zero-credential synthetic local sandbox.
- Durable proposal/confirmation flow, TTL, idempotency, policy limits and halt switch.
- Metadata audit log, tests, packaging and CI.
- Explicit connection/account identities, multiple credential connections per broker, a local
  instrument registry and a credential-free multi-account workflow demo.

## Next milestones

The first selected workflow is cross-broker portfolio review. The [session guide](workflow-validation.md)
and [broker validation checklist](broker-validation.md) are prepared, with an opt-in read-only
verification CLI and synthetic contract tests. Alpaca paper-account API checks passed on
October 29, 2026. User sessions, Kite checks, populated-portfolio mappings, history and private
broker-UI comparisons remain pending; neither milestone is complete.

1. Validate read adapters against user-authorized broker accounts; add recorded, sanitized
   fixtures and contract tests for corporate actions, auth expiry, pagination and rate limits.
2. Extend the implemented local registry and multi-account identities with broker-master metadata
   and a reconciled portfolio with explicit FX timestamps. Current per-account snapshots flag
   duplicates and missing prices; holdings reconciliation, FX and consolidated exposure remain pending.
3. Add broker-independent historical datasets and deterministic backtesting with fees,
   slippage, corporate actions, metrics and out-of-sample evaluation. Avoid arbitrary agent code.
4. Expand the local simulator with fills, cash, holdings, realized P&L, daily loss limits,
   exchange calendars and risk limits. Add replayable event data with redaction controls.
5. Add independently authenticated human approval and broker-paper execution. Approval must
   bind exact order content, expiry, account and policy version. Agents must not self-approve.
6. Assess Interactive Brokers and Upstox adapters using current first-party API documents.
   SDK/MCP availability is a separate question from whether an adapter can be built.
7. Review each market/broker/segment's legal and operational requirements before any live
   execution work. Hosted multi-user service and strategy distribution require a separate review.

No target date or automatic live-trading switch is promised by this roadmap.
