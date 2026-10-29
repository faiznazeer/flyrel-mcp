from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Symbol = Annotated[str, Field(pattern=r"^(US|NSE|BSE):[A-Z0-9][A-Z0-9.&/_-]*$", max_length=80)]
Currency = Literal["USD", "INR"]
Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


def currency_for(symbol: str) -> Currency:
    return "USD" if symbol.startswith("US:") else "INR"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Instrument(Model):
    instrument_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,99}$")]
    symbol: Symbol
    name: str
    currency: Currency
    asset_class: Literal["equity"] = "equity"
    venue: Annotated[str, Field(min_length=1, max_length=20)] | None = None
    broker_symbols: dict[Literal["kite", "alpaca", "paper"], str] = Field(default_factory=dict)
    source: Literal["local", "synthetic-fixture"] = "local"
    synthetic: bool = False

    @model_validator(mode="after")
    def consistent_identity(self):
        prefix, ticker = self.symbol.split(":", 1)
        if self.currency != currency_for(self.symbol):
            raise ValueError("Instrument currency must match its supported market")
        if (prefix != "US" and self.venue != prefix) or (
            prefix == "US" and self.venue in {"NSE", "BSE"}
        ):
            raise ValueError(
                "Venue must match the market; a US listing venue is optional and explicit"
            )
        if self.synthetic != (self.source == "synthetic-fixture"):
            raise ValueError("Synthetic instrument metadata must be labelled consistently")
        for broker_id, broker_symbol in self.broker_symbols.items():
            expected = ticker if broker_id == "alpaca" else self.symbol
            if broker_id == "alpaca" and prefix != "US":
                raise ValueError("Alpaca mappings require a US symbol")
            if broker_id == "kite" and prefix == "US":
                raise ValueError("Kite mappings require an NSE/BSE symbol")
            if broker_symbol != expected:
                raise ValueError("Broker symbol does not match the supported adapter mapping")
        return self


class AccountIdentity(Model):
    broker_id: str
    account_id: str
    environment: Literal["synthetic", "paper", "live"]


class Account(Model):
    broker_id: str
    account_id: str
    currency: Currency
    cash: Decimal | None = None
    environment: Literal["synthetic", "paper", "live"]


class Quote(Model):
    symbol: Symbol
    currency: Currency
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    timestamp: AwareDatetime | None = None
    source: str
    synthetic: bool = False


class Bar(Model):
    symbol: Symbol
    timestamp: AwareDatetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class Position(Model):
    environment: Literal["synthetic", "paper", "live"]
    broker_id: str
    account_id: str
    symbol: Symbol
    currency: Currency
    quantity: Decimal
    average_price: Decimal
    market_value: Decimal | None = None
    product: str


class OrderRequest(Model):
    broker_id: Literal["paper"] = "paper"
    symbol: Symbol
    side: Literal["buy"] = "buy"
    quantity: Annotated[int, Field(gt=0, le=1_000_000, strict=True)]
    limit_price: Positive
    idempotency_key: Annotated[str, Field(min_length=8, max_length=100, pattern=r"^[\w-]+$")]


class Order(Model):
    broker_id: str
    order_id: str
    symbol: Symbol
    side: str
    quantity: Decimal
    limit_price: Decimal | None = None
    status: str
    environment: Literal["synthetic", "paper", "live"]


class Policy(Model):
    read_only: bool = False
    allowed_symbols: tuple[Symbol, ...] = ("US:AAPL", "NSE:RELIANCE")
    max_order_value: dict[Currency, Positive] = Field(
        default_factory=lambda: {"USD": Decimal("1000"), "INR": Decimal("100000")}
    )
    max_open_value: dict[Currency, Positive] = Field(
        default_factory=lambda: {"USD": Decimal("5000"), "INR": Decimal("500000")}
    )
    proposal_ttl_seconds: Annotated[int, Field(ge=1, le=900)] = 120

    @field_validator("max_order_value", "max_open_value")
    @classmethod
    def require_currencies(cls, value: dict) -> dict:
        if set(value) != {"USD", "INR"}:
            raise ValueError("Both USD and INR limits are required")
        return value


def validate_range(start: datetime, end: datetime) -> None:
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Use timezone-aware datetimes with start before end")
