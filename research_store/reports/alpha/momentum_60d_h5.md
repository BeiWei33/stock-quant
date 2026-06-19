# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | -0.041767 |
| icir | -0.109434 |
| rank_ic_mean | -0.052690 |
| rank_icir | -0.159445 |
| rank_ic_positive_rate | 0.436754 |
| sample_days | 1257.000000 |
| top_group_return_mean | -0.000337 |
| bottom_group_return_mean | 0.003815 |
| long_short_return_mean | -0.004152 |
| group_monotonicity | 0.250000 |
| top_quantile_turnover_mean | 0.113887 |
| oos_rank_ic_mean | -0.042323 |
| oos_rank_icir | -0.147655 |
| oos_long_short_return_mean | -0.000242 |
| rank_ic_train_test_delta | 0.014825 |
| long_short_train_test_delta | 0.005591 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2021-04-06 | 2024-11-18 | 879 | -0.057148 | -0.164447 | -0.005833 | 0.125379 |
| test | 2024-11-19 | 2026-06-11 | 378 | -0.042323 | -0.147655 | -0.000242 | 0.089149 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | 0.003815 |
| 2 | 0.003851 |
| 3 | 0.003891 |
| 4 | -0.002593 |
| 5 | -0.000337 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
