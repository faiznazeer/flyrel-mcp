# Validate cross-broker portfolio review

This is a supporting read-data/usability track. The primary experiment is now the
[independent permissions and approval layer](product-direction.md); the
[community research guide](community-research.md) investigates actual adoption barriers before
introducing that concept. A successful portfolio review does not establish demand for agent
execution or authorize external writes. Initial product discovery can include a single-account
investor or an organizational builder/operator; no customer segment has been selected. The
multi-broker criteria below apply to this particular portfolio comparison. Owner or Reddit
feedback does not establish demand from brokers, agent-building companies or quant firms.

Selected first workflow: review equity holdings across Kite and Alpaca. Alpaca paper-account and
Kite Personal account API checks passed on October 29, 2026. The owner reported that available
Kite holding values matched the UI. A first owner walkthrough identified current holding/daily
performance as useful, with actual personal portfolio returns and account growth as a later need.
The new holding-performance fields have not yet been compared privately with the broker UI.
Alpaca is empty, and no measured multi-broker benefit or completed multi-user pilot is established.
See the [validation record](broker-validation.md).

## Question to answer

Can someone with both accounts review what they hold, where they hold it, and what remains
unpriced or unreconciled more quickly and reliably than by switching between broker interfaces?
The present product can show separate broker records and per-account holding value/P&L summaries.
It cannot yet produce a complete combined exposure figure, concentration percentage or NAV.
Treat demand for those outputs as input to remaining reconciliation work, prioritized against
the selected product experiment rather than assumed to be the next release.

## Offline walkthrough

Run this now, without configuring keys:

```bash
uv run flyrel demo-portfolio
```

Alternatively call `get_demo_portfolio` from the MCP client. Both return the same fixed, invented
four-account scenario and sample instrument catalog, dated January 1, 2026. Every account, position
and holding is labelled `synthetic`; broker IDs describe the schema being rehearsed, not connected
accounts. The CLI loads no settings, makes no network requests and writes no state. The demo is
separate from the zero-position local order sandbox and does not change external read routing.

Practice these tasks:

1. Identify all four connection names, broker/account references and currencies. Explain why
   connection names and broker-returned account IDs are separate concepts.
2. Inspect the two Kite-style accounts holding the same canonical symbol. Keep the accounts
   separate, and explain why the first account's delivery holdings are not added to net positions.
3. Find the fractional and short positions in the Alpaca-style examples. Explain why holdings
   are an alias and why adding them again would double-count the positions.
4. Find the unpriced position in `demo-alpaca-second`. Confirm the full USD position value is null,
   the completeness flag is false, and the partial priced USD value is separately identified.
5. Inspect the sample NSE/BSE instrument records. Confirm they have distinct local IDs; do not
   infer cross-listing equivalence or combine them based only on a shared ticker.
6. State what remains unknown: actual account correctness, current prices, user usefulness,
   holdings reconciliation, FX, cash-inclusive NAV and real execution behavior.

Automated tests rehearse these properties through the same portfolio helpers and the MCP tool.
They also cover multiple mocked broker connections, duplicate account detection, paper/live
identity isolation and rejected ambiguous routing. This verifies engineering behavior with
synthetic inputs. It does not establish a measured user benefit or real-account compatibility.

## First session

Use the account owner's own machine and MCP client. Recruit three people who actually use more
than one broker; start with the project owner if eligible. Obtain their agreement before reading
their accounts. Do not contact participants or collect their portfolio data automatically.

1. Ask how often they review both accounts, which question they are trying to answer, how they
   currently do it, and what mistakes or missing data cost them time.
2. Time their existing process: identify positions, delivery holdings, and open orders separately
   in both broker interfaces. Note account environment, currency, data feed and observation time.
3. Repeat with Flyrel. Discover connections with `list_brokers`, select `connection_id` explicitly
   for brokers with multiple connections, and check `list_accounts` privately,
   then read `get_positions` and `get_holdings` for each broker. Use `list_orders` to review order
   context, `get_holdings_summary` for current holding value/P&L, and `get_portfolio_summary` for
   separate position values and holding summaries. Kite daily price change is distinct from
   daily monetary P&L. Missing broker performance stays unknown; do not infer account returns.
4. Ask them to explain the result: which account each record belongs to, which records overlap,
   whether the Alpaca account is paper or live, and what is excluded from the portfolio summary.
   Distinguish current holding P&L from historical portfolio return and account-value growth.
   Do not add Alpaca holdings to positions. Keep Kite holdings separate pending reconciliation.
   Keep the local synthetic `paper` broker out of any real-account comparison.
   Inspect `duplicate_accounts` before treating snapshots from different connections as distinct.
5. Compare records privately with the same broker UI. Record timing differences and discrepancies
   before deciding whether the adapter mapping is wrong. Prices can move between observations.
6. Ask whether they would use this again, what it replaces, and which missing output matters most.

Proposed pilot acceptance criteria: three completed sessions; every participant correctly
distinguishes currencies, environments and overlapping views; no unexplained mapping discrepancy;
at least two prefer the workflow and identify a repeated use. Record baseline and Flyrel times
without claiming a speed improvement before measuring it. Revise the criteria with participants
if the task does not reflect their actual needs.

## Session notes template

Keep completed notes outside version control or under ignored `.state/`. Use an anonymous
participant label; do not include account IDs, balances, positions, screenshots or credentials.

```text
Participant label / session date:
Workflow and review frequency:
Brokers and environments (no account IDs):
Existing process / elapsed time:
Flyrel task / elapsed time:
Understood currency, account and overlap labels? yes/no + issue:
Broker UI checks: matched / mismatch / not observable:
Missing data or unsupported instruments:
Most useful output / repeated use:
Would use again? why:
Decision: continue / change workflow / stop:
```

Completion requires actual sessions and the account checks in [broker validation](broker-validation.md).
Preparing this guide or passing mocked tests does not complete the milestone.
