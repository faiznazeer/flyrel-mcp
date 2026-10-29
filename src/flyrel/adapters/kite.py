import csv
import io
from datetime import datetime
from decimal import Decimal

from flyrel.adapters.base import Interval
from flyrel.adapters.http import ReadOnlyHTTP
from flyrel.models import Account, Bar, Order, Position, PositionPerformance, Quote, validate_range


class KiteAdapter(ReadOnlyHTTP):
    id = "kite"
    environment = "live"
    markets = ("IN",)
    capabilities = frozenset({"accounts", "quotes", "history", "positions", "holdings", "orders"})
    base = "https://api.kite.trade"

    def __init__(self, key: str, token: str, transport=None):
        super().__init__(
            {"X-Kite-Version": "3", "Authorization": f"token {key}:{token}"}, transport
        )

    @staticmethod
    def check(symbol: str) -> str:
        if symbol.split(":")[0] not in {"NSE", "BSE"}:
            raise ValueError("Kite starter supports NSE/BSE cash equities only")
        return symbol

    def data(self, path: str, params=None):
        result = self.get(self.base + path, params).json(parse_float=Decimal)
        if result.get("status") != "success":
            raise ValueError("Kite returned an unsuccessful response")
        return result["data"]

    def accounts(self) -> list[Account]:
        a = self.data("/user/profile")
        return [
            Account(broker_id=self.id, account_id=a["user_id"], currency="INR", environment="live")
        ]

    def quotes(self, symbols: list[str]) -> list[Quote]:
        data = self.data("/quote", [("i", self.check(s)) for s in symbols])
        if any(s not in data for s in symbols):
            raise ValueError("Kite did not return all requested quotes")
        # Kite timestamp strings have no timezone; avoid inventing a quote timestamp.
        return [
            Quote(symbol=s, currency="INR", last=data[s]["last_price"], source="kite")
            for s in symbols
        ]

    def history(self, symbol: str, interval: Interval, start: datetime, end: datetime) -> list[Bar]:
        from zoneinfo import ZoneInfo

        validate_range(start, end)
        exchange, ticker = self.check(symbol).split(":", 1)
        rows = csv.DictReader(io.StringIO(self.get(f"{self.base}/instruments/{exchange}").text))
        token = next((r["instrument_token"] for r in rows if r["tradingsymbol"] == ticker), None)
        if token is None:
            raise ValueError("Instrument not found in current Kite instrument master")
        periods = {"1Min": "minute", "1Hour": "60minute", "1Day": "day"}
        zone = ZoneInfo("Asia/Kolkata")
        candles = self.data(
            f"/instruments/historical/{token}/{periods[interval]}",
            {
                "from": start.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"),
                "to": end.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S"),
            },
        )["candles"]
        return [
            Bar(
                symbol=symbol,
                timestamp=c[0],
                open=c[1],
                high=c[2],
                low=c[3],
                close=c[4],
                volume=c[5],
            )
            for c in candles
        ]

    def normalize(
        self, rows: list[dict], account_id: str, *, holdings: bool = False
    ) -> list[Position]:
        if any(r["exchange"] not in {"NSE", "BSE"} for r in rows):
            raise ValueError("Non-cash segment unsupported; portfolio would be incomplete")
        return [
            Position(
                broker_id=self.id,
                account_id=account_id,
                environment=self.environment,
                symbol=f"{r['exchange']}:{r['tradingsymbol']}",
                currency="INR",
                quantity=Decimal(str(r["quantity"])) + Decimal(str(r.get("t1_quantity", 0))),
                average_price=r["average_price"],
                product=r.get("product", "CNC"),
                market_value=(
                    (Decimal(str(r["quantity"])) + Decimal(str(r.get("t1_quantity", 0))))
                    * Decimal(str(r["last_price"]))
                    if r.get("last_price") is not None
                    else None
                ),
                # Kite position `pnl` can include realized P&L. Only its holdings
                # response is mapped to the current holding's unrealized P&L.
                performance=PositionPerformance(
                    source="kite_holdings",
                    last_price=r.get("last_price"),
                    previous_close=r.get("close_price"),
                    unrealized_pnl=r.get("pnl"),
                    day_price_change=r.get("day_change"),
                    day_price_change_percent=r.get("day_change_percentage"),
                )
                if holdings
                else None,
            )
            for r in rows
        ]

    def positions(self) -> list[Position]:
        return self.normalize(
            self.data("/portfolio/positions")["net"], self.accounts()[0].account_id
        )

    def holdings(self) -> list[Position]:
        return self.normalize(
            self.data("/portfolio/holdings"), self.accounts()[0].account_id, holdings=True
        )

    def orders(self) -> list[Order]:
        rows = self.data("/orders")
        if any(r["exchange"] not in {"NSE", "BSE"} for r in rows):
            raise ValueError("Non-cash segment orders unsupported")
        return [
            Order(
                broker_id=self.id,
                order_id=r["order_id"],
                symbol=f"{r['exchange']}:{r['tradingsymbol']}",
                side=r["transaction_type"].lower(),
                quantity=r["quantity"],
                limit_price=r.get("price"),
                status=r["status"],
                environment="live",
            )
            for r in rows
        ]
