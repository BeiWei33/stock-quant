# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.039025 |
| icir | 0.195213 |
| rank_ic_mean | 0.023608 |
| rank_icir | 0.116238 |
| rank_ic_positive_rate | 0.532110 |
| sample_days | 109.000000 |
| top_group_return_mean | 0.003917 |
| bottom_group_return_mean | -0.001885 |
| long_short_return_mean | 0.005801 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.087719 |
| oos_rank_ic_mean | -0.000667 |
| oos_rank_icir | -0.003282 |
| oos_long_short_return_mean | 0.004953 |
| rank_ic_train_test_delta | -0.034816 |
| long_short_train_test_delta | -0.001217 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-09 | 76 | 0.034149 | 0.168973 | 0.006170 | 0.100877 |
| test | 2024-07-10 | 2024-08-23 | 33 | -0.000667 | -0.003282 | 0.004953 | 0.060606 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001885 |
| 2 | 0.003013 |
| 3 | -0.001302 |
| 4 | -0.000539 |
| 5 | 0.003917 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
