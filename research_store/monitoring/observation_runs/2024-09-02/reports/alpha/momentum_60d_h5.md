# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.040815 |
| icir | 0.204203 |
| rank_ic_mean | 0.025479 |
| rank_icir | 0.125439 |
| rank_ic_positive_rate | 0.536364 |
| sample_days | 110.000000 |
| top_group_return_mean | 0.004037 |
| bottom_group_return_mean | -0.002069 |
| long_short_return_mean | 0.006106 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.086957 |
| oos_rank_ic_mean | 0.016834 |
| oos_rank_icir | 0.085261 |
| oos_long_short_return_mean | 0.007535 |
| rank_ic_train_test_delta | -0.012350 |
| long_short_train_test_delta | 0.002042 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-10 | 77 | 0.029184 | 0.142087 | 0.005494 | 0.099567 |
| test | 2024-07-11 | 2024-08-26 | 33 | 0.016834 | 0.085261 | 0.007535 | 0.060606 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.002069 |
| 2 | 0.003213 |
| 3 | -0.001112 |
| 4 | -0.000366 |
| 5 | 0.004037 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
