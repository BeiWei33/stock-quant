from __future__ import annotations

from datetime import date

import pandas as pd

from quant.core.data.quality import add_basic_quality_flags


def normalize_stocks(df: pd.DataFrame, source: str) -> pd.DataFrame:
    normalized = df.rename(
        columns={
            "代码": "ts_code",
            "名称": "name",
            "证券代码": "ts_code",
            "证券简称": "name",
            "交易所": "exchange",
            "所属行业": "industry",
            "上市日期": "list_date",
            "退市日期": "delist_date",
            "ts_code": "ts_code",
            "symbol": "ts_code",
            "name": "name",
            "exchange": "exchange",
            "industry": "industry",
            "list_date": "list_date",
            "delist_date": "delist_date",
            "is_st": "is_st",
            "status": "status",
        }
    ).copy()
    normalized["ts_code"] = normalized["ts_code"].map(_normalize_ts_code)
    normalized["name"] = normalized.get("name", normalized["ts_code"]).fillna(normalized["ts_code"])
    normalized["exchange"] = _series_or_default(
        normalized, "exchange", normalized["ts_code"].map(_exchange_from_code)
    )
    normalized["industry"] = _series_or_default(normalized, "industry", "UNKNOWN").fillna("UNKNOWN")
    normalized["list_date"] = pd.to_datetime(
        _series_or_default(normalized, "list_date", pd.NaT), errors="coerce"
    ).dt.date
    normalized["delist_date"] = pd.to_datetime(
        _series_or_default(normalized, "delist_date", pd.NaT), errors="coerce"
    ).dt.date
    normalized["is_st"] = normalized.get("is_st", normalized["name"].astype(str).str.contains("ST")).fillna(False)
    normalized["status"] = normalized.get("status", "listed").fillna("listed")
    normalized["source"] = source
    return normalized[
        [
            "ts_code",
            "name",
            "exchange",
            "industry",
            "list_date",
            "delist_date",
            "is_st",
            "status",
            "source",
        ]
    ].drop_duplicates("ts_code")


def normalize_daily_bars(df: pd.DataFrame, source: str, adj_type: str = "qfq") -> pd.DataFrame:
    normalized = df.rename(
        columns={
            "代码": "ts_code",
            "日期": "trade_date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "昨收": "pre_close",
            "成交量": "volume",
            "成交额": "amount",
            "股票代码": "ts_code",
            "交易日期": "trade_date",
            "date": "trade_date",
            "vol": "volume",
            "trade_date": "trade_date",
            "ts_code": "ts_code",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "pre_close": "pre_close",
            "volume": "volume",
            "amount": "amount",
        }
    ).copy()
    normalized["ts_code"] = normalized["ts_code"].map(_normalize_ts_code)
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"]).dt.date
    normalized["adj_type"] = _series_or_default(normalized, "adj_type", adj_type).fillna(adj_type)
    normalized["pre_close"] = _series_or_default(normalized, "pre_close", pd.NA)
    normalized["source"] = source
    normalized["quality_flag"] = _series_or_default(normalized, "quality_flag", "NORMAL")

    for column in ["open", "high", "low", "close", "pre_close", "volume", "amount"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = add_basic_quality_flags(normalized)
    return normalized[
        [
            "ts_code",
            "trade_date",
            "adj_type",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "volume",
            "amount",
            "source",
            "quality_flag",
        ]
    ].drop_duplicates(["ts_code", "trade_date", "adj_type"])


def normalize_benchmark_bars(df: pd.DataFrame, source: str, benchmark_code: str) -> pd.DataFrame:
    normalized = df.rename(
        columns={
            "日期": "trade_date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "trade_date": "trade_date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
    ).copy()
    normalized["benchmark_code"] = benchmark_code
    normalized["trade_date"] = pd.to_datetime(normalized["trade_date"]).dt.date
    normalized["source"] = source
    for column in ["open", "high", "low", "close", "volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized[
        ["benchmark_code", "trade_date", "open", "high", "low", "close", "volume", "source"]
    ].drop_duplicates(["benchmark_code", "trade_date"])


def filter_by_date(df: pd.DataFrame, start_date: date | None, end_date: date | None) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df
    result = df.copy()
    if start_date is not None:
        result = result[result["trade_date"] >= start_date]
    if end_date is not None:
        result = result[result["trade_date"] <= end_date]
    return result.reset_index(drop=True)


def _normalize_ts_code(value: object) -> str:
    text = str(value).strip()
    if "." in text:
        code, suffix = text.split(".", 1)
        return f"{code.zfill(6)}.{suffix.upper()}"
    if text.startswith(("6", "9")):
        return f"{text.zfill(6)}.SH"
    if text.startswith(("8", "4")):
        return f"{text.zfill(6)}.BJ"
    return f"{text.zfill(6)}.SZ"


def _exchange_from_code(ts_code: str) -> str:
    if ts_code.endswith(".SH"):
        return "SH"
    if ts_code.endswith(".BJ"):
        return "BJ"
    return "SZ"


def _series_or_default(df: pd.DataFrame, column: str, default: object) -> pd.Series:
    if column in df.columns:
        return df[column]
    if isinstance(default, pd.Series):
        return default
    return pd.Series([default] * len(df), index=df.index)
