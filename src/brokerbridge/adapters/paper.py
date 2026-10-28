from datetime import UTC, datetime
from decimal import Decimal

from brokerbridge.models import Account, Quote, currency_for

PRICES = {"US:AAPL": Decimal("100"), "NSE:RELIANCE": Decimal("1000")}
SNAPSHOT = datetime(2026, 1, 1, tzinfo=UTC)


class PaperAdapter:
    id = "paper"
    environment = "synthetic"
    markets = ("IN", "US")
    capabilities = frozenset(
        {"accounts", "quotes", "positions", "holdings", "orders", "paper_orders"}
    )

    def accounts(self) -> list[Account]:
        return [
            Account(broker_id=self.id, account_id=f"paper-{c}", currency=c, environment="synthetic")
            for c in ("USD", "INR")
        ]

    def quotes(self, symbols: list[str]) -> list[Quote]:
        if any(s not in PRICES for s in symbols):
            raise ValueError("Synthetic quotes only support US:AAPL and NSE:RELIANCE")
        return [
            Quote(
                symbol=s,
                currency=currency_for(s),
                last=PRICES[s],
                timestamp=SNAPSHOT,
                source="paper:synthetic-fixed-fixture",
                synthetic=True,
            )
            for s in symbols
        ]

    def positions(self) -> list:
        return []

    def holdings(self) -> list:
        return []

    def close(self) -> None:
        pass
