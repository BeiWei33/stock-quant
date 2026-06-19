# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.020907 |
| icir | 0.104840 |
| rank_ic_mean | 0.006209 |
| rank_icir | 0.030797 |
| rank_ic_positive_rate | 0.484848 |
| sample_days | 99.000000 |
| top_group_return_mean | 0.002969 |
| bottom_group_return_mean | -0.001353 |
| long_short_return_mean | 0.004321 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088141 |
| oos_rank_ic_mean | -0.103330 |
| oos_rank_icir | -0.494832 |
| oos_long_short_return_mean | -0.004429 |
| rank_ic_train_test_delta | -0.157164 |
| long_short_train_test_delta | -0.012555 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-06-28 | 69 | 0.053834 | 0.301533 | 0.008126 | 0.106280 |
| test | 2024-07-01 | 2024-08-09 | 30 | -0.103330 | -0.494832 | -0.004429 | 0.038889 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001353 |
| 2 | 0.004257 |
| 3 | -0.001222 |
| 4 | -0.000920 |
| 5 | 0.002969 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
