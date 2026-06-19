# Alpha Research Report: momentum_60d

## Setup

- Factor: `momentum_60d`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.046591 |
| icir | 0.232425 |
| rank_ic_mean | 0.032542 |
| rank_icir | 0.158666 |
| rank_ic_positive_rate | 0.548673 |
| sample_days | 113.000000 |
| top_group_return_mean | 0.004186 |
| bottom_group_return_mean | -0.002851 |
| long_short_return_mean | 0.007037 |
| group_monotonicity | 0.750000 |
| top_quantile_turnover_mean | 0.087571 |
| oos_rank_ic_mean | 0.051037 |
| oos_rank_icir | 0.249445 |
| oos_long_short_return_mean | 0.011933 |
| rank_ic_train_test_delta | 0.026456 |
| long_short_train_test_delta | 0.007003 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-12 | 79 | 0.024581 | 0.120031 | 0.004930 | 0.099156 |
| test | 2024-07-15 | 2024-08-29 | 34 | 0.051037 | 0.249445 | 0.011933 | 0.063725 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | -0.002851 |
| 2 | 0.003463 |
| 3 | -0.000669 |
| 4 | 0.000096 |
| 5 | 0.004186 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
