# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.022424 |
| icir | 0.113368 |
| rank_ic_mean | 0.006333 |
| rank_icir | 0.031726 |
| rank_ic_positive_rate | 0.495050 |
| sample_days | 101.000000 |
| top_group_return_mean | 0.003097 |
| bottom_group_return_mean | -0.001327 |
| long_short_return_mean | 0.004424 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.089623 |
| oos_rank_ic_mean | -0.111314 |
| oos_rank_icir | -0.589988 |
| oos_long_short_return_mean | -0.005569 |
| rank_ic_train_test_delta | -0.169747 |
| long_short_train_test_delta | -0.014419 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-01 | 70 | 0.058433 | 0.322256 | 0.008850 | 0.104762 |
| test | 2024-07-02 | 2024-08-13 | 31 | -0.111314 | -0.589988 | -0.005569 | 0.043011 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001327 |
| 2 | 0.004154 |
| 3 | -0.001178 |
| 4 | -0.000955 |
| 5 | 0.003097 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
