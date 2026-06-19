# Personal Quant System V1.0 技术设计文档

本文档是个人 A股中低频量化交易系统的主设计文档。系统目标是先完成一条稳定闭环：

**数据采集 -> Alpha 研究 -> 因子计算 -> Benchmark 对比 -> 回测验证 -> 组合管理 -> 风控检查 -> 模拟盘 -> 小资金实盘**

V1.0 不追求高频、不追求复杂 AI、不追求全市场全周期覆盖。第一目标是验证系统闭环和 Alpha 研究能力，等系统稳定后再进入小资金实盘。

# 一、系统目标

## 1.1 V1 范围

```text
市场：A股
周期：日线
频率：中低频
策略：多因子选股 + 趋势过滤 + 组合管理
交易：先系统验证和模拟盘，稳定后再小资金实盘
部署：本地开发 + VPS/本机挂机
语言：Python 为主，Rust 渐进式增强
预算：0~100 元/月优先
```

## 1.2 V1 不做什么

```text
不做毫秒级高频
不做盘口做市
不做复杂多模型 AI Agent
不做全市场期货/期权/加密货币统一框架
不一开始重写券商网关
不依赖网页自动点击或模拟鼠标
```

## 1.3 V1 成功标准

| 指标 | 目标 |
| --- | --- |
| 数据完整性 | 日线数据可追溯、可校验 |
| 回测能力 | 支持多因子、组合调仓、费用和滑点 |
| Alpha 研究 | 每个上线因子都有研究假设、验证报告和淘汰标准 |
| Benchmark | 策略必须对比沪深300、中证500、中证1000等基准 |
| 模拟盘 | 连续运行 20 个交易日无重大异常 |
| 实盘方式 | 系统稳定后再小资金、低频、可人工接管 |
| 系统稳定性 | 交易日任务成功率 99%+ |
| 风控 | 单股、行业、组合回撤均有硬约束 |

收益指标可以作为观察目标，但不作为 V1 唯一成功标准：

| 指标 | 观察目标 |
| --- | --- |
| 年化收益 | 15%-25% |
| 最大回撤 | <15% |
| Sharpe | >1.0 |
| 持仓数量 | 10-20 只 |
| 换手率 | 中低频 |

# 二、总体架构

## 2.1 主流程

```text
AKShare / Tushare Free
        |
        v
Data Service
数据采集、清洗、复权、质量标记
        |
        v
PostgreSQL
历史行情、因子、信号、订单、持仓
        |
        v
Research Engine
因子计算、样本筛选、研究分析
        |
        v
Backtest Engine
组合回测、费用滑点、调仓模拟
        |
        v
Portfolio Engine
目标持仓、调仓计划、行业约束
        |
        v
Risk Engine
事前风控、组合约束、异常拦截
        |
        v
Execution Adapter
QMT / 券商接口 / 人工确认
        |
        v
Broker
```

## 2.2 Python 与 Rust 分工

Python 是 V1 主系统，负责业务逻辑和研究迭代：

1. 数据采集编排。
2. 因子开发。
3. 策略生成。
4. 回测编排。
5. 组合管理。
6. 业务风控规则。
7. 实盘流程控制。
8. 报表、监控、复盘。

Rust 是渐进式增强模块，优先负责边界清晰、性能敏感、失败可回退的部分：

1. 数据清洗 CLI。
2. K线去重、排序、校验。
3. 批量指标计算。
4. 回测数据预处理。
5. 调度器。
6. 硬风控安全阀。

V1 不建议 Rust 直接接管券商报单主链路和行情网关主链路。报单和网关是实盘敏感模块，异常状态复杂，应在系统稳定后再评估。

## 2.3 事件总线预留

V1 先定义统一事件模型，不强制引入复杂消息中间件。早期可以同步调用，后续再升级为 Redis Stream 或本地事件总线。

基础事件结构：

```python
class Event:
    event_id: str
    event_type: str
    event_time: str
    receive_time: str
    source: str
    payload: dict
```

核心事件：

1. SignalEvent。
2. RiskCheckEvent。
3. OrderIntentEvent。
4. OrderEvent。
5. TradeEvent。
6. PositionEvent。
7. PortfolioSnapshotEvent。
8. SystemEvent。

事件总线的目标是让策略、风控、执行、监控之间的状态可追踪、可审计、可扩展。

# 三、项目目录

```text
quant/
  apps/
    collector/          # 数据采集任务
    backtest/           # 回测入口
    trader/             # 模拟盘/实盘入口
    monitor/            # 监控与报表

  core/
    data/               # 数据访问、清洗编排
    universe/           # 股票池管理
    research/           # Alpha 研究、因子验证、研究报告
    factor/             # 因子
    strategy/           # 策略
    portfolio/          # 组合管理
    risk/               # Python 业务风控
      china_market/     # A股特殊规则：T+1、涨跌停、停牌、ST等
    execution/          # QMT/券商适配层
    event_bus/          # 统一事件模型，V1先定义接口
    ai/                 # V1 仅预留

  rust_core/
    crates/
      data_cleaner/     # 数据清洗
      bar_builder/      # K线聚合
      indicator_engine/ # 批量指标
      risk_guard/       # 硬风控安全阀
      scheduler/        # 定时调度

  database/
    migrations/
    seeds/

  config/
  notebooks/
  scripts/
  tests/
  docker/
  logs/
  research_store/
    feature_store/      # 预处理特征
    factor_matrix/      # Parquet 因子矩阵
    reports/            # Alpha 研究报告
```

# 四、数据库设计

V1 推荐 PostgreSQL。若预算或维护压力很低，也可以先用 SQLite 跑研究闭环，但进入模拟盘和实盘前建议切到 PostgreSQL。

## 4.1 股票基础表

```sql
CREATE TABLE stocks (
    ts_code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    exchange VARCHAR(20),
    industry VARCHAR(100),
    list_date DATE,
    delist_date DATE,
    is_st BOOLEAN DEFAULT FALSE,
    status VARCHAR(20),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4.2 日线行情表

```sql
CREATE TABLE daily_bar (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    adj_type VARCHAR(20) NOT NULL DEFAULT 'none',

    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    pre_close NUMERIC,

    volume BIGINT,
    amount NUMERIC,

    source VARCHAR(50),
    quality_flag VARCHAR(50) DEFAULT 'NORMAL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(ts_code, trade_date, adj_type)
);
```

## 4.3 因子值表

`factor_value` 只保存最终入选或需要审计的因子结果，不作为大规模研究矩阵的主存储。研究阶段的全量因子矩阵优先使用 Parquet 存储：

```text
research_store/factor_matrix/
```

```sql
CREATE TABLE factor_value (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    factor_name VARCHAR(50) NOT NULL,
    factor_value NUMERIC,
    version VARCHAR(50) DEFAULT 'v1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (ts_code, trade_date, factor_name, version)
);
```

## 4.4 信号表

```sql
CREATE TABLE signal (
    id BIGSERIAL PRIMARY KEY,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL DEFAULT 'v1',
    factor_set_id VARCHAR(100),
    signal_type VARCHAR(20) NOT NULL,
    score NUMERIC,
    target_weight NUMERIC,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4.5 订单表

```sql
CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    broker_order_id VARCHAR(100),
    signal_id BIGINT,
    account_id VARCHAR(50),
    strategy_id VARCHAR(50),
    strategy_version VARCHAR(50),
    ts_code VARCHAR(20) NOT NULL,

    side VARCHAR(10) NOT NULL,
    price NUMERIC,
    quantity INT NOT NULL,
    filled_quantity INT DEFAULT 0,
    avg_price NUMERIC,

    status VARCHAR(30) NOT NULL,
    error_msg TEXT,
    request_id VARCHAR(100),

    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4.6 持仓表

```sql
CREATE TABLE positions (
    account_id VARCHAR(50),
    ts_code VARCHAR(20),
    trade_date DATE,
    quantity INT,
    available_quantity INT,
    avg_cost NUMERIC,
    market_value NUMERIC,
    weight NUMERIC,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(account_id, ts_code, trade_date)
);
```

## 4.7 组合快照表

每日保存组合状态，作为回测、模拟盘、实盘复盘的统一净值口径。

```sql
CREATE TABLE portfolio_snapshot (
    account_id VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    total_asset NUMERIC,
    cash NUMERIC,
    market_value NUMERIC,
    total_position_ratio NUMERIC,
    daily_return NUMERIC,
    cum_return NUMERIC,
    drawdown NUMERIC,
    benchmark_code VARCHAR(50),
    excess_return NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(account_id, trade_date)
);
```

## 4.8 Benchmark 表

用于保存沪深300、中证500、中证1000、红利ETF等基准数据。

```sql
CREATE TABLE benchmark_bar (
    benchmark_code VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(benchmark_code, trade_date)
);
```

## 4.9 策略版本表

所有上线策略必须登记版本，保证未来能复盘收益来源。

```sql
CREATE TABLE strategy_registry (
    strategy_id VARCHAR(50) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL,
    description TEXT,
    factor_set_id VARCHAR(100),
    code_hash VARCHAR(100),
    research_report_path TEXT,
    status VARCHAR(20) DEFAULT 'research',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(strategy_id, strategy_version)
);
```

策略状态 `status` 固定为：

1. research：研究中。
2. candidate：候选，已通过初步研究。
3. paper：模拟盘观察。
4. production：小资金或正式实盘。
5. deprecated：已淘汰，禁止新开仓。

## 4.10 股票池快照表

每日保存可交易股票池，保证回测、模拟盘和实盘使用同一套 Universe。

```sql
CREATE TABLE universe_snapshot (
    universe_id VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    include_reason TEXT,
    exclude_reason TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY(universe_id, trade_date, ts_code)
);
```

## 4.11 数据质量标记

`quality_flag` 建议使用以下值：

1. NORMAL：正常。
2. DUPLICATED：重复数据。
3. MISSING_GAP：存在缺口。
4. ZERO_VOLUME：零成交量。
5. LIMIT_UP：涨停。
6. LIMIT_DOWN：跌停。
7. SUSPENDED：停牌。
8. ST_STOCK：ST 股票。
9. DELISTED：退市。
10. MANUAL_REVIEW：需要人工复核。

涨跌停、停牌、ST 不应简单删除，应作为状态进入回测和风控。

# 五、数据层

## 5.1 数据源

V1 推荐：

1. AKShare：基础行情、股票列表、指数数据。
2. Tushare Free：补充基本面、财务指标、交易日历。

注意：免费数据源适合研究和低频系统，不应假设字段永久稳定。所有采集任务必须记录数据源、更新时间和质量标记。

## 5.2 更新频率

日线系统推荐在交易日 17:00 后执行：

1. 更新股票列表。
2. 更新全部 A股日线。
3. 更新指数日线。
4. 更新停牌、ST、退市状态。
5. 更新财务和基本面数据。
6. 执行数据质量检查。

## 5.3 数据清洗规则

必须处理：

1. 停牌。
2. 退市。
3. ST。
4. 前复权 / 后复权 / 不复权。
5. 涨跌停。
6. 缺失交易日。
7. 异常价格。
8. 成交量为 0。

原则：

1. 不随意删除异常行情。
2. 先标记，再决定是否进入策略样本。
3. 回测必须显式处理停牌、涨跌停和 T+1。

# 六、Universe 股票池

Universe 是所有策略共享的股票池入口。V1 必须把股票池独立出来，避免不同策略各自维护过滤规则，导致回测、模拟盘和实盘口径不一致。

## 6.1 目录结构

```text
core/universe/
```

统一接口：

```python
class Universe:
    universe_id = "a_share_v1"

    def get_universe(self, trade_date):
        raise NotImplementedError
```

## 6.2 V1 股票池规则

默认股票池处理：

1. 排除 ST。
2. 排除退市和退市整理期。
3. 排除停牌。
4. 排除上市不足 120 个交易日。
5. 排除近 20 日平均成交额低于 5000 万的股票。
6. 排除长期零成交量或流动性枯竭股票。
7. 默认排除北交所，后续单独建模。
8. 科创板和创业板可配置是否纳入。

## 6.3 Universe 快照

每天生成 `universe_snapshot`，记录当日每只股票是否进入股票池以及原因。

作用：

1. 保证回测可复现。
2. 保证策略共享同一股票池。
3. 便于排查为什么某只股票被纳入或排除。
4. 避免未来函数和幸存者偏差。

# 七、Alpha Research 层

Alpha Research 是 V1 最重要的研究层，目标不是列出因子，而是建立一套持续发现、验证、上线和淘汰 Alpha 的机制。

## 7.1 目录结构

```text
core/research/
  factor_lab/          # 候选因子实验
  alpha_validation/    # 有效性检验
  factor_report/       # 研究报告生成
  benchmark/           # 基准对比
```

## 7.2 因子研究流程

每个候选因子必须经过以下流程：

1. 提出研究假设。
2. 明确经济或行为金融解释。
3. 生成因子矩阵。
4. 做缺失值、极值、行业中性化检查。
5. 检查 IC、Rank IC、分组收益。
6. 检查换手率和交易成本。
7. 对比 Benchmark。
8. 样本外测试。
9. 生成研究报告。
10. 决定进入观察、上线或淘汰。

## 7.3 Alpha 验证指标

必须输出：

1. IC 均值。
2. ICIR。
3. Rank IC。
4. 多空分组收益。
5. 分组单调性。
6. 换手率。
7. 最大回撤。
8. 超额收益。
9. 信息比率。
10. 不同市场状态下的表现。

## 7.4 因子上线标准

候选因子不能因为一次回测好看就上线。至少满足：

1. 有明确研究假设。
2. 样本外有效。
3. 不依赖未来数据。
4. 扣除交易成本后仍有超额收益。
5. 在不同年份不过度失效。
6. 与现有因子相关性不过高。
7. 有明确淘汰条件。

## 7.5 因子淘汰机制

上线因子需要定期复查。触发以下情况时进入观察或淘汰：

1. 连续 N 个月 IC 显著下降。
2. 超额收益长期为负。
3. 换手率上升导致成本吞噬收益。
4. 与组合其他因子高度同质化。
5. 市场制度或数据口径发生变化。

## 7.6 研究存储

研究阶段不把所有因子明细都写入数据库。推荐：

```text
Parquet：保存 Feature Store 和大规模因子矩阵
PostgreSQL：保存最终入选因子、信号、快照和审计结果
Markdown/HTML：保存研究报告
```

## 7.7 Feature Store

Feature Store 保存可复用的预处理特征，不等同于最终因子。

目录：

```text
research_store/feature_store/
```

典型特征：

1. 净利润同比。
2. ROE。
3. ROA。
4. 资产负债率。
5. 总市值。
6. 流通市值。
7. 行业编码。
8. 换手率。
9. 波动率。
10. 成交额。

用途：

1. 供因子研究复用。
2. 供机器学习实验复用。
3. 供 AI 研究辅助读取。
4. 减少重复计算和数据口径漂移。

# 八、因子引擎

目录：

```text
core/factor/
```

统一接口：

```python
class Factor:
    name = ""
    version = "v1"

    def calculate(self, df):
        raise NotImplementedError
```

## 8.1 第一批因子

动量：

1. 20 日收益率。
2. 60 日收益率。
3. 120 日收益率。

波动率：

1. 20 日标准差。
2. 60 日标准差。

趋势：

1. MA20。
2. MA60。
3. MA120。

基本面：

1. ROE。
2. ROA。
3. 净利润增长率。
4. 资产负债率。

## 8.2 Rust 加速边界

V1 初期因子由 Python 实现。后续可以把固定数学指标交给 Rust：

1. MA。
2. EMA。
3. MACD。
4. RSI。
5. ATR。
6. BOLL。
7. 滚动均值、标准差、最大值、最小值。

Rust 只输出指标列，Python 继续负责因子组合和策略解释。

# 九、策略引擎

统一接口：

```python
class Strategy:
    strategy_id = ""

    def generate_signal(self, context):
        raise NotImplementedError
```

## 9.1 策略一：动量排名

规则：

1. 股票池排除 ST、退市、停牌、上市不足 120 个交易日。
2. 按 60 日涨幅排名。
3. 选择排名前 10%。
4. 最多买入前 20 只。

## 9.2 策略二：质量因子

规则：

1. ROE > 10%。
2. 净利润增长率 > 15%。
3. 资产负债率 < 60%。
4. 排除财务异常和连续亏损股票。

## 9.3 策略三：趋势过滤

规则：

1. 沪深300 > MA120，允许持仓。
2. 沪深300 <= MA120，降低仓位或空仓。

## 9.4 策略生命周期与可追溯性

每个策略必须登记：

1. strategy_id。
2. strategy_version。
3. factor_set_id。
4. code_hash。
5. research_report_path。
6. 上线日期。
7. 淘汰条件。

实盘和模拟盘必须形成完整链路：

```text
订单 -> 信号 -> 策略版本 -> 因子组合 -> Alpha 研究报告
```

没有登记版本和研究报告的策略，不进入模拟盘。

# 十、组合管理

目标：

1. 避免重仓单只股票。
2. 避免行业过度集中。
3. 控制换手率。
4. 输出明确目标持仓。

## 10.1 持仓约束

```text
持仓数量：10-20 只
单股默认仓位：5%
单股最大仓位：10%
单行业最大仓位：30%
现金预留：5%-20%
```

## 10.2 调仓规则

V1 推荐每周或每月调仓，不建议每日大规模换仓。

调仓流程：

1. 读取当前持仓。
2. 生成目标持仓。
3. 计算差额。
4. 先卖出，再买入。
5. 考虑 T+1 可卖数量。
6. 生成订单意图。
7. 进入风控检查。

# 十一、风险控制

## 11.1 组合风控

1. 单股止损：-8%。
2. 单股止盈：20%，后续可改移动止盈。
3. 组合回撤 10%：减仓 50%。
4. 最大回撤 15%：停止新开仓。
5. 单行业仓位 <= 30%。
6. 单股仓位 <= 10%。

## 11.2 A股实盘约束

实盘和回测必须处理：

1. T+1。
2. 100 股整数手。
3. 涨跌停无法买入或卖出。
4. 停牌无法交易。
5. ST 股票限制。
6. 手续费、印花税、过户费。
7. 部分成交。
8. 撤单失败。
9. 废单。
10. 本地持仓与券商持仓对账。

## 11.3 A股专属风险模型

目录：

```text
core/risk/china_market/
```

必须单独建模：

1. T+1 可卖数量。
2. 涨停无法买入。
3. 跌停无法卖出。
4. 停牌无法交易。
5. ST 和退市风险。
6. 退市整理期。
7. 北交所规则差异。
8. 可转债规则差异。

## 11.4 流动性风险

买入前必须检查：

1. 近 20 日平均成交额。
2. 当日成交额。
3. 预估成交金额占成交额比例。
4. 是否连续缩量。

V1 默认规则：

```text
近20日平均成交额 < 5000万，禁止新买入。
单笔买入金额 > 近20日平均成交额的 1%，禁止自动下单。
```

## 11.5 跳空与黑名单风险

跳空风险：

1. 开盘跌停时止损可能失效。
2. 大幅低开时按实际可成交价格评估风险。
3. 回测必须模拟隔夜跳空。

黑名单：

1. ST。
2. 退市风险。
3. 财务造假风险。
4. 重大违法风险。
5. 长期停牌或流动性枯竭。

黑名单股票默认禁止新开仓。

## 11.6 Rust 硬风控安全阀

Python 负责业务风控，Rust 负责稳定、保守的硬拦截。

V1.1 可实现：

1. 最大单笔金额限制。
2. 最大单股仓位限制。
3. 最大组合仓位限制。
4. 非交易时段禁止开仓。
5. 重复委托指纹拦截。
6. 单日最大亏损锁定。

原则：

1. Rust 风控失败时，默认拒绝新开仓。
2. 每次拦截必须记录不可覆盖日志。
3. Python 发送订单意图前必须通过风控检查。

# 十二、回测引擎

## 12.1 回测框架

V1 使用分层方案：

```text
研究回测：vectorbt
实盘一致性回测：自研 Portfolio / Execution Simulator
```

vectorbt 适合快速研究和向量化验证。实盘一致性回测需要额外模拟：

1. T+1。
2. 涨跌停。
3. 停牌。
4. 手续费和税费。
5. 滑点。
6. 调仓顺序。
7. 部分成交。

## 12.2 核心指标

1. Annual Return。
2. Sharpe。
3. Sortino。
4. Calmar。
5. Max Drawdown。
6. Profit Factor。
7. Win Rate。
8. Turnover。
9. Exposure。

## 12.3 Benchmark 体系

所有策略回测必须对比基准。V1 默认基准：

1. 沪深300。
2. 中证500。
3. 中证1000。
4. 红利ETF。
5. Equal Weight Benchmark：当期 Universe 等权基准。

Equal Weight Benchmark 是 V1 必须实现的内部基准，用于判断策略收益来自市场整体上涨、股票池风格，还是来自真正选股 Alpha。

回测报告必须输出：

1. 策略绝对收益。
2. Benchmark 收益。
3. 超额收益。
4. 信息比率。
5. 相对最大回撤。
6. 月度胜率。
7. 牛市、熊市、震荡市分段表现。

判断原则：

```text
策略跑赢现金不够，必须解释为什么跑赢或跑输对应 Benchmark。
```

## 12.4 回测流程

```text
读取数据
  |
  v
计算因子
  |
  v
Alpha 验证
  |
  v
生成信号
  |
  v
组合构建
  |
  v
撮合模拟
  |
  v
统计结果
  |
  v
生成报告
```

## 12.5 防过拟合规则

1. 训练集、验证集、测试集分离。
2. 参数取稳定区间，不取孤立最优点。
3. 多年份、多市场状态测试。
4. 检查未来函数。
5. 检查幸存者偏差。
6. 记录每次回测配置。

# 十三、实盘交易

A股实盘是 V1 最大难点。V1 推荐走 QMT 或券商提供的正式程序化接口，不使用网页自动点击或模拟鼠标。

## 13.1 推荐路线

优先评估：

1. 同花顺 QMT。
2. 国金 QMT。
3. 华泰 QMT。
4. 中泰 QMT。
5. 其他券商正式 API 或量化终端。

选择标准：

1. 是否支持 Python。
2. 是否支持查询资金、持仓、委托、成交。
3. 是否支持自动报单和撤单。
4. 是否有模拟盘。
5. 是否有明确的权限和合规要求。
6. 是否能稳定运行在目标机器。

## 13.2 V1 执行方式

V1 先采用保守模式：

1. Python 生成订单意图。
2. Python 业务风控检查。
3. Rust 硬风控检查。
4. 生成调仓单。
5. 模拟盘验证。
6. 小资金实盘。
7. 每日盘后对账。

早期可以保留人工确认开关：

```text
auto_trade = false
```

当模拟盘连续稳定后，再打开自动执行。

## 13.3 对账流程

每日盘后必须执行：

1. 拉取券商资金。
2. 拉取券商持仓。
3. 拉取当日委托。
4. 拉取当日成交。
5. 与本地 orders / positions 对账。
6. 生成差异报告。
7. 有差异时停止下一交易日自动开仓。

# 十四、Rust 模块设计

Rust 模块是 V1 的增强层，不是主系统替代品。

## 14.1 V1 优先实现

```text
rust_core/
  crates/
    data_cleaner/
    indicator_engine/
    scheduler/
```

职责：

1. 数据清洗。
2. 数据质量标记。
3. 批量指标计算。
4. 定时任务调度。

## 14.2 V1.1 实现

```text
rust_core/
  crates/
    bar_builder/
    risk_guard/
```

职责：

1. K线聚合。
2. 回测数据预处理。
3. 硬风控安全阀。
4. 委托指纹去重。

## 14.3 暂不实现

```text
暂不 Rust 化：
券商报单主链路
行情网关主链路
策略表达
回测编排
AI Agent
```

## 14.4 Python 与 Rust 通信

第一阶段：Rust CLI。

适合：

1. 数据清洗。
2. 指标批量计算。
3. 回测数据准备。

第二阶段：本地服务。

适合：

1. 风控检查。
2. 调度器。
3. 消息转发。

第三阶段：Python 扩展。

适合：

1. 大量重复调用的数值函数。
2. 大规模数组计算。

V1 不建议一开始使用 PyO3/maturin，先用 CLI 最简单。

# 十五、AI Agent 系统

V1 不接入 AI Agent 主流程，只预留目录：

```text
core/ai/
```

AI 永远不能直接产生交易信号，也不能直接进入下单链路。AI 的定位是研究辅助：

```text
AI -> 候选因子/研究材料 -> 人工审核 -> 回测验证 -> 模拟盘观察 -> 上线
```

## 15.1 V1.5 可做

1. 财报摘要。
2. 公告分类。
3. 新闻情绪标签。
4. 回测报告解释。

## 15.2 V2 再做

1. 因子发现 Agent。
2. 回测生成 Agent。
3. 策略审计 Agent。
4. 过拟合检查 Agent。

AI 输出只能作为研究输入或人工审核材料。任何 AI 生成的候选因子，必须经过 Alpha Research、Benchmark 对比、样本外测试和模拟盘验证。

# 十六、部署方案

## 16.1 开发环境约定

本项目开发环境固定如下：

```text
Python 环境：conda 环境 trading
Rust 环境：宿主机 Rust 工具链
```

Python 开发、数据采集、回测、因子研究、模拟盘任务均在 conda 的 `trading` 环境中运行。

常用命令：

```bash
conda activate trading
python --version
pip list
```

Rust 模块在宿主机环境中开发和构建，不放入 conda 环境管理。

常用命令：

```bash
rustc --version
cargo --version
cargo build
cargo test
```

Python 调用 Rust 的优先方式：

1. V1：通过 Rust CLI 输出文件，Python 在 `trading` 环境中读取结果。
2. V1.1：Rust 作为本地服务或二进制工具，由 Python 调用。
3. 暂不使用 PyO3/maturin，除非后续出现明确性能瓶颈。

## 16.2 V1 最小部署

```text
PostgreSQL
Python Collector
Python Backtest
Python Trader
日志文件
```

适合 0~100 元/月预算。

## 16.3 V1.1 增强部署

```text
PostgreSQL
Redis
Python API
Python Trader
Rust Scheduler
Rust Risk Guard
Grafana
```

Redis 和 Grafana 不必第一天引入。日线系统先跑通闭环更重要。

## 16.4 Docker 服务

```text
postgres:16
redis:7
python:3.12
rust:stable
collector
backtest
trader
monitor
```

# 十七、监控系统

## 17.1 V1 必须监控

1. 数据更新是否成功。
2. 因子计算是否成功。
3. 回测任务是否异常。
4. 调仓计划是否生成。
5. 委托是否成功。
6. 成交是否回报。
7. 本地持仓与券商持仓是否一致。
8. 组合回撤是否触线。

## 17.2 V1.1 可视化

Grafana 监控：

1. 账户净值。
2. 仓位。
3. 回撤。
4. 策略收益。
5. 数据任务状态。
6. VPS 状态。

# 十八、开发路线图

## 18.1 优先级

P0 必须完成：

1. 数据层。
2. Alpha Research。
3. Benchmark。
4. 回测层。
5. 组合层。
6. 基础风控。
7. Portfolio Snapshot。

P1 重要：

1. 事件模型。
2. 策略版本管理。
3. Traceability。
4. 模拟盘。
5. 对账系统。

P2 稳定后：

1. QMT 接入。
2. 小资金实盘。
3. Rust Risk Guard。
4. Grafana。
5. Redis。

P3 未来：

1. AI Agent。
2. 多模型。
3. 分钟线研究。

## 18.2 8 周实现顺序

冻结 V1 设计后，优先按以下顺序实现：

```text
Week 1：stocks / daily_bar / benchmark_bar
Week 2：Universe
Week 3：Feature Store + Factor Engine
Week 4：Alpha Research
Week 5：Backtest + Benchmark Report
Week 6：Portfolio + Portfolio Snapshot
Week 7：Risk + China Market Rules
Week 8：Paper Trading
```

## 18.3 月度路线图

## 第 1 个月：研究平台

完成：

1. PostgreSQL。
2. AKShare / Tushare Free 采集。
3. 日线数据表。
4. 数据质量标记。
5. Alpha Research 目录。
6. Benchmark 数据。
7. 第一批因子。
8. 基础回测。

## 第 2 个月：策略和组合

完成：

1. 动量策略。
2. 质量策略。
3. 趋势过滤。
4. 组合管理。
5. 费用和滑点。
6. Portfolio Snapshot。
7. 策略版本管理。
8. 回测报告。

## 第 3 个月：模拟盘和风控

完成：

1. 业务风控。
2. A股专属风险模型。
3. 流动性和黑名单规则。
4. 事件模型。
5. 模拟盘。
6. 调仓单生成。
7. 盘后对账。

## 第 4 个月：系统稳定性验证

完成：

1. 模拟盘连续运行 20 个交易日。
2. 数据任务稳定性验证。
3. 策略信号复核。
4. 回测与模拟盘差异分析。
5. 每日对账流程。
6. 监控告警。
7. Rust 数据清洗 CLI。

## 第 5 个月以后：稳定后再实盘

可选：

1. QMT 或正式券商接口接入。
2. 小资金实盘。
3. Rust 硬风控安全阀。
4. Redis。
5. Grafana。
6. AI 财报摘要。
7. 新闻情绪标签。
8. 分钟线研究扩展。

# 十九、最终判断

V1.0 的核心不是技术炫技，而是闭环稳定。

最推荐的落地顺序是：

```text
数据 -> Alpha Research -> Benchmark -> 因子 -> 回测 -> 组合 -> 风控 -> 模拟盘 -> 稳定验证 -> 小资金实盘
```

Rust 应该作为增强层逐步进入，而不是一开始接管交易主链路。

AI Agent 应该作为研究辅助逐步进入，而不是一开始进入下单链路。

系统跑满 3 到 6 个月后，再根据真实瓶颈决定是否引入更多 Rust 服务、Redis 消息总线、Grafana 监控和 AI 研究模块。
