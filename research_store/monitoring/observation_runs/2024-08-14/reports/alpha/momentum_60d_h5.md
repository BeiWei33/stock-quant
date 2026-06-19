# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.019459 |
| icir | 0.096738 |
| rank_ic_mean | 0.006608 |
| rank_icir | 0.032459 |
| rank_ic_positive_rate | 0.484536 |
| sample_days | 97.000000 |
| top_group_return_mean | 0.002749 |
| bottom_group_return_mean | -0.001199 |
| long_short_return_mean | 0.003948 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.086601 |
| oos_rank_ic_mean | -0.080949 |
| oos_rank_icir | -0.342552 |
| oos_long_short_return_mean | -0.002856 |
| rank_ic_train_test_delta | -0.126761 |
| long_short_train_test_delta | -0.009849 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-06-26 | 67 | 0.045812 | 0.264401 | 0.006994 | 0.104478 |
| test | 2024-06-27 | 2024-08-07 | 30 | -0.080949 | -0.342552 | -0.002856 | 0.050000 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001199 |
| 2 | 0.003783 |
| 3 | -0.001532 |
| 4 | -0.000676 |
| 5 | 0.002749 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
