"""External adapters expose GET operations only; execution stays in the local sandbox."""

from flyrel.adapters.alpaca import AlpacaAdapter
from flyrel.adapters.kite import KiteAdapter
from flyrel.config import Settings


def external_adapter(settings: Settings, connection_id: str) -> KiteAdapter | AlpacaAdapter | None:
    """Construct one read-only adapter without creating local state or making requests."""
    for connection in settings.broker_connections:
        if connection.connection_id != connection_id:
            continue
        if connection.broker_id == "kite":
            return KiteAdapter(
                connection.api_key.get_secret_value(), connection.access_token.get_secret_value()
            )
        return AlpacaAdapter(
            connection.api_key.get_secret_value(),
            connection.secret_key.get_secret_value(),
            paper=connection.environment == "paper",
            feed=connection.feed,
        )
    broker_id = connection_id
    if broker_id == "kite":
        key = settings.kite_api_key.get_secret_value()
        token = settings.kite_access_token.get_secret_value()
        if bool(key) != bool(token):
            raise ValueError("Set both Kite API key and access token")
        return KiteAdapter(key, token) if key else None
    if broker_id == "alpaca":
        key = settings.alpaca_api_key.get_secret_value()
        secret = settings.alpaca_secret_key.get_secret_value()
        if bool(key) != bool(secret):
            raise ValueError("Set both Alpaca key and secret")
        return (
            AlpacaAdapter(key, secret, settings.alpaca_paper, settings.alpaca_feed) if key else None
        )
    raise ValueError("Unknown external broker")
