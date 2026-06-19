# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.021286 |
| icir | 0.107256 |
| rank_ic_mean | 0.006314 |
| rank_icir | 0.031474 |
| rank_ic_positive_rate | 0.490000 |
| sample_days | 100.000000 |
| top_group_return_mean | 0.003023 |
| bottom_group_return_mean | -0.001352 |
| long_short_return_mean | 0.004375 |
| group_monotonicity | 0.500000 |
| top_quantile_turnover_mean | 0.088889 |
| oos_rank_ic_mean | -0.115298 |
| oos_rank_icir | -0.605235 |
| oos_long_short_return_mean | -0.006068 |
| rank_ic_train_test_delta | -0.173732 |
| long_short_train_test_delta | -0.014918 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-01 | 70 | 0.058433 | 0.322256 | 0.008850 | 0.104762 |
| test | 2024-07-02 | 2024-08-12 | 30 | -0.115298 | -0.605235 | -0.006068 | 0.044444 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001352 |
| 2 | 0.004157 |
| 3 | -0.000979 |
| 4 | -0.001004 |
| 5 | 0.003023 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
