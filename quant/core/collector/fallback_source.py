from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from quant.core.collector.base import CollectionResult, MarketDataSource


@dataclass(frozen=True)
class FallbackAttempt:
    source_name: str
    status: str
    error: str = ""


class FallbackMarketDataSource(MarketDataSource):
    source_name = "auto"

    def __init__(self, sources: list[MarketDataSource]) -> None:
        if not sources:
            raise ValueError("fallback source requires at least one market data source")
        self.sources = sources
        self.attempts: list[FallbackAttempt] = []

    def fetch_stocks(self):  # pragma: no cover - collect owns the fallback behavior.
        raise NotImplementedError("use collect() so stocks and bars come from the same source")

    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None):
        raise NotImplementedError("use collect() so stocks and bars come from the same source")

    def collect(self, start_date: date | None = None, end_date: date | None = None) -> CollectionResult:
        self.attempts = []
        errors: list[str] = []
        for source in self.sources:
            name = getattr(source, "source_name", source.__class__.__name__)
            try:
                result = source.collect(start_date=start_date, end_date=end_date)
                if result.daily_bars.empty:
                    raise RuntimeError("source returned no daily bars")
                self.attempts.append(FallbackAttempt(name, "OK"))
                return result
            except Exception as exc:
                error = str(exc)
                self.attempts.append(FallbackAttempt(name, "FAIL", error))
                errors.append(f"{name}: {error}")
        raise RuntimeError("all market data sources failed; " + "; ".join(errors))


class LazyMarketDataSource(MarketDataSource):
    def __init__(self, source_name: str, factory: Callable[[], MarketDataSource]) -> None:
        self.source_name = source_name
        self._factory = factory
        self._source: MarketDataSource | None = None

    def fetch_stocks(self):  # pragma: no cover - delegated through collect.
        return self._get_source().fetch_stocks()

    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None):
        return self._get_source().fetch_daily_bars(start_date, end_date)

    def collect(self, start_date: date | None = None, end_date: date | None = None) -> CollectionResult:
        return self._get_source().collect(start_date=start_date, end_date=end_date)

    def _get_source(self) -> MarketDataSource:
        if self._source is None:
            self._source = self._factory()
        return self._source
