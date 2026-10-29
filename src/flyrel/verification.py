"""Opt-in broker reads with a metadata-only report; no snapshots are recorded."""

from datetime import UTC, datetime

from flyrel.adapters import external_adapter
from flyrel.adapters.http import BrokerReadError
from flyrel.config import Settings
from flyrel.models import Symbol, validate_range


def verify_brokers(
    settings: Settings,
    brokers: list[str],
    *,
    history_start: datetime | None = None,
    history_end: datetime | None = None,
    connection_ids: list[str] | None = None,
) -> dict:
    if not brokers or any(b not in {"kite", "alpaca"} for b in brokers):
        raise ValueError("Select kite and/or alpaca")
    if (history_start is None) != (history_end is None):
        raise ValueError("Provide both history bounds")
    if history_start is not None and history_end is not None:
        validate_range(history_start, history_end)
        if (history_end - history_start).total_seconds() > 31 * 86400:
            raise ValueError("Request at most 31 days")

    selected = (
        [key for broker_id in dict.fromkeys(brokers) for key in settings.connection_ids(broker_id)]
        if connection_ids is None
        else connection_ids
    )
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select at least one unique connection")
    profiles = {key: settings.connection_profile(key) for key in selected}
    if any(profile[0] not in brokers for profile in profiles.values()):
        raise ValueError("Selected connection does not match the requested broker")

    reports = []
    for connection_id in selected:
        broker_id, environment, feed = profiles[connection_id]
        report = {
            "broker_id": broker_id,
            "connection_id": connection_id,
            "environment": environment,
            "currency": "INR" if broker_id == "kite" else "USD",
            "synthetic": False,
            "data_feed": feed,
            "quote_probe_symbol": "NSE:RELIANCE" if broker_id == "kite" else "US:AAPL",
            "checks": [],
        }
        reports.append(report)
        try:
            adapter = external_adapter(settings, connection_id)
        except ValueError:
            report["status"] = "configuration_error"
            continue
        if adapter is None:
            report["status"] = "not_configured"
            continue

        symbol: Symbol = "NSE:RELIANCE" if broker_id == "kite" else "US:AAPL"
        operations = ["accounts", "positions", "holdings", "orders", "quotes"]
        if history_start is not None:
            operations.append("history")
        account_ids = set()
        try:
            for operation in operations:
                check = {"operation": operation}
                report["checks"].append(check)
                try:
                    if operation == "quotes":
                        rows = adapter.quotes([symbol])
                        if len(rows) != 1 or rows[0].symbol != symbol or rows[0].synthetic:
                            raise ValueError("Unexpected quote identity")
                    elif operation == "history":
                        rows = adapter.history(symbol, "1Day", history_start, history_end)
                        if any(row.symbol != symbol for row in rows):
                            raise ValueError("Unexpected bar identity")
                    else:
                        rows = getattr(adapter, operation)()
                    if operation in {"accounts", "positions", "holdings", "orders"}:
                        if any(
                            row.broker_id != broker_id or row.environment != report["environment"]
                            for row in rows
                        ):
                            raise ValueError("Unexpected broker/environment identity")
                    if operation in {"accounts", "positions", "holdings", "quotes"}:
                        if any(row.currency != report["currency"] for row in rows):
                            raise ValueError("Unexpected currency")
                    if operation == "accounts":
                        account_ids = {row.account_id for row in rows}
                        if not account_ids:
                            raise ValueError("No account returned")
                    if operation in {"positions", "holdings"}:
                        if any(row.account_id not in account_ids for row in rows):
                            raise ValueError("Unexpected account identity")
                    check.update(status="passed", count=len(rows))
                except BrokerReadError as exc:
                    check.update(status="failed", reason=exc.code, http_status=exc.status_code)
                    # Stop this connection on auth, throttling or transport errors. No retry storm.
                    break
                except Exception:
                    # Schema errors can contain entire broker payloads. Never render them.
                    check.update(status="failed", reason="response_validation")
                    break
            report["status"] = (
                "passed" if all(c["status"] == "passed" for c in report["checks"]) else "failed"
            )
        finally:
            adapter.close()

    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "live_execution_implemented": False,
        "account_details": "omitted",
        "scope": "API connectivity and normalization; broker UI reconciliation is still required",
        "history": "1Day; broker-supplied bars; no local corporate-action adjustment"
        if history_start is not None
        else "not_requested",
        "brokers": reports,
        "passed": all(r["status"] == "passed" for r in reports),
    }
