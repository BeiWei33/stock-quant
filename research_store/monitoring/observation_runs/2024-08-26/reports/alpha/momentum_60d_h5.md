# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.030135 |
| icir | 0.152214 |
| rank_ic_mean | 0.014414 |
| rank_icir | 0.071811 |
| rank_ic_positive_rate | 0.514286 |
| sample_days | 105.000000 |
| top_group_return_mean | 0.003252 |
| bottom_group_return_mean | -0.001729 |
| long_short_return_mean | 0.004980 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.087879 |
| oos_rank_ic_mean | -0.071607 |
| oos_rank_icir | -0.343431 |
| oos_long_short_return_mean | -0.002409 |
| rank_ic_train_test_delta | -0.123729 |
| long_short_train_test_delta | -0.010629 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-04 | 73 | 0.052122 | 0.281737 | 0.008220 | 0.102740 |
| test | 2024-07-05 | 2024-08-19 | 32 | -0.071607 | -0.343431 | -0.002409 | 0.057292 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001729 |
| 2 | 0.003419 |
| 3 | -0.001286 |
| 4 | -0.000937 |
| 5 | 0.003252 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
