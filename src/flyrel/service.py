from pathlib import Path

from flyrel.adapters.alpaca import AlpacaAdapter
from flyrel.adapters.kite import KiteAdapter
from flyrel.adapters.paper import PaperAdapter
from flyrel.config import Settings
from flyrel.models import Policy
from flyrel.store import Store


class Service:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.state_dir)
        self.adapters = {"paper": PaperAdapter()}
        if bool(settings.kite_api_key.get_secret_value()) != bool(
            settings.kite_access_token.get_secret_value()
        ):
            raise ValueError("Set both Kite API key and access token")
        if bool(settings.alpaca_api_key.get_secret_value()) != bool(
            settings.alpaca_secret_key.get_secret_value()
        ):
            raise ValueError("Set both Alpaca key and secret")
        if settings.kite_api_key.get_secret_value():
            self.adapters["kite"] = KiteAdapter(
                settings.kite_api_key.get_secret_value(),
                settings.kite_access_token.get_secret_value(),
            )
        if settings.alpaca_api_key.get_secret_value():
            self.adapters["alpaca"] = AlpacaAdapter(
                settings.alpaca_api_key.get_secret_value(),
                settings.alpaca_secret_key.get_secret_value(),
                settings.alpaca_paper,
                settings.alpaca_feed,
            )

    @property
    def policy_path(self) -> Path:
        return self.settings.state_dir / "policy.json"

    def policy(self) -> Policy:
        # Reload before each decision; malformed policy fails closed.
        return (
            Policy.model_validate_json(self.policy_path.read_text())
            if self.policy_path.exists()
            else Policy()
        )

    def adapter(self, broker_id: str, capability: str):
        if broker_id not in self.adapters:
            raise ValueError("Broker is not configured; use list_brokers")
        adapter = self.adapters[broker_id]
        if capability not in adapter.capabilities:
            raise ValueError(f"Broker does not support {capability}")
        return adapter

    def close(self):
        for adapter in self.adapters.values():
            adapter.close()
