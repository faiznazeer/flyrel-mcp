import httpx


class BrokerReadError(RuntimeError):
    def __init__(self, status_code: int | None = None):
        self.status_code = status_code
        self.code = (
            "auth_or_access"
            if status_code in {401, 403}
            else "rate_limited"
            if status_code == 429
            else "network"
            if status_code is None
            else "broker_error"
        )
        super().__init__(
            f"Broker read failed ({status_code or 'network'}); check auth and data access"
        )


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
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            raise BrokerReadError(status) from None

    def close(self) -> None:
        self.client.close()
