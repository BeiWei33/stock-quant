from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import date
from typing import Callable

import pandas as pd

from quant.core.collector.akshare_source import DEFAULT_A_SHARE_SYMBOLS
from quant.core.collector.base import CollectionResult, MarketDataSource
from quant.core.collector.normalization import filter_by_date, normalize_daily_bars, normalize_stocks
from quant.core.collector.tencent_source import TencentDataSource, TencentDataSourceConfig


ClientFactory = Callable[[], object]


TDX_SERVERS: tuple[tuple[str, int], ...] = (
    ("119.97.185.59", 7709),
    ("124.70.133.119", 7709),
    ("116.205.183.150", 7709),
    ("123.60.73.44", 7709),
    ("116.205.163.254", 7709),
    ("121.36.225.169", 7709),
    ("123.60.70.228", 7709),
    ("124.71.9.153", 7709),
    ("110.41.147.114", 7709),
    ("124.71.187.122", 7709),
)


@dataclass(frozen=True)
class MootdxDataSourceConfig:
    symbols: tuple[str, ...] = DEFAULT_A_SHARE_SYMBOLS
    max_symbols: int | None = None
    all_market: bool = False
    max_bars_per_symbol: int = 800
    probe_timeout_seconds: float = 1.5


class MootdxDataSource(MarketDataSource):
    source_name = "mootdx"

    def __init__(
        self,
        config: MootdxDataSourceConfig | None = None,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.config = config or MootdxDataSourceConfig()
        self._client_factory = client_factory or self._default_client_factory
        self._client: object | None = None
        self._stocks_cache: pd.DataFrame | None = None

    def collect(self, start_date: date | None = None, end_date: date | None = None) -> CollectionResult:
        daily_bars = self.fetch_daily_bars(start_date=start_date, end_date=end_date)
        return CollectionResult(
            stocks=self.fetch_stocks(),
            daily_bars=daily_bars,
            benchmark_bars=self.fetch_benchmark_bars(start_date, end_date),
        )

    def fetch_stocks(self) -> pd.DataFrame:
        if self._stocks_cache is not None:
            return self._stocks_cache.copy()
        if self.config.all_market:
            stocks = TencentDataSource(
                TencentDataSourceConfig(max_symbols=self.config.max_symbols, all_market=True),
            ).fetch_stocks()
            stocks = stocks.assign(source=self.source_name)
            self._stocks_cache = stocks
            return stocks.copy()
        rows = [
            {
                "ts_code": ts_code,
                "name": ts_code,
                "exchange": ts_code.split(".")[-1],
                "industry": "UNKNOWN",
                "list_date": pd.NaT,
                "status": "listed",
            }
            for ts_code in self._symbols()
        ]
        self._stocks_cache = normalize_stocks(pd.DataFrame(rows), self.source_name)
        return self._stocks_cache.copy()

    def fetch_daily_bars(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        if start_date is None or end_date is None:
            raise ValueError("mootdx daily collection requires start_date and end_date")
        frames: list[pd.DataFrame] = []
        errors: list[str] = []
        client = self._get_client()
        for ts_code in self._symbols():
            try:
                raw = client.bars(
                    symbol=ts_code.split(".")[0],
                    category=4,
                    offset=max(1, self.config.max_bars_per_symbol),
                )
                frame = self._normalize_bars(ts_code, raw)
                frame = filter_by_date(frame, start_date, end_date)
            except Exception as exc:  # pragma: no cover - remote provider details vary.
                errors.append(f"{ts_code}: {exc}")
                continue
            if not frame.empty:
                frames.append(frame)
        if frames:
            return pd.concat(frames, ignore_index=True)
        detail = f"; first_error={errors[0]}" if errors else ""
        raise RuntimeError(f"mootdx returned no daily bars{detail}")

    def _symbols(self) -> tuple[str, ...]:
        if self.config.all_market:
            return tuple(self.fetch_stocks()["ts_code"])
        symbols = tuple(_normalize_symbol(symbol) for symbol in self.config.symbols)
        if self.config.max_symbols is not None:
            symbols = symbols[: max(0, self.config.max_symbols)]
        if not symbols:
            raise RuntimeError("mootdx daily source requires at least one symbol")
        return symbols

    def _normalize_bars(self, ts_code: str, raw: object) -> pd.DataFrame:
        df = pd.DataFrame(raw)
        if df.empty:
            return pd.DataFrame()
        date_col = "datetime" if "datetime" in df.columns else "date" if "date" in df.columns else "trade_date"
        volume_col = "vol" if "vol" in df.columns else "volume"
        amount_col = "amount" if "amount" in df.columns else None
        rows = pd.DataFrame(
            {
                "ts_code": ts_code,
                "trade_date": df[date_col],
                "open": df["open"],
                "high": df["high"],
                "low": df["low"],
                "close": df["close"],
                "volume": df[volume_col],
                "amount": df[amount_col] if amount_col else pd.NA,
            }
        )
        return normalize_daily_bars(rows, self.source_name, adj_type="qfq")

    def _get_client(self) -> object:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _default_client_factory(self) -> object:
        try:
            from mootdx.quotes import Quotes  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("mootdx is not installed. Install it with `pip install mootdx`.") from exc
        for ip, port in TDX_SERVERS:
            if _probe(ip, port, timeout=self.config.probe_timeout_seconds):
                return Quotes.factory(market="std", server=(ip, port))
        try:
            return Quotes.factory(market="std", bestip=True)
        except Exception as exc:
            raise RuntimeError("all mootdx servers are unavailable") from exc


def _probe(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." in text:
        code, suffix = text.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    suffix = "SH" if text.startswith(("6", "9")) else "BJ" if text.startswith(("8", "4")) else "SZ"
    return f"{text.zfill(6)}.{suffix}"
