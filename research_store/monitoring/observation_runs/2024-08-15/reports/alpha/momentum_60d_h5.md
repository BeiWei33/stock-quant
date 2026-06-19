# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.019858 |
| icir | 0.099208 |
| rank_ic_mean | 0.005979 |
| rank_icir | 0.029510 |
| rank_ic_positive_rate | 0.479592 |
| sample_days | 98.000000 |
| top_group_return_mean | 0.002864 |
| bottom_group_return_mean | -0.001296 |
| long_short_return_mean | 0.004161 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.087379 |
| oos_rank_ic_mean | -0.088869 |
| oos_rank_icir | -0.384260 |
| oos_long_short_return_mean | -0.003034 |
| rank_ic_train_test_delta | -0.136693 |
| long_short_train_test_delta | -0.010369 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-06-27 | 68 | 0.047824 | 0.276800 | 0.007335 | 0.105392 |
| test | 2024-06-28 | 2024-08-08 | 30 | -0.088869 | -0.384260 | -0.003034 | 0.044444 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001296 |
| 2 | 0.004188 |
| 3 | -0.001434 |
| 4 | -0.000871 |
| 5 | 0.002864 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
