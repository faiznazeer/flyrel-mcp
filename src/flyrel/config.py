from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrokerConnection(BaseModel):
    """One credential set; a local connection name never replaces the broker account ID."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    connection_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
    broker_id: Literal["kite", "alpaca"]
    environment: Literal["paper", "live"]
    api_key: SecretStr
    access_token: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")
    feed: Annotated[str, Field(min_length=1, max_length=40)] = "iex"

    @model_validator(mode="after")
    def validate_credentials(self):
        if self.connection_id in {"paper", "kite", "alpaca"}:
            raise ValueError("Named connections cannot use reserved IDs paper, kite or alpaca")
        if not self.api_key.get_secret_value():
            raise ValueError("A named connection requires an API key")
        if self.broker_id == "kite":
            if self.environment != "live":
                raise ValueError("Kite connections support live account reads only")
            if not self.access_token.get_secret_value() or self.secret_key.get_secret_value():
                raise ValueError("Kite requires an access token and no Alpaca secret key")
        elif not self.secret_key.get_secret_value() or self.access_token.get_secret_value():
            raise ValueError("Alpaca requires a secret key and no Kite access token")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLYREL_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    state_dir: Path = Path(".state")
    kite_api_key: SecretStr = SecretStr("")
    kite_access_token: SecretStr = SecretStr("")
    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_paper: bool = True
    alpaca_feed: str = "iex"
    broker_connections: list[BrokerConnection] = Field(default_factory=list)
    instrument_registry_file: Path | None = None

    @model_validator(mode="after")
    def unique_connections(self):
        names = [c.connection_id for c in self.broker_connections]
        if len(names) != len(set(names)):
            raise ValueError("Connection IDs must be unique")
        return self

    def connection_ids(self, broker_id: str) -> list[str]:
        if broker_id not in {"kite", "alpaca"}:
            raise ValueError("Unknown external broker")
        named = [c.connection_id for c in self.broker_connections if c.broker_id == broker_id]
        has_default = (
            bool(self.kite_api_key.get_secret_value() or self.kite_access_token.get_secret_value())
            if broker_id == "kite"
            else bool(
                self.alpaca_api_key.get_secret_value() or self.alpaca_secret_key.get_secret_value()
            )
        )
        return ([broker_id] if has_default or not named else []) + named

    def connection_profile(self, connection_id: str) -> tuple[str, str, str]:
        """Non-secret broker, environment and feed metadata."""
        for connection in self.broker_connections:
            if connection.connection_id == connection_id:
                return (
                    connection.broker_id,
                    connection.environment,
                    "kite" if connection.broker_id == "kite" else connection.feed,
                )
        if connection_id == "kite":
            return "kite", "live", "kite"
        if connection_id == "alpaca":
            return "alpaca", "paper" if self.alpaca_paper else "live", self.alpaca_feed
        raise ValueError("Unknown connection")
