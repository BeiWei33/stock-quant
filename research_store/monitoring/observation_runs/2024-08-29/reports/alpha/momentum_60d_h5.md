# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.036306 |
| icir | 0.182612 |
| rank_ic_mean | 0.020331 |
| rank_icir | 0.101074 |
| rank_ic_positive_rate | 0.527778 |
| sample_days | 108.000000 |
| top_group_return_mean | 0.003793 |
| bottom_group_return_mean | -0.001711 |
| long_short_return_mean | 0.005504 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088496 |
| oos_rank_ic_mean | -0.022078 |
| oos_rank_icir | -0.110646 |
| oos_long_short_return_mean | 0.003053 |
| rank_ic_train_test_delta | -0.061070 |
| long_short_train_test_delta | -0.003530 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-08 | 75 | 0.038991 | 0.195924 | 0.006582 | 0.100000 |
| test | 2024-07-09 | 2024-08-22 | 33 | -0.022078 | -0.110646 | 0.003053 | 0.065657 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001711 |
| 2 | 0.002948 |
| 3 | -0.001411 |
| 4 | -0.000863 |
| 5 | 0.003793 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
