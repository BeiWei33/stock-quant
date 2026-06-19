# Daily Quant Report - 2024-09-09

Source summary: `research_store\reports\daily_summary.json`

## Workflow
| Item | Value |
| --- | --- |
| Account | paper |
| Run Status | SUCCESS |
| Run ID | 438107600726428689123a8c3196ef18 |
| Summary OK | True |
| Collected Stocks | 30 |
| Collected Daily Bars | 5400 |
| Collected Benchmark Bars | 0 |
| Data Quality Level | INFO |
| Order Count | 1 |
| Rejected Orders | 0 |
| Fill Count | 1 |
| Rejected Fills | 0 |

## Health Checks
| Check | OK | Detail |
| --- | --- | --- |
| collected_stocks | True | count=30 |
| collected_daily_bars | True | count=5400 |
| data_quality_ok | True | level=INFO; report=research_store\reports\data_quality.md |
| research_report_exists | True | research_store\reports\alpha\momentum_60d_h5.md |
| orders_evaluated | True | count=1 |
| portfolio_snapshot_created | True |  |

## Portfolio
| Metric | Value |
| --- | --- |
| Total Asset | 1,006,778.13 |
| Cash | 708,586.73 |
| Market Value | 298,191.41 |
| Position Ratio | 29.62% |
| Daily Return | 0.43% |
| Cumulative Return | 0.68% |
| Drawdown | 0.00% |
| Excess Return | 0.00% |

## Orders
| Code | Side | Qty | Price | Target Weight | Status | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| 000001.SZ | BUY | 17500 | 5.71 | 10.00% | CREATED | rebalance_to_target_weight |
| 000001.SZ | BUY | 17500 | 5.71 | 10.00% | CREATED | rebalance_to_target_weight |
| 000002.SZ | BUY | 8000 | 12.49 | 10.00% | CREATED | rebalance_to_target_weight |
| 000008.SZ | BUY | 5700 | 17.50 | 10.00% | CREATED | rebalance_to_target_weight |
| 000012.SZ | BUY | 5000 | 19.71 | 10.00% | CREATED | rebalance_to_target_weight |
| 000012.SZ | SELL | 100 | 19.71 | 10.00% | FILLED | rebalance_to_target_weight |
| 000016.SZ | BUY | 8900 | 11.12 | 10.00% | CREATED | rebalance_to_target_weight |
| 000016.SZ | BUY | 8900 | 11.12 | 10.00% | CREATED | rebalance_to_target_weight |
| 000019.SZ | BUY | 8200 | 12.08 | 10.00% | CREATED | rebalance_to_target_weight |
| 000019.SZ | BUY | 8200 | 12.08 | 10.00% | CREATED | rebalance_to_target_weight |

## Fills
| Code | Side | Qty | Price | Amount | Fee | Tax |
| --- | --- | --- | --- | --- | --- | --- |
| 000001.SZ | BUY | 17500 | 5.71 | 99,906.85 | 29.97 | 0.00 |
| 000001.SZ | BUY | 17500 | 5.71 | 99,906.85 | 29.97 | 0.00 |
| 000002.SZ | BUY | 8000 | 12.49 | 99,887.88 | 29.97 | 0.00 |
| 000008.SZ | BUY | 5700 | 17.50 | 99,743.82 | 29.92 | 0.00 |
| 000012.SZ | BUY | 5000 | 19.71 | 98,559.71 | 29.57 | 0.00 |
| 000012.SZ | SELL | 100 | 19.71 | 1,971.19 | 5.00 | 0.99 |
| 000016.SZ | BUY | 8900 | 11.12 | 98,992.79 | 29.70 | 0.00 |
| 000016.SZ | BUY | 8900 | 11.12 | 98,992.79 | 29.70 | 0.00 |
| 000019.SZ | BUY | 8200 | 12.08 | 99,085.68 | 29.73 | 0.00 |
| 000019.SZ | BUY | 8200 | 12.08 | 99,085.68 | 29.73 | 0.00 |

## Risk Checks
| Code | Side | Allowed | Reasons |
| --- | --- | --- | --- |
| 000001.SZ | BUY | True |  |
| 000001.SZ | BUY | True |  |
| 000002.SZ | BUY | True |  |
| 000008.SZ | BUY | True |  |
| 000012.SZ | BUY | True |  |
| 000012.SZ | SELL | True |  |
| 000016.SZ | BUY | True |  |
| 000016.SZ | BUY | True |  |
| 000019.SZ | BUY | True |  |
| 000019.SZ | BUY | True |  |

## Reconciliation
| Report | Status | Local Count | Broker Count | Diff Count |
| --- | --- | --- | --- | --- |
| paper:2024-09-09:positions | DIFF | 2 | 2 | 1 |
| paper:2024-09-09:trades | DIFF | 6 | 3 | 3 |

## Positions
| Code | Qty | Available | Avg Cost | Market Value | Weight |
| --- | --- | --- | --- | --- | --- |
| 000001.SZ | 17500 | 17500 | 5.71 | 99,906.85 | 33.53% |
| 000002.SZ | 8000 | 8000 | 11.38 | 99,887.88 | 33.50% |
| 000008.SZ | 5700 | 5700 | 17.07 | 99,743.82 | 33.45% |
| 000019.SZ | 8200 | 8200 | 12.09 | 99,085.68 | 33.25% |
| 000016.SZ | 8900 | 8900 | 11.13 | 98,992.79 | 33.22% |
| 000012.SZ | 5000 | 5000 | 19.42 | 98,559.71 | 33.05% |

## Alpha Research
| Metric | Value |
| --- | --- |
| Factor | momentum_60d |
| Horizon | 5 |
| Quantiles | 5 |
| IC Mean | 0.0518 |
| ICIR | 0.2554 |
| Rank IC Mean | 0.0381 |
| Rank ICIR | 0.1835 |
| Rank IC Positive Rate | 55.65% |
| Sample Days | 115 |
| Top Group Return Mean | 0.46% |
| Bottom Group Return Mean | -0.34% |
| Long Short Return Mean | 0.80% |
| Group Monotonicity | 75.00% |
| Top Quantile Turnover Mean | 8.89% |
| OOS Rank IC Mean | 0.0748 |
| OOS Rank ICIR | 0.3562 |
| OOS Long Short Return Mean | 1.59% |
| Rank IC Train/Test Delta | 0.0528 |

## Artifacts
| Artifact | Path |
| --- | --- |
| Research JSON | research_store\reports\alpha\momentum_60d_h5.json |
| Research Markdown | research_store\reports\alpha\momentum_60d_h5.md |
| Data Quality JSON | research_store\reports\data_quality.json |
| Data Quality Markdown | research_store\reports\data_quality.md |
| Daily Summary | research_store\reports\daily_summary.json |
| Paper SQLite | research_store\paper_trading.sqlite3 |
