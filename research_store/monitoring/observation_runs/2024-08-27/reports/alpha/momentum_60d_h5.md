# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.031817 |
| icir | 0.160859 |
| rank_ic_mean | 0.016400 |
| rank_icir | 0.081671 |
| rank_ic_positive_rate | 0.518868 |
| sample_days | 106.000000 |
| top_group_return_mean | 0.003380 |
| bottom_group_return_mean | -0.001762 |
| long_short_return_mean | 0.005141 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088589 |
| oos_rank_ic_mean | -0.050723 |
| oos_rank_icir | -0.249089 |
| oos_long_short_return_mean | -0.000048 |
| rank_ic_train_test_delta | -0.096149 |
| long_short_train_test_delta | -0.007434 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-05 | 74 | 0.045426 | 0.236042 | 0.007385 | 0.101351 |
| test | 2024-07-08 | 2024-08-20 | 32 | -0.050723 | -0.249089 | -0.000048 | 0.062500 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001762 |
| 2 | 0.003151 |
| 3 | -0.001188 |
| 4 | -0.001005 |
| 5 | 0.003380 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
