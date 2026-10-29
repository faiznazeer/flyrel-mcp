# Product direction: independent permissions for investing agents

Decision: try this product hypothesis, agreed October 29, 2026. This is a direction for research
and development, not a claim of validated demand or authorization to implement broker execution.
External adapters remain read-only until a separately, explicitly authorized execution milestone.

## Intended customer and promise

Serve these audiences in order:

1. Individual investors/traders using general-purpose assistants in supported MCP clients.
2. The same kind of user managing multiple accounts or brokers.
3. Developers building investing agents who want to reuse the integration and enforcement service.

A single trader with several accounts is an extension of the first customer. An organization
operating accounts for multiple people is a different expansion: roles, organizational boundaries,
account authority, operations and market/broker requirements need separate discovery.

The intended promise is: **give an AI assistant explicitly limited trading permissions, with
independent approval and verifiable enforcement.** The user can keep their preferred assistant;
Flyrel supplies portfolio context and, eventually, a controlled path to broker actions.

The agent proposes; a separately protected service decides whether a request is permitted. The
model's confidence or assertion that the user approved must never substitute for authorization.
Reports provide useful account context and a way to learn whether users return. Extensive
reporting, historical portfolio analytics and a general backtesting engine are supporting work,
not prerequisites for testing this central hypothesis.

## What remains a hypothesis

- Some people want to delegate investing tasks to general-purpose agents but stop because they
  cannot adequately constrain or verify actions. Fear is a possible barrier, not an established
  explanation of non-adoption. There is no measured "99% reliability" figure for this product.
- A separate enforcement/approval service could change actual willingness to use those workflows.
  People may instead prefer manual execution, an existing broker tool, or no AI involvement.
- General-purpose assistants may be the preferred interface. Their future adoption is uncertain.
- The benefit could outweigh additional setup, approvals, latency and trust in another service.
  This additional trust burden must be investigated rather than assumed away.
- Later multi-account and developer customers may reuse the same core. Their demand is untested.

Use the [community research guide](community-research.md) to investigate all barriers without
presenting a safety solution first. Keep counterexamples and reasons to continue using existing
workflows. Reddit responses are qualitative, self-selected evidence, not market adoption rates.

## Current implementation and boundary

Implemented: read-only Kite/Alpaca adapters, account and environment identities, local instrument
metadata, portfolio/holding snapshots, and a durable synthetic order lifecycle with local policy,
idempotency, expiry and halt controls. See [tools](tools.md) and [broker validation](broker-validation.md).

Not implemented: an isolated credential service, agent-resistant policy administration,
independently authenticated trade approval, external order execution, realistic fills, broker
order reconciliation, or a tamper-evident execution archive. Existing propose/confirm tools are
both agent-callable and mutate only the local synthetic sandbox.

The current self-hosted setup is not an independent security boundary against an agent with
shell/filesystem access: it can read local credentials or change policy and state. Self-hosting
alone does not solve that problem. Future enforcement requires a deployment and authorization
boundary that actually excludes the agent from broker secrets and administrative controls.

## Target execution design — not implemented

The following requirements guide a future design; none enables external writes today.

### Protected permissions and credentials

Broker credentials and signing material must be held outside the agent's accessible environment.
The agent must not have another authenticated broker API/MCP or browser route that bypasses
Flyrel while the product claims to control its actions. Clearly scope enforcement to requests
routed through Flyrel; manual trades, other connectors and pre-existing orders can change accounts.

Use explicit, typed broker operations and capability checks. Do not forward arbitrary MCP tools,
URLs or opaque payloads as an execution shortcut. An upstream broker MCP would require its own
mapping and security review; MCP is an interface, not the enforcement boundary.

Policy editing, credential enrollment, approval and resuming execution must use protected user
channels. An agent must not be able to grant itself rights, weaken policy or sign its own approval.

### Exact, independently authorized intent

A trusted preview must show broker, account, environment, currency, resolved instrument, side,
quantity, order type, limit and time-in-force. Approval must bind that exact content, an expiry
and a policy version. Changing the order or policy requires fresh authorization. The approver
must authenticate independently of the model and its tool arguments.

Recheck authorization, policy and relevant broker state immediately before submission. Reject
unsupported instruments, ambiguous accounts, expired approval, stale/missing required inputs and
unresolved execution outcomes. Controls must apply to all supported mutations, including changes
and cancellations, with explicitly defined permission and halt behavior.

### Durable execution and reconciliation

Design a durable intent/order state machine, broker-specific identifiers, concurrency controls
and exposure reservations that account for outstanding requests and partial fills. A timeout is
an unknown outcome, not proof that no order was accepted. Reconcile before retrying; pause new
submissions when the required state cannot be established. Do not claim distributed exactly-once
execution on the strength of a local idempotency key.

An emergency halt blocks defined future actions. It cannot undo fills, guarantee cancellation,
or ensure a particular exit price. Order-size/exposure controls do not guarantee a maximum market
loss, and a permitted order is not evidence of a sound investment decision.

## Initial scope and evidence

Start with order previews and policy/failure tests using synthetic data. A separately authorized
broker-paper milestone should be narrow: one broker, cash equities, limit orders and explicit
per-order approval. Live execution remains another separate decision after broker-paper evidence
and current broker/market review; no enable-live switch is planned.

Proposed validation work:

- Interview actual current, former and non-users about recent tasks before showing the concept.
- Rehearse wrong-account, modified-order, expired/replayed approval, concurrent-request,
  credential-access, missing-state, timeout, partial-fill and process-restart cases. Record the
  tested invariants and deployment assumptions; passing tests is not a universal safety proof.
- Compare a participant's existing workflow with a consented prototype task. Measure completion,
  time, comprehension, repeat use and whether the added control changes their actual choice.
- Track approval friction and trust in Flyrel itself, alongside the errors it is intended to block.

Continue if recurring concrete problems map to enforceable controls and participants choose to
try/use the bounded workflow despite its costs. Revise if other barriers dominate. Reconsider
if people have no useful delegation task or would avoid an intermediary regardless of controls.
Qualitative enthusiasm alone does not establish willingness to use or pay.

## Claims and deferred work

Do not claim "100% secure", guaranteed profits, loss-free trading, universal regulatory compliance,
or control over every route into a broker account. Describe the specific enforced permissions,
assumptions, tested failure cases, residual risks and unresolved states instead.

Preserve broker/account/environment/currency/synthetic labels. Do not fabricate NAV, freshness,
portfolio performance or historical returns. Keep compliance planning separate from implemented
enforcement. Continue correcting read-data issues needed for trustworthy decisions; defer broad
broker expansion, rich reporting, multi-user administration and a general backtesting engine
unless the selected workflow provides evidence for them.

## Primary engineering references

Consulted October 29, 2026; these inform design, not a compliance certification:

- [MCP security guidance](https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices)
  describes intermediary authorization, token-handling and local-server risks.
- [Alpaca SDK resilience guidance](https://github.com/alpacahq/alpaca-trade-api-js/blob/master/docs/docs/resilience.md)
  distinguishes a stable order identifier and reconciliation from exactly-once execution.
- [Existing regulatory notes](regulatory-notes.md) are dated research and must be refreshed for
  each future execution milestone; this direction does not establish permission to trade.
