# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.028203 |
| icir | 0.142481 |
| rank_ic_mean | 0.011526 |
| rank_icir | 0.057773 |
| rank_ic_positive_rate | 0.509615 |
| sample_days | 104.000000 |
| top_group_return_mean | 0.003054 |
| bottom_group_return_mean | -0.001646 |
| long_short_return_mean | 0.004700 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088685 |
| oos_rank_ic_mean | -0.093312 |
| oos_rank_icir | -0.459130 |
| oos_long_short_return_mean | -0.004886 |
| rank_ic_train_test_delta | -0.151432 |
| long_short_train_test_delta | -0.013846 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-03 | 72 | 0.058120 | 0.324524 | 0.008960 | 0.104167 |
| test | 2024-07-04 | 2024-08-16 | 32 | -0.093312 | -0.459130 | -0.004886 | 0.052083 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001646 |
| 2 | 0.003687 |
| 3 | -0.001366 |
| 4 | -0.000843 |
| 5 | 0.003054 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
