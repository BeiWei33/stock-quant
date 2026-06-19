# Alpha Research Report: quality_score

## Setup

- Factor: `quality_score`
- Forward return horizon: `5` trading days
- Quantiles: `5`

## Summary

| Metric | Value |
| --- | ---: |
| ic_mean | 0.013557 |
| icir | 0.094096 |
| rank_ic_mean | 0.011606 |
| rank_icir | 0.081372 |
| rank_ic_positive_rate | 0.591304 |
| sample_days | 115.000000 |
| top_group_return_mean | 0.002283 |
| bottom_group_return_mean | 0.000638 |
| long_short_return_mean | 0.001646 |
| group_monotonicity | 0.250000 |
| top_quantile_turnover_mean | 0.133333 |
| oos_rank_ic_mean | -0.005536 |
| oos_rank_icir | -0.037688 |
| oos_long_short_return_mean | 0.002236 |
| rank_ic_train_test_delta | -0.024641 |
| long_short_train_test_delta | 0.000849 |

## Train/Test Split

| Period | Start | End | Days | Rank IC Mean | Rank ICIR | Long Short Mean | Turnover |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| train | 2024-03-26 | 2024-07-15 | 80 | 0.019106 | 0.136397 | 0.001387 | 0.112500 |
| test | 2024-07-16 | 2024-09-02 | 35 | -0.005536 | -0.037688 | 0.002236 | 0.185714 |

## Average Group Forward Return

| Quantile | Mean Return |
| ---: | ---: |
| 1 | 0.000638 |
| 2 | -0.000358 |
| 3 | -0.000516 |
| 4 | 0.002458 |
| 5 | 0.002283 |

## Review Notes

- This report is a statistical research artifact, not a production approval.
- A factor should still pass out-of-sample checks, cost checks, and benchmark comparison before paper trading.
- Negative or unstable Rank IC should trigger review rather than automatic deployment.
