from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from quant.core.data.repository import close_price_matrix


@dataclass(frozen=True)
class AlphaValidationResult:
    factor_name: str
    horizon: int
    quantiles: int
    summary: dict[str, float]
    split_summary: dict[str, dict[str, float | str]]
    ic_by_date: pd.DataFrame
    group_returns: pd.DataFrame
    turnover: pd.DataFrame

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_name": self.factor_name,
            "horizon": self.horizon,
            "quantiles": self.quantiles,
            "summary": self.summary,
            "split_summary": self.split_summary,
            "ic_by_date": self.ic_by_date.to_dict(orient="records"),
            "group_returns": self.group_returns.to_dict(orient="records"),
            "turnover": self.turnover.to_dict(orient="records"),
        }


def forward_returns(bars: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    close = close_price_matrix(bars)
    returns = close.shift(-horizon) / close - 1.0
    return returns.stack().rename("forward_return").reset_index()


def ic_by_date(factor_values: pd.DataFrame, forward_return_values: pd.DataFrame, factor_name: str) -> pd.DataFrame:
    merged = _merge_factor_forward_return(factor_values, forward_return_values, factor_name)
    rows: list[dict[str, object]] = []
    for trade_date, group in merged.groupby("trade_date"):
        if len(group) < 2:
            continue
        ic = group[factor_name].corr(group["forward_return"])
        rank_ic = group[factor_name].rank().corr(group["forward_return"].rank())
        rows.append({"trade_date": trade_date, "ic": ic, "rank_ic": rank_ic, "count": len(group)})
    return pd.DataFrame(rows)


def rank_ic_by_date(factor_values: pd.DataFrame, forward_return_values: pd.DataFrame, factor_name: str) -> pd.Series:
    ic_frame = ic_by_date(factor_values, forward_return_values, factor_name)
    if ic_frame.empty:
        return pd.Series(dtype=float, name="rank_ic")
    return ic_frame.set_index("trade_date")["rank_ic"]


def group_forward_returns(
    factor_values: pd.DataFrame,
    forward_return_values: pd.DataFrame,
    factor_name: str,
    quantiles: int = 5,
) -> pd.DataFrame:
    merged = _merge_factor_forward_return(factor_values, forward_return_values, factor_name)
    if merged.empty:
        return pd.DataFrame(columns=["trade_date", "quantile", "mean_forward_return", "count"])

    frames = [_assign_quantile(group, factor_name, quantiles) for _, group in merged.groupby("trade_date")]
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    merged = merged.dropna(subset=["quantile"])
    if merged.empty:
        return pd.DataFrame(columns=["trade_date", "quantile", "mean_forward_return", "count"])

    grouped = (
        merged.groupby(["trade_date", "quantile"], as_index=False)
        .agg(mean_forward_return=("forward_return", "mean"), count=("ts_code", "count"))
        .sort_values(["trade_date", "quantile"])
    )
    grouped["quantile"] = grouped["quantile"].astype(int)
    return grouped.reset_index(drop=True)


def quantile_turnover(
    factor_values: pd.DataFrame,
    factor_name: str,
    quantile: int,
    quantiles: int = 5,
) -> pd.DataFrame:
    if factor_values.empty:
        return pd.DataFrame(columns=["trade_date", "turnover", "selected_count"])

    frames = [
        _assign_quantile(group, factor_name, quantiles)
        for _, group in factor_values.dropna(subset=[factor_name]).groupby("trade_date")
    ]
    assigned = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if assigned.empty:
        return pd.DataFrame(columns=["trade_date", "turnover", "selected_count"])
    assigned = assigned[assigned["quantile"] == quantile].sort_values("trade_date")

    rows: list[dict[str, object]] = []
    previous: set[str] | None = None
    for trade_date, group in assigned.groupby("trade_date"):
        current = set(group["ts_code"])
        if previous is None or not current:
            turnover = 0.0
        else:
            turnover = 1.0 - len(current & previous) / max(len(current), 1)
        rows.append({"trade_date": trade_date, "turnover": turnover, "selected_count": len(current)})
        previous = current
    return pd.DataFrame(rows)


def alpha_summary(ic_frame: pd.DataFrame | pd.Series, group_returns: pd.DataFrame | None = None) -> dict[str, float]:
    if isinstance(ic_frame, pd.Series):
        rank_ic = ic_frame.dropna()
        ic = pd.Series(dtype=float)
    elif ic_frame.empty:
        rank_ic = pd.Series(dtype=float)
        ic = pd.Series(dtype=float)
    else:
        rank_ic = ic_frame["rank_ic"].dropna()
        ic = ic_frame["ic"].dropna()

    summary = {
        "ic_mean": float(ic.mean()) if not ic.empty else 0.0,
        "icir": _mean_over_std(ic),
        "rank_ic_mean": float(rank_ic.mean()) if not rank_ic.empty else 0.0,
        "rank_icir": _mean_over_std(rank_ic),
        "rank_ic_positive_rate": float((rank_ic > 0).mean()) if not rank_ic.empty else 0.0,
        "sample_days": float(len(rank_ic)),
    }

    if group_returns is not None and not group_returns.empty:
        by_quantile = group_returns.groupby("quantile")["mean_forward_return"].mean()
        low = by_quantile.get(int(by_quantile.index.min()), 0.0)
        high = by_quantile.get(int(by_quantile.index.max()), 0.0)
        summary["top_group_return_mean"] = float(high)
        summary["bottom_group_return_mean"] = float(low)
        summary["long_short_return_mean"] = float(high - low)
        summary["group_monotonicity"] = _monotonicity_score(by_quantile)
    else:
        summary["top_group_return_mean"] = 0.0
        summary["bottom_group_return_mean"] = 0.0
        summary["long_short_return_mean"] = 0.0
        summary["group_monotonicity"] = 0.0
    return summary


def validate_factor(
    bars: pd.DataFrame,
    factor_values: pd.DataFrame,
    factor_name: str,
    horizon: int = 5,
    quantiles: int = 5,
    train_ratio: float = 0.70,
) -> AlphaValidationResult:
    fwd = forward_returns(bars, horizon=horizon)
    ic_frame = ic_by_date(factor_values, fwd, factor_name)
    groups = group_forward_returns(factor_values, fwd, factor_name, quantiles=quantiles)
    turnover = quantile_turnover(factor_values, factor_name, quantile=quantiles, quantiles=quantiles)
    summary = alpha_summary(ic_frame, groups)
    summary["top_quantile_turnover_mean"] = (
        float(turnover["turnover"].mean()) if not turnover.empty else 0.0
    )
    split_summary = split_alpha_summary(
        ic_frame=ic_frame,
        group_returns=groups,
        turnover=turnover,
        train_ratio=train_ratio,
    )
    summary.update(_stability_summary(split_summary))
    return AlphaValidationResult(
        factor_name=factor_name,
        horizon=horizon,
        quantiles=quantiles,
        summary=summary,
        split_summary=split_summary,
        ic_by_date=_serialize_dates(ic_frame),
        group_returns=_serialize_dates(groups),
        turnover=_serialize_dates(turnover),
    )


def split_alpha_summary(
    *,
    ic_frame: pd.DataFrame,
    group_returns: pd.DataFrame,
    turnover: pd.DataFrame,
    train_ratio: float = 0.70,
) -> dict[str, dict[str, float | str]]:
    if ic_frame.empty or "trade_date" not in ic_frame.columns:
        empty = _empty_split_summary()
        return {"train": empty, "test": empty}

    dates = sorted(pd.to_datetime(ic_frame["trade_date"]).dt.date.unique())
    split_index = _split_index(len(dates), train_ratio)
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    return {
        "train": _period_summary("train", train_dates, ic_frame, group_returns, turnover),
        "test": _period_summary("test", test_dates, ic_frame, group_returns, turnover),
    }


def _merge_factor_forward_return(
    factor_values: pd.DataFrame,
    forward_return_values: pd.DataFrame,
    factor_name: str,
) -> pd.DataFrame:
    if factor_name not in factor_values.columns:
        raise ValueError(f"factor_values missing factor column: {factor_name}")
    if "forward_return" not in forward_return_values.columns:
        raise ValueError("forward_returns must contain forward_return")
    merged = factor_values[["trade_date", "ts_code", factor_name]].merge(
        forward_return_values[["trade_date", "ts_code", "forward_return"]],
        on=["trade_date", "ts_code"],
        how="inner",
    )
    return merged.dropna(subset=[factor_name, "forward_return"])


def _split_index(size: int, train_ratio: float) -> int:
    if size <= 1:
        return size
    ratio = min(max(train_ratio, 0.10), 0.90)
    return min(max(1, int(size * ratio)), size - 1)


def _period_summary(
    label: str,
    dates: set[object],
    ic_frame: pd.DataFrame,
    group_returns: pd.DataFrame,
    turnover: pd.DataFrame,
) -> dict[str, float | str]:
    if not dates:
        return _empty_split_summary(label)
    ic = _filter_dates(ic_frame, dates)
    groups = _filter_dates(group_returns, dates)
    period_turnover = _filter_dates(turnover, dates)
    summary = alpha_summary(ic, groups)
    summary["top_quantile_turnover_mean"] = (
        float(period_turnover["turnover"].mean()) if not period_turnover.empty else 0.0
    )
    summary["start_date"] = min(dates).isoformat() if hasattr(min(dates), "isoformat") else str(min(dates))
    summary["end_date"] = max(dates).isoformat() if hasattr(max(dates), "isoformat") else str(max(dates))
    summary["period"] = label
    return summary


def _filter_dates(df: pd.DataFrame, dates: set[object]) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df.copy()
    result = df.copy()
    date_values = pd.to_datetime(result["trade_date"]).dt.date
    return result[date_values.isin(dates)].reset_index(drop=True)


def _empty_split_summary(label: str = "") -> dict[str, float | str]:
    return {
        "period": label,
        "start_date": "",
        "end_date": "",
        "ic_mean": 0.0,
        "icir": 0.0,
        "rank_ic_mean": 0.0,
        "rank_icir": 0.0,
        "rank_ic_positive_rate": 0.0,
        "sample_days": 0.0,
        "top_group_return_mean": 0.0,
        "bottom_group_return_mean": 0.0,
        "long_short_return_mean": 0.0,
        "group_monotonicity": 0.0,
        "top_quantile_turnover_mean": 0.0,
    }


def _stability_summary(split_summary: dict[str, dict[str, float | str]]) -> dict[str, float]:
    train = split_summary.get("train", {})
    test = split_summary.get("test", {})
    return {
        "oos_rank_ic_mean": _float_metric(test.get("rank_ic_mean")),
        "oos_rank_icir": _float_metric(test.get("rank_icir")),
        "oos_long_short_return_mean": _float_metric(test.get("long_short_return_mean")),
        "rank_ic_train_test_delta": _float_metric(test.get("rank_ic_mean")) - _float_metric(train.get("rank_ic_mean")),
        "long_short_train_test_delta": _float_metric(test.get("long_short_return_mean"))
        - _float_metric(train.get("long_short_return_mean")),
    }


def _float_metric(value: object) -> float:
    if value is None:
        return 0.0
    return float(value)


def _assign_quantile(group: pd.DataFrame, factor_name: str, quantiles: int) -> pd.DataFrame:
    result = group.copy()
    valid = result[factor_name].dropna()
    if len(valid) < quantiles:
        result["quantile"] = pd.NA
        return result
    try:
        result.loc[valid.index, "quantile"] = pd.qcut(
            valid.rank(method="first"),
            q=quantiles,
            labels=False,
        ) + 1
    except ValueError:
        result["quantile"] = pd.NA
    return result


def _mean_over_std(series: pd.Series) -> float:
    series = series.dropna()
    if series.empty:
        return 0.0
    std = series.std(ddof=0)
    return float(series.mean() / std) if std > 0 else 0.0


def _monotonicity_score(by_quantile: pd.Series) -> float:
    if len(by_quantile) < 2:
        return 0.0
    diffs = by_quantile.sort_index().diff().dropna()
    if diffs.empty:
        return 0.0
    direction = 1.0 if by_quantile.iloc[-1] >= by_quantile.iloc[0] else -1.0
    return float(((diffs * direction) >= 0).mean())


def _serialize_dates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df
    result = df.copy()
    result["trade_date"] = result["trade_date"].map(lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value))
    return result
