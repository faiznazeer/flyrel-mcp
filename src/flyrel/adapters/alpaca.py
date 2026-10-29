from datetime import datetime
from decimal import Decimal

from flyrel.adapters.base import Interval
from flyrel.adapters.http import ReadOnlyHTTP
from flyrel.models import Account, Bar, Order, Position, PositionPerformance, Quote, validate_range


class AlpacaAdapter(ReadOnlyHTTP):
    id = "alpaca"
    markets = ("US",)
    capabilities = frozenset({"accounts", "quotes", "history", "positions", "holdings", "orders"})

    def __init__(
        self, key: str, secret: str, paper: bool = True, feed: str = "iex", transport=None
    ):
        super().__init__({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}, transport)
        self.base = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.environment = "paper" if paper else "live"
        self.feed = feed

    @staticmethod
    def raw(symbol: str) -> str:
        if not symbol.startswith("US:"):
            raise ValueError("Alpaca supports US: equity symbols in this starter")
        return symbol.removeprefix("US:")

    def accounts(self) -> list[Account]:
        a = self.get(f"{self.base}/v2/account").json(parse_float=Decimal)
        return [
            Account(
                broker_id=self.id,
                account_id=a["id"],
                currency="USD",
                cash=a["cash"],
                environment=self.environment,
            )
        ]

    def quotes(self, symbols: list[str]) -> list[Quote]:
        data = self.get(
            "https://data.alpaca.markets/v2/stocks/quotes/latest",
            params={
                "symbols": ",".join(self.raw(s) for s in symbols),
                "feed": self.feed,
            },
        ).json(parse_float=Decimal)["quotes"]
        if any(self.raw(s) not in data for s in symbols):
            raise ValueError("Broker did not return all requested quotes")
        return [
            Quote(
                symbol=s,
                currency="USD",
                bid=data[self.raw(s)]["bp"],
                ask=data[self.raw(s)]["ap"],
                timestamp=data[self.raw(s)]["t"],
                source=f"alpaca:{self.feed}",
            )
            for s in symbols
        ]

    def history(self, symbol: str, interval: Interval, start: datetime, end: datetime) -> list[Bar]:
        validate_range(start, end)
        params = {
            "timeframe": interval,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "feed": self.feed,
            "adjustment": "raw",
            "limit": 10000,
        }
        bars = []
        seen_tokens = set()
        for _ in range(100):
            data = self.get(
                f"https://data.alpaca.markets/v2/stocks/{self.raw(symbol)}/bars", params=params
            ).json(parse_float=Decimal)
            bars.extend(
                Bar(
                    symbol=symbol,
                    timestamp=b["t"],
                    open=b["o"],
                    high=b["h"],
                    low=b["l"],
                    close=b["c"],
                    volume=b["v"],
                )
                for b in data.get("bars") or []
            )
            if len(bars) > 50000:
                raise ValueError("History too large; request a shorter range")
            token = data.get("next_page_token")
            if not token:
                return bars
            if token in seen_tokens:
                raise ValueError("History pagination repeated a token; snapshot is incomplete")
            if len(bars) >= 50000:
                raise ValueError("History too large; request a shorter range")
            seen_tokens.add(token)
            params["page_token"] = token
        raise ValueError("History pagination exceeded 100 pages; request a shorter range")

    def positions(self) -> list[Position]:
        # USD is deliberately scoped to US equities; derivatives and crypto are future work.
        data = self.get(f"{self.base}/v2/positions").json(parse_float=Decimal)
        if any(p.get("asset_class") != "us_equity" for p in data):
            raise ValueError("Non-equity positions are unsupported; portfolio would be incomplete")
        account_id = self.accounts()[0].account_id
        return [
            Position(
                broker_id=self.id,
                account_id=account_id,
                environment=self.environment,
                symbol=f"US:{p['symbol']}",
                currency="USD",
                quantity=p["qty"],
                average_price=p["avg_entry_price"],
                market_value=p["market_value"],
                product="equity",
                performance=PositionPerformance(
                    source="alpaca_positions",
                    last_price=p.get("current_price"),
                    previous_close=p.get("lastday_price"),
                    unrealized_pnl=p.get("unrealized_pl"),
                    day_unrealized_pnl=p.get("unrealized_intraday_pl"),
                    day_price_change_percent=(
                        Decimal(str(p["change_today"])) * 100
                        if p.get("change_today") is not None
                        else None
                    ),
                ),
            )
            for p in data
        ]

    def holdings(self) -> list[Position]:
        # Same collection: callers must not add holdings and positions together.
        return self.positions()

    def orders(self) -> list[Order]:
        data = self.get(f"{self.base}/v2/orders", params={"status": "open", "limit": 500}).json(
            parse_float=Decimal
        )
        if len(data) >= 500:
            raise ValueError("Order snapshot may be truncated; use broker UI")
        if any(o.get("asset_class") != "us_equity" for o in data):
            raise ValueError("Non-equity orders are unsupported")
        return [
            Order(
                broker_id=self.id,
                order_id=o["id"],
                symbol=f"US:{o['symbol']}",
                side=o["side"],
                quantity=Decimal(o["qty"]),
                limit_price=o.get("limit_price"),
                status=o["status"],
                environment=self.environment,
            )
            for o in data
        ]
