from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from quant.core.collector.base import CollectionResult
from quant.core.collector.base import MarketDataSource
from quant.core.collector.normalization import normalize_daily_bars, normalize_stocks


DEFAULT_A_SHARE_SYMBOLS: tuple[str, ...] = (
    "600519.SH",  # 贵州茅台
    "000001.SZ",  # 平安银行
    "300750.SZ",  # 宁德时代
    "601318.SH",  # 中国平安
    "000858.SZ",  # 五粮液
    "600036.SH",  # 招商银行
    "601899.SH",  # 紫金矿业
    "002594.SZ",  # 比亚迪
    "600276.SH",  # 恒瑞医药
    "600030.SH",  # 中信证券
    "601398.SH",  # 工商银行
    "601088.SH",  # 中国神华
    "600309.SH",  # 万华化学
    "600887.SH",  # 伊利股份
    "600900.SH",  # 长江电力
    "601012.SH",  # 隆基绿能
    "002415.SZ",  # 海康威视
    "000002.SZ",  # 万科A
    "000333.SZ",  # 美的集团
    "000568.SZ",  # 泸州老窖
    "000651.SZ",  # 格力电器
    "002352.SZ",  # 顺丰控股
    "002714.SZ",  # 牧原股份
    "300059.SZ",  # 东方财富
    "300124.SZ",  # 汇川技术
    "300760.SZ",  # 迈瑞医疗
    "000008.SZ",  # 神州高铁
    "000012.SZ",  # 南玻A
    "600438.SH",  # 通威股份
    "601166.SH",  # 兴业银行
)


@dataclass(frozen=True)
class AkShareDataSourceConfig:
    symbols: tuple[str, ...] = DEFAULT_A_SHARE_SYMBOLS
    max_symbols: int | None = None
    all_market: bool = False
    retry_count: int = 3
    retry_sleep_seconds: float = 1.0
    chunk_days: int = 366


class AkShareDataSource(MarketDataSource):
    source_name = "akshare"

    def __init__(
        self,
        config: AkShareDataSourceConfig | None = None,
        *,
        ak_module: object | None = None,
    ) -> None:
        self.config = config or AkShareDataSourceConfig()
        self._stocks_cache: pd.DataFrame | None = None
        if ak_module is not None:
            self.ak = ak_module
            return
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "akshare is not installed. Install it with `pip install akshare` first."
            ) from exc
        self.ak = ak

    def collect(self, start_date: date | None = None, end_date: date | None = None) -> CollectionResult:
        stocks = self.fetch_stocks()
        daily_bars = self.fetch_daily_bars(start_date, end_date)
        if self.config.all_market and self.config.max_symbols is not None:
            collected_codes = list(dict.fromkeys(daily_bars["ts_code"].astype(str)))
            stocks = _filter_symbols(stocks, tuple(collected_codes))
            order = {ts_code: index for index, ts_code in enumerate(collected_codes)}
            stocks = (
                stocks.assign(_order=stocks["ts_code"].map(order))
                .sort_values("_order")
                .drop(columns=["_order"])
                .reset_index(drop=True)
            )
        return CollectionResult(
            stocks=stocks,
            daily_bars=daily_bars,
            benchmark_bars=self.fetch_benchmark_bars(start_date, end_date),
        )

    def fetch_stocks(self) -> pd.DataFrame:
        if self._stocks_cache is not None:
            return self._stocks_cache.copy()
        raw = self.ak.stock_info_a_code_name()
        raw["exchange"] = raw["code"].map(lambda code: "SH" if str(code).startswith("6") else "SZ")
        raw["list_date"] = pd.NaT
        raw["status"] = "listed"
        stocks = normalize_stocks(raw.rename(columns={"code": "ts_code"}), self.source_name)
        if not self.config.all_market:
            stocks = _filter_symbols(stocks, self.config.symbols)
        else:
            stocks = _prioritize_symbols(stocks, DEFAULT_A_SHARE_SYMBOLS)
        if self.config.max_symbols is not None and not self.config.all_market:
            stocks = stocks.head(max(0, self.config.max_symbols))
        if stocks.empty:
            raise RuntimeError("akshare returned no stocks for the configured symbols")
        self._stocks_cache = stocks.reset_index(drop=True)
        return self._stocks_cache.copy()

    def fetch_daily_bars(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        if start_date is None or end_date is None:
            raise ValueError("akshare daily collection requires start_date and end_date")
        stocks = self.fetch_stocks()
        frames: list[pd.DataFrame] = []
        errors: list[str] = []
        successful_symbols = 0
        for row in stocks.itertuples(index=False):
            symbol = row.ts_code.split(".")[0]
            symbol_frames: list[pd.DataFrame] = []
            for chunk_start, chunk_end in _date_chunks(
                start_date,
                end_date,
                max_days=max(30, self.config.chunk_days),
            ):
                try:
                    raw = self._fetch_hist_with_retry(symbol, row.ts_code, chunk_start, chunk_end)
                except Exception as exc:  # pragma: no cover - depends on remote provider behavior
                    errors.append(f"{row.ts_code} {chunk_start}~{chunk_end}: {exc}")
                    continue
                if raw.empty:
                    continue
                raw["ts_code"] = row.ts_code
                symbol_frames.append(normalize_daily_bars(raw, self.source_name, adj_type="qfq"))
            if symbol_frames:
                frames.append(pd.concat(symbol_frames, ignore_index=True))
                successful_symbols += 1
                if self.config.all_market and self.config.max_symbols is not None:
                    if successful_symbols >= max(0, self.config.max_symbols):
                        break
        if frames:
            return pd.concat(frames, ignore_index=True)
        detail = f"; first_error={errors[0]}" if errors else ""
        raise RuntimeError(f"akshare returned no daily bars{detail}")

    def _fetch_hist_with_retry(
        self,
        symbol: str,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        attempts = max(1, self.config.retry_count)
        for attempt in range(attempts):
            try:
                return self._fetch_hist_once(symbol, ts_code, start_date, end_date)
            except Exception as exc:  # pragma: no cover - depends on remote provider behavior
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(max(0.0, self.config.retry_sleep_seconds))
        assert last_error is not None
        raise last_error

    def _fetch_hist_once(
        self,
        symbol: str,
        ts_code: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        primary_error: Exception | None = None
        try:
            return self.ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
        except Exception as exc:  # pragma: no cover - depends on remote provider behavior
            primary_error = exc
        fallback = getattr(self.ak, "stock_zh_a_daily", None)
        if fallback is None:
            assert primary_error is not None
            raise primary_error
        try:
            return fallback(
                symbol=_akshare_daily_symbol(ts_code),
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
        except TypeError:
            return fallback(
                symbol=_akshare_daily_symbol(ts_code),
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )


def _date_chunks(start_date: date, end_date: date, *, max_days: int) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(end_date, cursor + timedelta(days=max_days - 1))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _akshare_daily_symbol(ts_code: str) -> str:
    code, suffix = ts_code.split(".", 1)
    prefix = "sh" if suffix.upper() == "SH" else "bj" if suffix.upper() == "BJ" else "sz"
    return f"{prefix}{code}"


def _filter_symbols(stocks: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    if not symbols:
        return stocks
    normalized = {_normalize_symbol(symbol) for symbol in symbols}
    return stocks[stocks["ts_code"].isin(normalized)].copy()


def _prioritize_symbols(stocks: pd.DataFrame, symbols: tuple[str, ...]) -> pd.DataFrame:
    priority = {_normalize_symbol(symbol): index for index, symbol in enumerate(symbols)}
    ordered = stocks.copy()
    ordered["_priority"] = ordered["ts_code"].map(priority).fillna(len(priority))
    return ordered.sort_values(["_priority", "ts_code"]).drop(columns=["_priority"]).reset_index(drop=True)


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." in text:
        code, suffix = text.split(".", 1)
        return f"{code.zfill(6)}.{suffix}"
    suffix = "SH" if text.startswith(("6", "9")) else "BJ" if text.startswith(("8", "4")) else "SZ"
    return f"{text.zfill(6)}.{suffix}"
