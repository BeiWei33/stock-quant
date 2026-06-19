# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.043352 |
| icir | 0.215958 |
| rank_ic_mean | 0.028522 |
| rank_icir | 0.139333 |
| rank_ic_positive_rate | 0.540541 |
| sample_days | 111.000000 |
| top_group_return_mean | 0.004099 |
| bottom_group_return_mean | -0.002307 |
| long_short_return_mean | 0.006406 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.087644 |
| oos_rank_ic_mean | 0.027023 |
| oos_rank_icir | 0.133038 |
| oos_long_short_return_mean | 0.008472 |
| rank_ic_train_test_delta | -0.002160 |
| long_short_train_test_delta | 0.002978 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-10 | 77 | 0.029184 | 0.142087 | 0.005494 | 0.099567 |
| test | 2024-07-11 | 2024-08-27 | 34 | 0.027023 | 0.133038 | 0.008472 | 0.063725 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.002307 |
| 2 | 0.003298 |
| 3 | -0.000924 |
| 4 | -0.000164 |
| 5 | 0.004099 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
