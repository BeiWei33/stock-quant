from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Callable
from urllib.request import Request, urlopen as stdlib_urlopen

import pandas as pd

from quant.core.collector.akshare_source import DEFAULT_A_SHARE_SYMBOLS
from quant.core.collector.base import CollectionResult, MarketDataSource
from quant.core.collector.normalization import normalize_daily_bars, normalize_stocks


UrlOpen = Callable[..., object]


@dataclass(frozen=True)
class TencentDataSourceConfig:
    symbols: tuple[str, ...] = DEFAULT_A_SHARE_SYMBOLS
    max_symbols: int | None = None
    all_market: bool = False
    timeout_seconds: float = 15.0


class TencentDataSource(MarketDataSource):
    source_name = "tencent"

    def __init__(
        self,
        config: TencentDataSourceConfig | None = None,
        *,
        urlopen: UrlOpen | None = None,
    ) -> None:
        self.config = config or TencentDataSourceConfig()
        self._urlopen = urlopen or stdlib_urlopen
        self._name_cache: dict[str, str] = {}
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
            self._stocks_cache = self._fetch_full_market_stocks()
            return self._stocks_cache.copy()
        rows = [
            {
                "ts_code": ts_code,
                "name": self._name_cache.get(ts_code, ts_code),
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
            raise ValueError("tencent daily collection requires start_date and end_date")
        frames: list[pd.DataFrame] = []
        errors: list[str] = []
        for ts_code in self._symbols():
            try:
                payload = self._fetch_kline_payload(ts_code, start_date, end_date)
                frame = self._payload_to_daily_bars(ts_code, payload)
            except Exception as exc:  # pragma: no cover - remote provider details vary.
                errors.append(f"{ts_code}: {exc}")
                continue
            if not frame.empty:
                frames.append(frame)
        if frames:
            return pd.concat(frames, ignore_index=True)
        detail = f"; first_error={errors[0]}" if errors else ""
        raise RuntimeError(f"tencent returned no daily bars{detail}")

    def _symbols(self) -> tuple[str, ...]:
        if self.config.all_market:
            return tuple(self.fetch_stocks()["ts_code"])
        symbols = tuple(_normalize_symbol(symbol) for symbol in self.config.symbols)
        if self.config.max_symbols is not None:
            symbols = symbols[: max(0, self.config.max_symbols)]
        if not symbols:
            raise RuntimeError("tencent daily source requires at least one symbol")
        return symbols

    def _fetch_full_market_stocks(self) -> pd.DataFrame:
        url = (
            "https://82.push2.eastmoney.com/api/qt/clist/get"
            "?pn=1&pz=6000&po=1&np=1&fltt=2&invt=2&fid=f3"
            "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
            "&fields=f12,f14"
        )
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            },
        )
        response = self._urlopen(request, timeout=self.config.timeout_seconds)
        payload = _loads_json_or_jsonp(response.read().decode("utf-8", errors="replace"))
        records = payload.get("data", {}).get("diff") or []
        rows = []
        for item in records:
            code = str(item.get("f12", "")).strip()
            if not code:
                continue
            ts_code = _normalize_symbol(code)
            name = str(item.get("f14") or ts_code)
            self._name_cache[ts_code] = name
            rows.append(
                {
                    "ts_code": ts_code,
                    "name": name,
                    "exchange": ts_code.split(".")[-1],
                    "industry": "UNKNOWN",
                    "list_date": pd.NaT,
                    "status": "listed",
                }
            )
        if self.config.max_symbols is not None:
            rows = rows[: max(0, self.config.max_symbols)]
        if not rows:
            raise RuntimeError("tencent full-market universe returned no stocks")
        return normalize_stocks(pd.DataFrame(rows), self.source_name)

    def _fetch_kline_payload(self, ts_code: str, start_date: date, end_date: date) -> dict:
        market_symbol = _tencent_symbol(ts_code)
        url = (
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={market_symbol},day,{start_date.isoformat()},{end_date.isoformat()},640,qfq"
        )
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://gu.qq.com/",
            },
        )
        response = self._urlopen(request, timeout=self.config.timeout_seconds)
        text = response.read().decode("utf-8", errors="replace")
        return _loads_json_or_jsonp(text)

    def _payload_to_daily_bars(self, ts_code: str, payload: dict) -> pd.DataFrame:
        market_symbol = _tencent_symbol(ts_code)
        node = payload.get("data", {}).get(market_symbol, {})
        if not isinstance(node, dict):
            raise RuntimeError("unexpected tencent kline payload")
        quote = (node.get("qt") or {}).get(market_symbol)
        if isinstance(quote, list) and len(quote) > 1 and quote[1]:
            self._name_cache[ts_code] = str(quote[1])
        rows = node.get("qfqday") or node.get("day") or []
        raw_rows = []
        for item in rows:
            if len(item) < 6:
                continue
            raw_rows.append(
                {
                    "ts_code": ts_code,
                    "trade_date": item[0],
                    "open": item[1],
                    "close": item[2],
                    "high": item[3],
                    "low": item[4],
                    "volume": item[5],
                    "amount": item[6] if len(item) > 6 else pd.NA,
                }
            )
        if not raw_rows:
            return pd.DataFrame()
        return normalize_daily_bars(pd.DataFrame(raw_rows), self.source_name, adj_type="qfq")


def _loads_json_or_jsonp(text: str) -> dict:
    payload = text.strip()
    if not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("tencent response is not a JSON object")
    return data


def _tencent_symbol(ts_code: str) -> str:
    code, suffix = ts_code.split(".", 1)
    prefix = "sh" if suffix.upper() == "SH" else "bj" if suffix.upper() == "BJ" else "sz"
    return f"{prefix}{code}"


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." in text:
        code, suffix = text.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    suffix = "SH" if text.startswith(("6", "9")) else "BJ" if text.startswith(("8", "4")) else "SZ"
    return f"{text.zfill(6)}.{suffix}"
