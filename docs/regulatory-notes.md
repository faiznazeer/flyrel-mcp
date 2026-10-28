# Regulatory and API research notes

Reviewed October 28, 2026. These are engineering research notes, not a legal opinion or an
exhaustive current rulebook. This release has no broker execution path or compliance engine.

## India

[SEBI's February 4, 2025 framework](https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html)
sets out a broker-mediated retail algorithmic trading framework, including responsibilities for
brokers, investors and algo providers. Do not infer that open source or personal deployment
automatically removes obligations.

[SEBI's September 30, 2025 implementation circular](https://www.sebi.gov.in/legal/circulars/sep-2025/extension-of-timeline-for-implementation-of-sebi-circular-dated-february-04-2025-on-safer-participation-of-retail-investors-in-algorithmic-trading-_96979.html)
sets April 1, 2026 as the date the framework and exchange standards apply to all stock
brokers (paragraph 8). Confirm subsequent amendments and broker implementation before execution
work. This repository does not implement those obligations.

[NSE's retail algo FAQ](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/FAQ_Retail%20Algo_03112025_NSE.pdf)
explains API order tagging, the 10 OPS threshold, static-IP distinctions, provider hosting and
black-box provider requirements. Its treatment distinguishes tech-savvy client deployment from
provider strategies hosted on broker infrastructure. It also identifies order-type restrictions.
Therefore do not reduce compliance to a universal static-IP or India-hosting boolean, assume a
generic ID is an exemption, or encode a single rule for every segment. Follow the binding
circulars referenced in the FAQ and the broker's current onboarding requirements.

## United States

[FINRA's new intraday margin guidance](https://syndication.finra.org/content/understanding-new-intraday-margin-requirements)
describes replacement of the prior PDT framework, effective June 4, 2026, with a permitted firm
transition through October 20, 2027. Account restrictions can consequently differ by broker
implementation during that window. Do not hardcode the old PDT threshold as a universal
current US check. Account type, buying power, short-sale rules, settlement, data permissions
and local eligibility need separate treatment before execution.

## API references used for this foundation

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk): pinned to the supported v1 maintenance line,
  with an actual stdio integration test. V2 is now stable; migration is separate work.
- [Kite API documentation](https://kite.trade/docs/connect/v3/),
  [market quotes](https://kite.trade/docs/connect/v3/market-quotes/),
  [portfolio](https://kite.trade/docs/connect/v3/portfolio/) and
  [history](https://kite.trade/docs/connect/v3/historical/): initial read mappings only.
- [Alpaca market data](https://docs.alpaca.markets/us/docs/about-market-data-api) and
  [paper trading](https://docs.alpaca.markets/us/v1.4.2/docs/paper-trading): data feeds and
  paper/live account environments are distinct.
- [Alpaca's official MCP documentation](https://docs.alpaca.markets/us/docs/trading-api-mcp)
  confirms its own connector exists. BrokerBridge's initial implementation talks to REST directly;
  it does not proxy or require a broker MCP server.

The community/official status of every other broker connector in the original discussion has
not been independently established here. It is not needed for these two read adapters.
