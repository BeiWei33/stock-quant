# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.020436 |
| icir | 0.101185 |
| rank_ic_mean | 0.008825 |
| rank_icir | 0.043373 |
| rank_ic_positive_rate | 0.489583 |
| sample_days | 96.000000 |
| top_group_return_mean | 0.002652 |
| bottom_group_return_mean | -0.001219 |
| long_short_return_mean | 0.003870 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.085809 |
| oos_rank_ic_mean | -0.076629 |
| oos_rank_icir | -0.320377 |
| oos_long_short_return_mean | -0.003346 |
| rank_ic_train_test_delta | -0.122441 |
| long_short_train_test_delta | -0.010340 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-06-26 | 67 | 0.045812 | 0.264401 | 0.006994 | 0.104478 |
| test | 2024-06-27 | 2024-08-06 | 29 | -0.076629 | -0.320377 | -0.003346 | 0.051724 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001219 |
| 2 | 0.003553 |
| 3 | -0.001593 |
| 4 | -0.000352 |
| 5 | 0.002652 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
