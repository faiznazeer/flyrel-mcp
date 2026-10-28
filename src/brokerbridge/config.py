from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROKERBRIDGE_", env_file=".env", extra="ignore")
    state_dir: Path = Path(".state")
    kite_api_key: SecretStr = SecretStr("")
    kite_access_token: SecretStr = SecretStr("")
    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_paper: bool = True
    alpaca_feed: str = "iex"
