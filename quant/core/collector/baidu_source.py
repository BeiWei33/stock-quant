from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen as stdlib_urlopen

import pandas as pd

from quant.core.collector.akshare_source import DEFAULT_A_SHARE_SYMBOLS
from quant.core.collector.base import CollectionResult, MarketDataSource
from quant.core.collector.normalization import filter_by_date, normalize_daily_bars, normalize_stocks
from quant.core.collector.tencent_source import TencentDataSource, TencentDataSourceConfig


UrlOpen = Callable[..., object]


@dataclass(frozen=True)
class BaiduDataSourceConfig:
    symbols: tuple[str, ...] = DEFAULT_A_SHARE_SYMBOLS
    max_symbols: int | None = None
    all_market: bool = False
    timeout_seconds: float = 10.0


class BaiduDataSource(MarketDataSource):
    source_name = "baidu"

    def __init__(
        self,
        config: BaiduDataSourceConfig | None = None,
        *,
        urlopen: UrlOpen | None = None,
    ) -> None:
        self.config = config or BaiduDataSourceConfig()
        self._urlopen = urlopen or stdlib_urlopen
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
                TencentDataSourceConfig(
                    max_symbols=self.config.max_symbols,
                    all_market=True,
                    timeout_seconds=self.config.timeout_seconds,
                ),
                urlopen=self._urlopen,
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
            raise ValueError("baidu daily collection requires start_date and end_date")
        frames: list[pd.DataFrame] = []
        errors: list[str] = []
        for ts_code in self._symbols():
            try:
                payload = self._fetch_kline_payload(ts_code)
                frame = self._payload_to_daily_bars(ts_code, payload)
                frame = filter_by_date(frame, start_date, end_date)
            except Exception as exc:  # pragma: no cover - remote provider details vary.
                errors.append(f"{ts_code}: {exc}")
                continue
            if not frame.empty:
                frames.append(frame)
        if frames:
            return pd.concat(frames, ignore_index=True)
        detail = f"; first_error={errors[0]}" if errors else ""
        raise RuntimeError(f"baidu returned no daily bars{detail}")

    def _symbols(self) -> tuple[str, ...]:
        if self.config.all_market:
            return tuple(self.fetch_stocks()["ts_code"])
        symbols = tuple(_normalize_symbol(symbol) for symbol in self.config.symbols)
        if self.config.max_symbols is not None:
            symbols = symbols[: max(0, self.config.max_symbols)]
        if not symbols:
            raise RuntimeError("baidu daily source requires at least one symbol")
        return symbols

    def _fetch_kline_payload(self, ts_code: str) -> dict:
        params = {
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": ts_code.split(".")[0],
            "start_time": "",
            "ktype": "1",
        }
        url = "https://finance.pae.baidu.com/selfselect/getstockquotation?" + urlencode(params)
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/vnd.finance-web.v1+json",
                "Origin": "https://gushitong.baidu.com",
                "Referer": "https://gushitong.baidu.com/",
            },
        )
        response = self._urlopen(request, timeout=self.config.timeout_seconds)
        return _loads_json_or_jsonp(response.read().decode("utf-8", errors="replace"))

    def _payload_to_daily_bars(self, ts_code: str, payload: dict) -> pd.DataFrame:
        market_data = payload.get("Result", {}).get("newMarketData", {})
        keys = [str(item).lower() for item in market_data.get("keys", [])]
        rows_text = str(market_data.get("marketData", "") or "")
        if not keys or not rows_text:
            return pd.DataFrame()
        raw_rows = []
        for row_text in rows_text.split(";"):
            if not row_text.strip():
                continue
            values = row_text.split(",")
            row = {key: values[index] for index, key in enumerate(keys) if index < len(values)}
            raw_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": _first_present(row, ("date", "time", "datetime", "day")),
                    "open": _first_present(row, ("open", "openprice")),
                    "close": _first_present(row, ("close", "closeprice", "price")),
                    "high": _first_present(row, ("high", "highprice")),
                    "low": _first_present(row, ("low", "lowprice")),
                    "volume": _first_present(row, ("volume", "vol")),
                    "amount": _first_present(row, ("amount", "turnover")),
                }
            )
        if not raw_rows:
            return pd.DataFrame()
        return normalize_daily_bars(pd.DataFrame(raw_rows), self.source_name, adj_type="qfq")


def _first_present(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _loads_json_or_jsonp(text: str) -> dict:
    payload = text.strip()
    if not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("baidu response is not a JSON object")
    return data


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." in text:
        code, suffix = text.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    suffix = "SH" if text.startswith(("6", "9")) else "BJ" if text.startswith(("8", "4")) else "SZ"
    return f"{text.zfill(6)}.{suffix}"
