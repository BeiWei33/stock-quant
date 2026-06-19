# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.025988 |
| icir | 0.131511 |
| rank_ic_mean | 0.008953 |
| rank_icir | 0.045048 |
| rank_ic_positive_rate | 0.504854 |
| sample_days | 103.000000 |
| top_group_return_mean | 0.003054 |
| bottom_group_return_mean | -0.001519 |
| long_short_return_mean | 0.004574 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.089506 |
| oos_rank_ic_mean | -0.105242 |
| oos_rank_icir | -0.539295 |
| oos_long_short_return_mean | -0.005614 |
| rank_ic_train_test_delta | -0.163363 |
| long_short_train_test_delta | -0.014574 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-03 | 72 | 0.058120 | 0.324524 | 0.008960 | 0.104167 |
| test | 2024-07-04 | 2024-08-15 | 31 | -0.105242 | -0.539295 | -0.005614 | 0.048387 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.001519 |
| 2 | 0.003933 |
| 3 | -0.001383 |
| 4 | -0.000802 |
| 5 | 0.003054 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
