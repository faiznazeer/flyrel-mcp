import httpx


class BrokerReadError(RuntimeError):
    pass


class ReadOnlyHTTP:
    def __init__(self, headers: dict[str, str], transport: httpx.BaseTransport | None = None):
        self.client = httpx.Client(headers=headers, timeout=20, transport=transport)

    def get(self, url: str, params=None):
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            # Never return broker response bodies, headers, or credential-bearing objects.
            status = (
                exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else "network"
            )
            raise BrokerReadError(
                f"Broker read failed ({status}); check auth and data access"
            ) from None

    def close(self) -> None:
        self.client.close()
