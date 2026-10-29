import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from flyrel.config import Settings
from flyrel.demo import demo_registry
from flyrel.instruments import InstrumentRegistry
from flyrel.models import Instrument
from flyrel.server import create_server


def instrument(**changes):
    return Instrument.model_validate(
        {
            "instrument_id": "local-aapl",
            "symbol": "US:AAPL",
            "name": "Local AAPL example",
            "currency": "USD",
            "broker_symbols": {"alpaca": "AAPL"},
            **changes,
        }
    )


def test_registry_keeps_stable_local_id_venue_and_broker_symbol_distinct(tmp_path):
    registry = demo_registry()
    nse = registry.resolve("NSE:RELIANCE", "kite")
    bse = registry.resolve("BSE:RELIANCE", "kite")
    assert nse.instrument_id != bse.instrument_id and nse.venue != bse.venue
    assert len(registry.search("reliance", "kite")) == 2
    assert registry.resolve("sample-us-aapl", "alpaca").broker_symbols["alpaca"] == "AAPL"
    assert registry.resolve("US:AAPL").venue is None
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [instrument().model_dump(mode="json")]}))
    reloaded = InstrumentRegistry.load(path)
    assert reloaded.resolve("US:AAPL").instrument_id == "local-aapl"
    assert not reloaded.resolve("local-aapl").synthetic
    assert InstrumentRegistry.load(None).search("") == []


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "INR"},
        {"venue": "NSE"},
        {"broker_symbols": {"kite": "NSE:AAPL"}},
        {"broker_symbols": {"alpaca": "US:AAPL"}},
        {"source": "synthetic-fixture"},
        {"synthetic": True},
    ],
)
def test_registry_rejects_conflicting_market_mapping_or_synthetic_labels(change):
    with pytest.raises(ValidationError):
        instrument(**change)


@pytest.mark.parametrize(
    "second",
    [
        {"instrument_id": "local-aapl", "symbol": "US:MSFT", "broker_symbols": {"alpaca": "MSFT"}},
        {"instrument_id": "other-id"},
        {"instrument_id": "US:AAPL", "symbol": "US:MSFT", "broker_symbols": {"alpaca": "MSFT"}},
    ],
)
def test_registry_rejects_duplicate_or_ambiguous_references(second):
    with pytest.raises(ValueError, match="exactly one"):
        InstrumentRegistry((instrument(), instrument(**second)))


def test_unknown_instrument_or_broker_mapping_is_not_guessed():
    registry = demo_registry()
    with pytest.raises(ValueError, match="not registered"):
        registry.resolve("US:UNKNOWN")
    with pytest.raises(ValueError, match="no explicit mapping"):
        registry.resolve("US:AAPL", "kite")
    assert registry.annotate({"symbol": "US:UNKNOWN"}) == {
        "symbol": "US:UNKNOWN",
        "instrument_id": None,
        "instrument_identity_source": "unregistered",
        "instrument_metadata_synthetic": None,
    }


def test_configured_registry_is_available_over_mcp_and_preserves_metadata_provenance(tmp_path):
    registry_path = Path(__file__).parents[1] / "src/flyrel/data/demo-instruments.json"
    mcp, service = create_server(
        Settings(_env_file=None, state_dir=tmp_path, instrument_registry_file=registry_path)
    )

    async def run():
        _, result = await mcp.call_tool(
            "search_instruments", {"query": "reliance", "broker_id": "kite"}
        )
        assert len(result["result"]) == 2
        _, resolved = await mcp.call_tool(
            "resolve_instrument", {"identifier": "US:AAPL", "broker_id": "alpaca"}
        )
        assert resolved["instrument_id"] == "sample-us-aapl" and resolved["synthetic"]
        _, quotes = await mcp.call_tool(
            "get_quotes", {"broker_id": "paper", "symbols": ["US:AAPL"]}
        )
        quote = quotes["result"][0]
        assert quote["synthetic"] and quote["instrument_metadata_synthetic"]
        assert quote["connection_id"] == "paper" and quote["currency"] == "USD"

    try:
        asyncio.run(run())
    finally:
        service.close()
