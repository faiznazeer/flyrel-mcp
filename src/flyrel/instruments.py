"""Explicit local identities, never a guessed broker master or security equivalence map."""

from pathlib import Path

from pydantic import Field

from flyrel.models import Instrument, Model


class InstrumentCatalog(Model):
    instruments: tuple[Instrument, ...] = Field(default=(), max_length=10000)


class InstrumentRegistry:
    def __init__(self, instruments: tuple[Instrument, ...] = ()):
        self._by_id = {}
        self._by_symbol = {}
        broker_keys = set()
        identifiers = set()
        for instrument in instruments:
            references = {instrument.instrument_id, instrument.symbol}
            if instrument.instrument_id == instrument.symbol or references & identifiers:
                raise ValueError("Instrument IDs and symbols must identify exactly one entry")
            identifiers.update(references)
            for mapping in instrument.broker_symbols.items():
                if mapping in broker_keys:
                    raise ValueError("Duplicate broker symbol mapping")
                broker_keys.add(mapping)
            self._by_id[instrument.instrument_id] = instrument
            self._by_symbol[instrument.symbol] = instrument

    @classmethod
    def load(cls, path: Path | None):
        if path is None:
            return cls()
        return cls(InstrumentCatalog.model_validate_json(path.read_text()).instruments)

    def find(self, symbol: str) -> Instrument | None:
        return self._by_symbol.get(symbol)

    def resolve(self, identifier: str, broker_id: str | None = None) -> Instrument:
        instrument = self._by_id.get(identifier) or self._by_symbol.get(identifier)
        if instrument is None:
            raise ValueError("Instrument is not registered")
        if broker_id is not None and broker_id not in instrument.broker_symbols:
            raise ValueError("Instrument has no explicit mapping for this broker")
        return instrument

    def search(self, query: str, broker_id: str | None = None, limit: int = 20) -> list[Instrument]:
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        needle = query.casefold().strip()
        return [
            instrument
            for instrument in self._by_id.values()
            if (broker_id is None or broker_id in instrument.broker_symbols)
            and any(
                needle in value.casefold()
                for value in (instrument.instrument_id, instrument.symbol, instrument.name)
            )
        ][:limit]

    def annotate(self, row: dict) -> dict:
        instrument = self.find(row["symbol"])
        return {
            **row,
            "instrument_id": instrument.instrument_id if instrument else None,
            "instrument_identity_source": instrument.source if instrument else "unregistered",
            "instrument_metadata_synthetic": instrument.synthetic if instrument else None,
        }
