# Roadmap

Product focus agreed October 29, 2026 and customer assumptions revised October 30, 2026:
try an independent security, permissions and approval layer for agentic trading. The customer
segment is undecided, with no expansion order. Companies building trading agents, brokers,
quant firms with relevant needs, developers and individual/multi-account traders are discovery
candidates. See the [product decision](product-direction.md) for the hypothesis and target boundary.

This is an experiment, not a validated business or a promise of secure/loss-free trading.
Agreement on this direction does not authorize external execution implementation. All external
adapters remain read-only until a separate, explicitly authorized execution milestone.

## Foundation delivered

- Normalized cash-equity models, capability discovery and stdio MCP server.
- Kite and Alpaca GET-only adapters; zero-credential synthetic local sandbox.
- Durable synthetic proposal/confirmation flow, TTL, idempotency, local policy limits and halt.
- Metadata audit log, tests, packaging and CI.
- Explicit connection/account identities, multiple credential connections per broker, a local
  instrument registry and a credential-free multi-account workflow demo.
- Per-account current-holding counts, value, broker P&L and daily-change fields, with explicit
  missing-data semantics and a holdings-only CLI/MCP path.

These are useful building blocks, not an agent-resistant security boundary or a realistic
execution simulator. Current local credentials/policy/state are accessible to agents with shell
access. Local proposal/confirmation tools do not establish independent human approval.

## Next priorities and gates

1. **Discover actual tasks and adoption barriers.** Use the [research drafts](community-research.md)
   and neutral interviews with current, former and non-users, including organizational builders
   and operators where possible. Separate user, integration owner, approver and budget holder.
   Look for recurring concrete tasks, workarounds and decisions; distinguish spontaneous concerns
   from prompted concept feedback.
   Investigate usefulness, setup, data quality, cost and trust in an intermediary alongside safety.
   Reddit feedback is exploratory; it does not establish company demand or procurement intent.
   No Reddit outreach, measured adoption or multi-user pilot is completed yet.
2. **Select an initial pilot segment using evidence.** Compare problem severity, existing
   workarounds, enforcement feasibility, integration costs, decision authority and willingness to
   run a bounded pilot. There is no prescribed retail-to-team-to-developer sequence. Multi-account
   controls, developer interfaces, organizational governance and hosted operation follow actual
   requirements rather than an assumed buyer. A small single-account prototype is a technical
   scope choice, not a retail-market commitment. Portable synthetic boundary tests can proceed
   while customer discovery remains open.
3. **Specify and rehearse the independent boundary without broker writes.** Define protected
   credential/policy administration, typed order intents, independently authenticated exact-order
   approval, permissions, expiry, rechecks and a durable execution/reconciliation state machine.
   Exercise bypass attempts, tampering, retries, concurrency and unknown broker outcomes using
   synthetic inputs. Record what each test establishes and its assumptions. These are design
   and test milestones; existing local sandbox controls do not implement this boundary.
4. **Consider a separately authorized broker-paper execution milestone.** Start with one broker,
   cash equities, limit orders and explicit per-order approval. Implement only after authorization
   and prerequisites. Validate fills, partial fills, cancellations, restarts, timeout ambiguity,
   risk accounting and authenticated approval without claiming exactly-once external execution.
5. **Validate repeated use and control comprehension.** Compare a participant's existing workflow
   with a consented bounded prototype. Measure completion, time, friction, understanding and
   voluntary repeat use. Test whether Flyrel changes their actual choice, including whether they
   would prefer manual execution or broker-native controls. A positive interview is not demand.
6. **Evaluate live execution separately.** Refresh each applicable market/broker/segment's
   operational and legal requirements and review the security/recovery evidence before any live
   execution work. There is no enable-live switch or automatic promotion from broker-paper.

## Supporting portfolio and broker validation

Read correctness remains necessary for useful reviews and future policy decisions. Continue
fixing account/instrument identity, missing prices, stale inputs and broker mappings as needed.
Kite holdings remain separate from net positions; Alpaca holdings alias positions. Reconciliation,
FX timestamps and consolidated exposure are not implemented, and no NAV is fabricated.

Alpaca paper-account and Kite Personal account reads passed on October 29, 2026. The owner
reported that available Kite holding values matched the UI. The owner walkthrough found a
current-holding/daily-performance summary useful and requested actual historical portfolio returns.
UI validation of the newly exposed performance fields, populated Alpaca mappings, populated Kite
position/order mappings, history, baseline timing and the multi-user pilot remain pending.
See the [broker record](broker-validation.md) and [portfolio walkthrough](workflow-validation.md).

## Deferred until the selected workflow needs them

- Historical personal portfolio performance and account growth remain a recorded user need.
  They require dated valuations and cash-flow/transaction context, including distributions,
  fees and corporate actions. Snapshot P&L is not historical account return.
- Broad reporting, tax reports and a general strategy-research platform are not the first product.
- Backtesting remains distinct from personal portfolio performance. If strategy users require it,
  prefer reproducible rules/data, explicit costs and assumptions and an established engine where
  appropriate. Do not execute arbitrary agent-generated code with broker credentials.
- Rich local fills/cash/P&L simulation, broker-master synchronization and more broker adapters
  follow demonstrated workflow needs; assess new adapters against current primary documentation.

No target date, universal compliance engine, guaranteed profit, maximum-loss guarantee or
blanket "100% secure" claim is promised. Maintain a clear distinction between plans, tested
invariants and implemented enforcement.
