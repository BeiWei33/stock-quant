# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.033542 |
| icir | 0.169687 |
| rank_ic_mean | 0.017820 |
| rank_icir | 0.088925 |
| rank_ic_positive_rate | 0.523364 |
| sample_days | 107.000000 |
| top_group_return_mean | 0.003601 |
| bottom_group_return_mean | -0.001681 |
| long_short_return_mean | 0.005282 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.089286 |
| oos_rank_ic_mean | -0.044083 |
| oos_rank_icir | -0.216078 |
| oos_long_short_return_mean | 0.000565 |
| rank_ic_train_test_delta | -0.089508 |
| long_short_train_test_delta | -0.006820 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-05 | 74 | 0.045426 | 0.236042 | 0.007385 | 0.101351 |
| test | 2024-07-08 | 2024-08-21 | 33 | -0.044083 | -0.216078 | 0.000565 | 0.065657 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001681 |
| 2 | 0.003042 |
| 3 | -0.001259 |
| 4 | -0.001076 |
| 5 | 0.003601 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
