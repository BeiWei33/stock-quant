# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.024690 |
| icir | 0.124609 |
| rank_ic_mean | 0.008292 |
| rank_icir | 0.041545 |
| rank_ic_positive_rate | 0.500000 |
| sample_days | 102.000000 |
| top_group_return_mean | 0.003107 |
| bottom_group_return_mean | -0.001453 |
| long_short_return_mean | 0.004560 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.090343 |
| oos_rank_ic_mean | -0.108170 |
| oos_rank_icir | -0.560259 |
| oos_long_short_return_mean | -0.005650 |
| rank_ic_train_test_delta | -0.167313 |
| long_short_train_test_delta | -0.014668 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-02 | 71 | 0.059142 | 0.328310 | 0.009018 | 0.105634 |
| test | 2024-07-03 | 2024-08-14 | 31 | -0.108170 | -0.560259 | -0.005650 | 0.043011 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001453 |
| 2 | 0.004059 |
| 3 | -0.001309 |
| 4 | -0.000854 |
| 5 | 0.003107 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
