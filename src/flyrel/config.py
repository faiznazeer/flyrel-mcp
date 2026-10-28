from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_alias(name: str) -> AliasChoices:
    # Prefer the new name while keeping existing deployments configured after the rename.
    return AliasChoices(f"FLYREL_{name}", f"BROKERBRIDGE_{name}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLYREL_", env_file=".env", extra="ignore", populate_by_name=True
    )
    state_dir: Path = Field(default=Path(".state"), validation_alias=_env_alias("STATE_DIR"))
    kite_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=_env_alias("KITE_API_KEY")
    )
    kite_access_token: SecretStr = Field(
        default=SecretStr(""), validation_alias=_env_alias("KITE_ACCESS_TOKEN")
    )
    alpaca_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=_env_alias("ALPACA_API_KEY")
    )
    alpaca_secret_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=_env_alias("ALPACA_SECRET_KEY")
    )
    alpaca_paper: bool = Field(default=True, validation_alias=_env_alias("ALPACA_PAPER"))
    alpaca_feed: str = Field(default="iex", validation_alias=_env_alias("ALPACA_FEED"))
