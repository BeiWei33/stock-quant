# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.045250 |
| icir | 0.225300 |
| rank_ic_mean | 0.030701 |
| rank_icir | 0.149703 |
| rank_ic_positive_rate | 0.544643 |
| sample_days | 112.000000 |
| top_group_return_mean | 0.004173 |
| bottom_group_return_mean | -0.002600 |
| long_short_return_mean | 0.006773 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088319 |
| oos_rank_ic_mean | 0.039979 |
| oos_rank_icir | 0.195668 |
| oos_long_short_return_mean | 0.010512 |
| rank_ic_train_test_delta | 0.013323 |
| long_short_train_test_delta | 0.005370 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-11 | 78 | 0.026656 | 0.129857 | 0.005143 | 0.098291 |
| test | 2024-07-12 | 2024-08-28 | 34 | 0.039979 | 0.195668 | 0.010512 | 0.068627 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.002600 |
| 2 | 0.003294 |
| 3 | -0.000671 |
| 4 | -0.000063 |
| 5 | 0.004173 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
