# 每日量化报告 - 2026-06-18

> 数据源说明：AkShare 真实 A 股行情。通过 AkShare 获取公开 A 股行情数据，仅用于研究和模拟盘，不代表已经接入实盘交易。

来源摘要：`research_store\reports\daily_summary.json`

## 流程概览
| 项目 | 值 |
| --- | --- |
| 账户 | paper |
| 运行状态 | SUCCESS |
| 运行 ID | 88f319347cc842458aee4701d577a563 |
| 摘要是否正常 | True |
| 股票数 | 10 |
| 日线数量 | 1690 |
| 基准日线数量 | 0 |
| 数据质量级别 | WARNING |
| 订单数 | 10 |
| 拒绝订单数 | 0 |
| 成交数 | 10 |
| 拒绝成交数 | 0 |

## 健康检查
| 检查项 | 通过 | 详情 |
| --- | --- | --- |
| collected_stocks | True | count=10 |
| collected_daily_bars | True | count=1690 |
| data_quality_ok | True | level=WARNING; report=research_store\reports\data_quality.md |
| research_report_exists | True | research_store\reports\alpha\momentum_60d_h5.md |
| orders_evaluated | True | count=10 |
| portfolio_snapshot_created | True |  |

## 组合资产
| 指标 | 值 |
| --- | --- |
| 总资产 | 1,150,486.60 |
| 现金 | 662,404.70 |
| 市值 | 488,081.90 |
| 仓位比例 | 42.42% |
| 日收益 | 14.27% |
| 累计收益 | 15.05% |
| 回撤 | 0.00% |
| 超额收益 | 0.00% |

## 订单
| 代码 | 方向 | 数量 | 价格 | 目标权重 | 状态 | 原因 |
| --- | --- | --- | --- | --- | --- | --- |
| 000001.SZ | SELL | 17500 | 10.52 | 0.00% | FILLED | rebalance_to_target_weight |
| 000002.SZ | SELL | 8000 | 3.06 | 0.00% | FILLED | rebalance_to_target_weight |
| 000008.SZ | SELL | 5700 | 2.45 | 0.00% | FILLED | rebalance_to_target_weight |
| 000012.SZ | SELL | 5000 | 4.30 | 0.00% | FILLED | rebalance_to_target_weight |
| 002962.SZ | BUY | 2900 | 17.29 | 5.00% | FILLED | rebalance_to_target_weight |
| 002963.SZ | BUY | 2500 | 19.49 | 5.00% | FILLED | rebalance_to_target_weight |
| 002965.SZ | BUY | 1100 | 43.92 | 5.00% | FILLED | rebalance_to_target_weight |
| 002971.SZ | BUY | 700 | 67.38 | 5.00% | FILLED | rebalance_to_target_weight |
| 301596.SZ | BUY | 800 | 59.74 | 5.00% | FILLED | rebalance_to_target_weight |
| 600030.SH | BUY | 1800 | 26.56 | 5.00% | FILLED | rebalance_to_target_weight |

## 成交
| 代码 | 方向 | 数量 | 价格 | 金额 | 手续费 | 税费 |
| --- | --- | --- | --- | --- | --- | --- |
| 000001.SZ | SELL | 17500 | 10.52 | 184,100.00 | 55.23 | 92.05 |
| 000002.SZ | SELL | 8000 | 3.06 | 24,480.00 | 7.34 | 12.24 |
| 000008.SZ | SELL | 5700 | 2.45 | 13,965.00 | 5.00 | 6.98 |
| 000012.SZ | SELL | 5000 | 4.30 | 21,500.00 | 6.45 | 10.75 |
| 002962.SZ | BUY | 2900 | 17.29 | 50,141.00 | 15.04 | 0.00 |
| 002963.SZ | BUY | 2500 | 19.49 | 48,725.00 | 14.62 | 0.00 |
| 002965.SZ | BUY | 1100 | 43.92 | 48,312.00 | 14.49 | 0.00 |
| 002971.SZ | BUY | 700 | 67.38 | 47,166.00 | 14.15 | 0.00 |
| 301596.SZ | BUY | 800 | 59.74 | 47,792.00 | 14.34 | 0.00 |
| 600030.SH | BUY | 1800 | 26.56 | 47,808.00 | 14.34 | 0.00 |

## 风控检查
| 代码 | 方向 | 是否允许 | 原因 |
| --- | --- | --- | --- |
| 000001.SZ | SELL | True |  |
| 000002.SZ | SELL | True |  |
| 000008.SZ | SELL | True |  |
| 000012.SZ | SELL | True |  |
| 002962.SZ | BUY | True |  |
| 002963.SZ | BUY | True |  |
| 002965.SZ | BUY | True |  |
| 002971.SZ | BUY | True |  |
| 301596.SZ | BUY | True |  |
| 600030.SH | BUY | True |  |

## 对账
_没有记录对账报告。_

## 持仓
| 代码 | 数量 | 可用数量 | 平均成本 | 市值 | 权重 |
| --- | --- | --- | --- | --- | --- |
| 000019.SZ | 8200 | 8200 | 12.09 | 99,115.41 | 20.31% |
| 000016.SZ | 8900 | 8900 | 11.13 | 99,022.49 | 20.29% |
| 002962.SZ | 2900 | 2900 | 17.30 | 50,141.00 | 10.27% |
| 002963.SZ | 2500 | 2500 | 19.50 | 48,725.00 | 9.98% |
| 002965.SZ | 1100 | 1100 | 43.93 | 48,312.00 | 9.90% |
| 600030.SH | 1800 | 1800 | 26.57 | 47,808.00 | 9.80% |
| 301596.SZ | 800 | 800 | 59.76 | 47,792.00 | 9.79% |
| 002971.SZ | 700 | 700 | 67.40 | 47,166.00 | 9.66% |

## Alpha 研究
| 指标 | 值 |
| --- | --- |
| 因子 | momentum_60d |
| 持有期 | 5 |
| 分组数 | 5 |
| IC 均值 | -0.0418 |
| ICIR | -0.1094 |
| Rank IC 均值 | -0.0527 |
| Rank ICIR | -0.1594 |
| Rank IC 为正比例 | 43.68% |
| 样本天数 | 1,257 |
| 最高组平均收益 | -0.03% |
| 最低组平均收益 | 0.38% |
| 多空平均收益 | -0.42% |
| 分组单调性 | 25.00% |
| 最高分位换手率 | 11.39% |
| 样本外 Rank IC 均值 | -0.0423 |
| 样本外 Rank ICIR | -0.1477 |
| 样本外多空收益 | -0.02% |
| Rank IC 训练/测试差异 | 0.0148 |

## 产物
| 产物 | 路径 |
| --- | --- |
| 研究 JSON | research_store\reports\alpha\momentum_60d_h5.json |
| 研究 Markdown | research_store\reports\alpha\momentum_60d_h5.md |
| 数据质量 JSON | research_store\reports\data_quality.json |
| 数据质量 Markdown | research_store\reports\data_quality.md |
| 日摘要 | research_store\reports\daily_summary.json |
| 纸面账户 SQLite | research_store\paper_trading.sqlite3 |
