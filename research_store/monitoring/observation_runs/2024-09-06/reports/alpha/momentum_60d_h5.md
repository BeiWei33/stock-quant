# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.048645 |
| icir | 0.242299 |
| rank_ic_mean | 0.034740 |
| rank_icir | 0.169031 |
| rank_ic_positive_rate | 0.552632 |
| sample_days | 114.000000 |
| top_group_return_mean | 0.004354 |
| bottom_group_return_mean | -0.003139 |
| long_short_return_mean | 0.007492 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.088235 |
| oos_rank_ic_mean | 0.057670 |
| oos_rank_icir | 0.280861 |
| oos_long_short_return_mean | 0.013276 |
| rank_ic_train_test_delta | 0.033089 |
| long_short_train_test_delta | 0.008346 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-12 | 79 | 0.024581 | 0.120031 | 0.004930 | 0.099156 |
| test | 2024-07-15 | 2024-08-30 | 35 | 0.057670 | 0.280861 | 0.013276 | 0.061905 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.003139 |
| 2 | 0.003652 |
| 3 | -0.000662 |
| 4 | 0.000111 |
| 5 | 0.004354 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
