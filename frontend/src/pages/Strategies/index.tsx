import { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
  Descriptions,
  Tabs,
  Tooltip,
  Popconfirm,
  Progress,
  Alert,
  Typography,
} from 'antd';
import {
  ExperimentOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import api from '../../api/client';

const { TextArea } = Input;
const { Paragraph } = Typography;

interface StrategyConfig {
  strategy_id: string;
  strategy_name: string;
  strategy_type: string;
  strategy_version: string;
  description: string;
  status: string;
  params?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

interface StrategyReview {
  review_id: string;
  strategy_id: string;
  decision: string;
  score: number;
  criteria_results: Array<{
    name: string;
    passed: boolean;
    value: number;
    threshold: number;
    message: string;
  }>;
  created_at: string;
}

interface ScriptStrategy {
  type: string;
  name: string;
  description: string;
  params: Array<{
    name: string;
    type: string;
    default: any;
    description: string;
  }>;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [createVisible, setCreateVisible] = useState(false);
  const [editVisible, setEditVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [scriptVisible, setScriptVisible] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyConfig | null>(null);
  const [editingStrategy, setEditingStrategy] = useState<StrategyConfig | null>(null);
  const [review, setReview] = useState<StrategyReview | null>(null);
  const [scriptTypes, setScriptTypes] = useState<ScriptStrategy[]>([]);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [scriptForm] = Form.useForm();

  useEffect(() => {
    fetchStrategies();
    fetchScriptTypes();
  }, []);

  const fetchStrategies = async () => {
    setLoading(true);
    try {
      // 从本地存储获取策略列表
      const saved = localStorage.getItem('strategies');
      if (saved) {
        setStrategies(JSON.parse(saved));
      } else {
        // 默认策略
        const defaultStrategies: StrategyConfig[] = [
          {
            strategy_id: 'momentum_rank',
            strategy_name: '动量排名策略',
            strategy_type: 'momentum_rank',
            strategy_version: 'v1',
            description: '基于动量因子选股，持有排名靠前的股票',
            status: 'production',
            created_at: '2025-01-01',
            updated_at: '2025-01-01',
          },
          {
            strategy_id: 'quality_rank',
            strategy_name: '质量排名策略',
            strategy_type: 'quality_rank',
            strategy_version: 'v1',
            description: '基于质量因子选股，持有质量评分最高的股票',
            status: 'production',
            created_at: '2025-01-01',
            updated_at: '2025-01-01',
          },
          {
            strategy_id: 'momentum_rank_trend',
            strategy_name: '动量+趋势策略',
            strategy_type: 'momentum_rank_trend',
            strategy_version: 'v1',
            description: '动量因子选股，叠加趋势过滤',
            status: 'candidate',
            created_at: '2025-01-01',
            updated_at: '2025-01-01',
          },
        ];
        setStrategies(defaultStrategies);
        localStorage.setItem('strategies', JSON.stringify(defaultStrategies));
      }
    } catch (error) {
      console.error('获取策略列表失败', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchScriptTypes = async () => {
    try {
      // 脚本策略类型 - 支持自定义参数
      const types: ScriptStrategy[] = [
        {
          type: 'momentum',
          name: '动量策略',
          description: '基于价格动量选股',
          params: [
            { name: 'lookback', type: 'int', default: 20, description: '回看周期' },
            { name: 'threshold', type: 'float', default: 0, description: '动量阈值' },
            { name: 'position_size', type: 'float', default: 0.05, description: '仓位大小' },
          ],
        },
        {
          type: 'ma_cross',
          name: '均线交叉策略',
          description: '快慢均线金叉死叉',
          params: [
            { name: 'fast_period', type: 'int', default: 5, description: '快线周期' },
            { name: 'slow_period', type: 'int', default: 20, description: '慢线周期' },
            { name: 'position_size', type: 'float', default: 0.05, description: '仓位大小' },
          ],
        },
        {
          type: 'rsi',
          name: 'RSI 策略',
          description: '基于 RSI 超买超卖',
          params: [
            { name: 'period', type: 'int', default: 14, description: 'RSI 周期' },
            { name: 'oversold', type: 'float', default: 30, description: '超卖阈值' },
            { name: 'overbought', type: 'float', default: 70, description: '超买阈值' },
          ],
        },
        {
          type: 'bollinger',
          name: '布林带策略',
          description: '基于布林带突破',
          params: [
            { name: 'period', type: 'int', default: 20, description: '周期' },
            { name: 'std_dev', type: 'float', default: 2, description: '标准差倍数' },
          ],
        },
        {
          type: 'dual_ma',
          name: '双均线策略',
          description: '双均线 + 止损止盈',
          params: [
            { name: 'fast_period', type: 'int', default: 5, description: '快线周期' },
            { name: 'slow_period', type: 'int', default: 20, description: '慢线周期' },
            { name: 'stop_loss', type: 'float', default: 0.05, description: '止损比例' },
            { name: 'take_profit', type: 'float', default: 0.10, description: '止盈比例' },
          ],
        },
        {
          type: 'custom',
          name: '自定义脚本',
          description: '用户自定义 Python 脚本',
          params: [
            { name: 'code', type: 'text', default: '', description: 'Python 代码' },
          ],
        },
      ];
      setScriptTypes(types);
    } catch (error) {
      console.error('获取脚本类型失败', error);
    }
  };

  // 生成策略 Python 代码
  const generateStrategyCode = (strategy: StrategyConfig): string => {
    const params = strategy.params || {};
    const strategyType = strategy.strategy_type;

    if (strategyType === 'momentum_rank') {
      const maxHoldings = params.max_holdings || 20;
      return `# 动量排名策略
# 策略名称: ${strategy.strategy_name}
# 最大持仓: ${maxHoldings}

from quant.core.strategy.momentum import MomentumRankStrategy
from quant.core.factor.technical import MomentumFactor, FactorEngine
from quant.core.backtest.engine import BacktestEngine, BacktestRequest

# 创建策略
strategy = MomentumRankStrategy(
    factor_name="momentum_60d",
    max_holdings=${maxHoldings},
)

# 创建因子引擎
factor_engine = FactorEngine([MomentumFactor(60)])

# 运行回测
engine = BacktestEngine(factor_engine=factor_engine)
result = engine.run(BacktestRequest(
    bars=bars,
    stocks=stocks,
    strategy=strategy,
    benchmark_bars=benchmark_bars,
    benchmark_code="000300.SH",
    initial_cash=1_000_000,
    rebalance="weekly",
))

# 查看结果
print(f"年化收益: {result.metrics['annual_return']*100:.2f}%")
print(f"夏普比率: {result.metrics['sharpe']:.4f}")
print(f"最大回撤: {result.metrics['max_drawdown']*100:.2f}%")`;
    }

    if (strategyType === 'quality_rank') {
      const maxHoldings = params.max_holdings || 20;
      return `# 质量排名策略
# 策略名称: ${strategy.strategy_name}
# 最大持仓: ${maxHoldings}

from quant.core.strategy.quality import QualityRankStrategy
from quant.core.factor.quality import QualityScoreFactor
from quant.core.factor.technical import FactorEngine
from quant.core.backtest.engine import BacktestEngine, BacktestRequest

# 创建策略
strategy = QualityRankStrategy(
    factor_name="quality_score",
    max_holdings=${maxHoldings},
)

# 创建因子引擎
factor_engine = FactorEngine([QualityScoreFactor()])

# 运行回测
engine = BacktestEngine(factor_engine=factor_engine)
result = engine.run(BacktestRequest(
    bars=bars,
    stocks=stocks,
    strategy=strategy,
    benchmark_bars=benchmark_bars,
    benchmark_code="000300.SH",
    initial_cash=1_000_000,
    rebalance="weekly",
))

# 查看结果
print(f"年化收益: {result.metrics['annual_return']*100:.2f}%")
print(f"夏普比率: {result.metrics['sharpe']:.4f}")
print(f"最大回撤: {result.metrics['max_drawdown']*100:.2f}%")`;
    }

    if (strategyType === 'momentum') {
      const lookback = params.lookback || 20;
      const threshold = params.threshold || 0;
      return `# 动量策略 (脚本版)
# 策略名称: ${strategy.strategy_name}
# 回看周期: ${lookback}
# 动量阈值: ${threshold}

def on_init(ctx):
    ctx.set_param("lookback", ${lookback})
    ctx.set_param("threshold", ${threshold})
    ctx.set_param("prices", {})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    lookback = ctx.param("lookback")
    if len(prices[bar.ts_code]) < lookback + 1:
        return

    # 计算动量
    current = prices[bar.ts_code][-1]
    past = prices[bar.ts_code][-(lookback + 1)]
    momentum = (current - past) / past

    threshold = ctx.param("threshold")

    # 买入条件：动量超过阈值且无持仓
    if momentum > threshold and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=0.05, reason=f"momentum={momentum:.4f}")

    # 卖出条件：动量转负且有持仓
    elif momentum < 0 and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason=f"momentum={momentum:.4f}")`;
    }

    if (strategyType === 'ma_cross') {
      const fastPeriod = params.fast_period || 5;
      const slowPeriod = params.slow_period || 20;
      return `# 均线交叉策略
# 策略名称: ${strategy.strategy_name}
# 快线周期: ${fastPeriod}
# 慢线周期: ${slowPeriod}

def on_init(ctx):
    ctx.set_param("fast_period", ${fastPeriod})
    ctx.set_param("slow_period", ${slowPeriod})
    ctx.set_param("prices", {})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    fast_period = ctx.param("fast_period")
    slow_period = ctx.param("slow_period")

    if len(prices[bar.ts_code]) < slow_period:
        return

    # 计算均线
    fast_ma = sum(prices[bar.ts_code][-fast_period:]) / fast_period
    slow_ma = sum(prices[bar.ts_code][-slow_period:]) / slow_period

    # 金叉买入
    if fast_ma > slow_ma and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=0.05, reason="golden_cross")

    # 死叉卖出
    elif fast_ma < slow_ma and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="death_cross")`;
    }

    if (strategyType === 'rsi') {
      const period = params.period || 14;
      const oversold = params.oversold || 30;
      const overbought = params.overbought || 70;
      return `# RSI 策略
# 策略名称: ${strategy.strategy_name}
# RSI 周期: ${period}
# 超卖阈值: ${oversold}
# 超买阈值: ${overbought}

def on_init(ctx):
    ctx.set_param("period", ${period})
    ctx.set_param("oversold", ${oversold})
    ctx.set_param("overbought", ${overbought})
    ctx.set_param("prices", {})

def _calculate_rsi(prices, period):
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0.0001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    period = ctx.param("period")
    rsi = _calculate_rsi(prices[bar.ts_code], period)
    if rsi is None:
        return

    oversold = ctx.param("oversold")
    overbought = ctx.param("overbought")

    # 超卖买入
    if rsi < oversold and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=0.05, reason=f"rsi_oversold={rsi:.1f}")

    # 超买卖出
    elif rsi > overbought and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason=f"rsi_overbought={rsi:.1f}")`;
    }

    if (strategyType === 'bollinger') {
      const period = params.period || 20;
      const stdDev = params.std_dev || 2;
      return `# 布林带策略
# 策略名称: ${strategy.strategy_name}
# 周期: ${period}
# 标准差倍数: ${stdDev}

import math

def on_init(ctx):
    ctx.set_param("period", ${period})
    ctx.set_param("std_dev", ${stdDev})
    ctx.set_param("prices", {})

def _calculate_bollinger(prices, period, std_dev):
    if len(prices) < period:
        return None, None, None
    recent = prices[-period:]
    middle = sum(recent) / period
    variance = sum((p - middle) ** 2 for p in recent) / period
    std = math.sqrt(variance)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    period = ctx.param("period")
    std_dev = ctx.param("std_dev")
    upper, middle, lower = _calculate_bollinger(prices[bar.ts_code], period, std_dev)

    if upper is None:
        return

    # 跌破下轨买入
    if bar.close < lower and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=0.05, reason="bollinger_lower")

    # 突破上轨卖出
    elif bar.close > upper and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="bollinger_upper")`;
    }

    if (strategyType === 'dual_ma') {
      const fastPeriod = params.fast_period || 5;
      const slowPeriod = params.slow_period || 20;
      const stopLoss = params.stop_loss || 0.05;
      const takeProfit = params.take_profit || 0.10;
      return `# 双均线策略 (带止损止盈)
# 策略名称: ${strategy.strategy_name}
# 快线周期: ${fastPeriod}
# 慢线周期: ${slowPeriod}
# 止损比例: ${stopLoss}
# 止盈比例: ${takeProfit}

def on_init(ctx):
    ctx.set_param("fast_period", ${fastPeriod})
    ctx.set_param("slow_period", ${slowPeriod})
    ctx.set_param("stop_loss", ${stopLoss})
    ctx.set_param("take_profit", ${takeProfit})
    ctx.set_param("prices", {})
    ctx.set_param("entry_prices", {})

def on_bar(ctx, bar):
    prices = ctx.param("prices")
    if bar.ts_code not in prices:
        prices[bar.ts_code] = []
    prices[bar.ts_code].append(bar.close)

    fast_period = ctx.param("fast_period")
    slow_period = ctx.param("slow_period")

    if len(prices[bar.ts_code]) < slow_period:
        return

    fast_ma = sum(prices[bar.ts_code][-fast_period:]) / fast_period
    slow_ma = sum(prices[bar.ts_code][-slow_period:]) / slow_period

    stop_loss = ctx.param("stop_loss")
    take_profit = ctx.param("take_profit")
    entry_prices = ctx.param("entry_prices")

    # 止损止盈检查
    if ctx.has_position(bar.ts_code):
        entry_price = entry_prices.get(bar.ts_code, 0)
        if entry_price > 0:
            pnl_pct = (bar.close - entry_price) / entry_price
            if stop_loss > 0 and pnl_pct < -stop_loss:
                ctx.sell(bar.ts_code, reason=f"stop_loss={pnl_pct:.4f}")
                return
            if take_profit > 0 and pnl_pct > take_profit:
                ctx.sell(bar.ts_code, reason=f"take_profit={pnl_pct:.4f}")
                return

    # 金叉买入
    if fast_ma > slow_ma and not ctx.has_position(bar.ts_code):
        ctx.buy(bar.ts_code, weight=0.05, reason="golden_cross")
        entry_prices[bar.ts_code] = bar.close

    # 死叉卖出
    elif fast_ma < slow_ma and ctx.has_position(bar.ts_code):
        ctx.sell(bar.ts_code, reason="death_cross")
        entry_prices.pop(bar.ts_code, None)`;
    }

    // 自定义脚本
    return params.code || `# 自定义脚本策略
# 请编写 on_init 和 on_bar 函数

def on_init(ctx):
    # 初始化参数
    pass

def on_bar(ctx, bar):
    # 每根K线触发
    # 买入: ctx.buy(ts_code, weight=0.05)
    # 卖出: ctx.sell(ts_code)
    pass`;
  };

  const handleCreate = (values: any) => {
    const newStrategy: StrategyConfig = {
      strategy_id: values.strategy_id,
      strategy_name: values.strategy_name,
      strategy_type: values.strategy_type,
      strategy_version: 'v1',
      description: values.description || '',
      status: 'draft',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const updated = [...strategies, newStrategy];
    setStrategies(updated);
    localStorage.setItem('strategies', JSON.stringify(updated));
    setCreateVisible(false);
    createForm.resetFields();
    message.success('策略创建成功');
  };

  const handleEdit = (strategy: StrategyConfig) => {
    setEditingStrategy(strategy);
    const formValues: any = {
      strategy_name: strategy.strategy_name,
      description: strategy.description,
      status: strategy.status,
    };

    // 设置参数初始值
    if (strategy.params) {
      Object.entries(strategy.params).forEach(([key, value]) => {
        formValues[`param_${key}`] = String(value);
      });
    }

    editForm.setFieldsValue(formValues);
    setEditVisible(true);
  };

  const handleEditSave = (values: any) => {
    if (!editingStrategy) return;

    // 收集参数
    const params: Record<string, any> = {};
    Object.entries(values).forEach(([key, value]) => {
      if (key.startsWith('param_') && value !== undefined && value !== '') {
        const paramName = key.replace('param_', '');
        // 尝试转换为数字
        const numValue = Number(value);
        params[paramName] = isNaN(numValue) ? value : numValue;
      }
    });

    const updated = strategies.map(s =>
      s.strategy_id === editingStrategy.strategy_id
        ? {
            ...s,
            strategy_name: values.strategy_name,
            description: values.description,
            status: values.status,
            params: Object.keys(params).length > 0 ? params : s.params,
            updated_at: new Date().toISOString(),
          }
        : s
    );
    setStrategies(updated);
    localStorage.setItem('strategies', JSON.stringify(updated));
    setEditVisible(false);
    editForm.resetFields();
    setEditingStrategy(null);
    message.success('策略更新成功');
  };

  const handleDelete = (strategyId: string) => {
    const updated = strategies.filter(s => s.strategy_id !== strategyId);
    setStrategies(updated);
    localStorage.setItem('strategies', JSON.stringify(updated));
    message.success('已删除');
  };

  const handleViewDetail = (strategy: StrategyConfig) => {
    setSelectedStrategy(strategy);
    setDetailVisible(true);
    // 模拟获取审核结果
    setReview({
      review_id: 'review_001',
      strategy_id: strategy.strategy_id,
      decision: 'approve',
      score: 85,
      criteria_results: [
        { name: 'sharpe_ratio', passed: true, value: 1.5, threshold: 0.8, message: '夏普比率: 1.5000 (阈值: 0.8000)' },
        { name: 'max_drawdown', passed: true, value: -0.10, threshold: -0.20, message: '最大回撤: -0.1000 (阈值: -0.2000)' },
        { name: 'annual_return', passed: true, value: 0.20, threshold: 0.10, message: '年化收益: 0.2000 (阈值: 0.1000)' },
        { name: 'excess_return', passed: true, value: 0.15, threshold: 0, message: '超额收益: 0.1500 (阈值: 0.0000)' },
        { name: 'stability', passed: true, value: 0.6, threshold: 0.5, message: '收益稳定性: 0.6000 (阈值: 0.5000)' },
      ],
      created_at: new Date().toISOString(),
    });
  };

  const handleStatusChange = (strategyId: string, newStatus: string) => {
    const updated = strategies.map(s =>
      s.strategy_id === strategyId
        ? { ...s, status: newStatus, updated_at: new Date().toISOString() }
        : s
    );
    setStrategies(updated);
    localStorage.setItem('strategies', JSON.stringify(updated));
    message.success(`状态已更新为 ${newStatus}`);
  };

  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; icon: any; text: string }> = {
      draft: { color: 'default', icon: <EditOutlined />, text: '草稿' },
      research: { color: 'processing', icon: <ExperimentOutlined />, text: '研究中' },
      candidate: { color: 'warning', icon: <ClockCircleOutlined />, text: '候选' },
      paper: { color: 'blue', icon: <PlayCircleOutlined />, text: '模拟盘' },
      production: { color: 'success', icon: <CheckCircleOutlined />, text: '实盘' },
      deprecated: { color: 'error', icon: <StopOutlined />, text: '已淘汰' },
      retired: { color: 'default', icon: <StopOutlined />, text: '退役' },
    };
    const c = config[status] || config.draft;
    return <Tag icon={c.icon} color={c.color}>{c.text}</Tag>;
  };

  const getDecisionTag = (decision: string) => {
    const config: Record<string, { color: string; text: string }> = {
      approve: { color: 'success', text: '通过' },
      reject: { color: 'error', text: '拒绝' },
      revise: { color: 'warning', text: '需修改' },
      pending: { color: 'default', text: '待审核' },
    };
    const c = config[decision] || config.pending;
    return <Tag color={c.color}>{c.text}</Tag>;
  };

  const columns = [
    {
      title: '策略ID',
      dataIndex: 'strategy_id',
      key: 'strategy_id',
      width: 150,
    },
    {
      title: '策略名称',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      width: 150,
    },
    {
      title: '类型',
      dataIndex: 'strategy_type',
      key: 'strategy_type',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 250,
      render: (_: any, record: StrategyConfig) => (
        <Space>
          <Tooltip title="查看详情">
            <Button type="link" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Tooltip title="状态流转">
            <Select
              size="small"
              value={record.status}
              style={{ width: 90 }}
              onChange={(value) => handleStatusChange(record.strategy_id, value)}
              options={[
                { value: 'draft', label: '草稿' },
                { value: 'research', label: '研究中' },
                { value: 'candidate', label: '候选' },
                { value: 'paper', label: '模拟盘' },
                { value: 'production', label: '实盘' },
                { value: 'deprecated', label: '淘汰' },
                { value: 'retired', label: '退役' },
              ]}
            />
          </Tooltip>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.strategy_id)}>
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card
        title="策略管理"
        extra={
          <Space>
            <Button type="primary" icon={<ExperimentOutlined />} onClick={() => setCreateVisible(true)}>
              创建策略
            </Button>
            <Button icon={<CodeOutlined />} onClick={() => setScriptVisible(true)}>
              脚本策略
            </Button>
          </Space>
        }
      >
        <Alert
          message="策略生命周期"
          description="draft(草稿) → research(研究) → candidate(候选) → paper(模拟盘) → production(实盘) → retired(退役)"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Table
          dataSource={strategies}
          columns={columns}
          rowKey="strategy_id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1200 }}
          size="small"
        />
      </Card>

      {/* 创建策略 Modal */}
      <Modal
        title="创建策略"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={createForm} onFinish={handleCreate} layout="vertical">
          <Form.Item label="策略ID" name="strategy_id" rules={[{ required: true, message: '请输入策略ID' }]}>
            <Input placeholder="例如: my_momentum_v1" />
          </Form.Item>
          <Form.Item label="策略名称" name="strategy_name" rules={[{ required: true, message: '请输入策略名称' }]}>
            <Input placeholder="例如: 我的动量策略" />
          </Form.Item>
          <Form.Item label="策略类型" name="strategy_type" rules={[{ required: true, message: '请选择策略类型' }]}>
            <Select placeholder="选择策略类型">
              <Select.Option value="momentum_rank">动量排名</Select.Option>
              <Select.Option value="quality_rank">质量排名</Select.Option>
              <Select.Option value="momentum_rank_trend">动量+趋势</Select.Option>
              <Select.Option value="quality_rank_trend">质量+趋势</Select.Option>
              <Select.Option value="custom">自定义脚本</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="描述" name="description">
            <TextArea rows={3} placeholder="策略描述..." />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑策略 Modal */}
      <Modal
        title={`编辑策略: ${editingStrategy?.strategy_name || ''}`}
        open={editVisible}
        onCancel={() => {
          setEditVisible(false);
          editForm.resetFields();
          setEditingStrategy(null);
        }}
        footer={null}
        width={700}
      >
        {editingStrategy && (
          <Form form={editForm} onFinish={handleEditSave} layout="vertical">
            <Form.Item label="策略ID">
              <Input value={editingStrategy.strategy_id} disabled />
            </Form.Item>
            <Form.Item label="策略类型">
              <Input value={editingStrategy.strategy_type} disabled />
            </Form.Item>
            <Form.Item
              label="策略名称"
              name="strategy_name"
              rules={[{ required: true, message: '请输入策略名称' }]}
            >
              <Input placeholder="例如: 我的动量策略" />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select>
                <Select.Option value="draft">草稿</Select.Option>
                <Select.Option value="research">研究中</Select.Option>
                <Select.Option value="candidate">候选</Select.Option>
                <Select.Option value="paper">模拟盘</Select.Option>
                <Select.Option value="production">实盘</Select.Option>
                <Select.Option value="deprecated">淘汰</Select.Option>
                <Select.Option value="retired">退役</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item label="描述" name="description">
              <TextArea rows={2} placeholder="策略描述..." />
            </Form.Item>

            {/* 策略参数编辑 */}
            <Card title="策略参数" size="small" style={{ marginBottom: 16 }}>
              {editingStrategy.strategy_type === 'momentum_rank' && (
                <>
                  <Form.Item label="最大持仓数量" name="param_max_holdings">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'quality_rank' && (
                <>
                  <Form.Item label="最大持仓数量" name="param_max_holdings">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'momentum' && (
                <>
                  <Form.Item label="回看周期" name="param_lookback">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                  <Form.Item label="动量阈值" name="param_threshold">
                    <Input type="number" placeholder="0" step="0.01" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'ma_cross' && (
                <>
                  <Form.Item label="快线周期" name="param_fast_period">
                    <Input type="number" placeholder="5" />
                  </Form.Item>
                  <Form.Item label="慢线周期" name="param_slow_period">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'rsi' && (
                <>
                  <Form.Item label="RSI 周期" name="param_period">
                    <Input type="number" placeholder="14" />
                  </Form.Item>
                  <Form.Item label="超卖阈值" name="param_oversold">
                    <Input type="number" placeholder="30" />
                  </Form.Item>
                  <Form.Item label="超买阈值" name="param_overbought">
                    <Input type="number" placeholder="70" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'bollinger' && (
                <>
                  <Form.Item label="周期" name="param_period">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                  <Form.Item label="标准差倍数" name="param_std_dev">
                    <Input type="number" placeholder="2" step="0.1" />
                  </Form.Item>
                </>
              )}
              {editingStrategy.strategy_type === 'dual_ma' && (
                <>
                  <Form.Item label="快线周期" name="param_fast_period">
                    <Input type="number" placeholder="5" />
                  </Form.Item>
                  <Form.Item label="慢线周期" name="param_slow_period">
                    <Input type="number" placeholder="20" />
                  </Form.Item>
                  <Form.Item label="止损比例" name="param_stop_loss">
                    <Input type="number" placeholder="0.05" step="0.01" />
                  </Form.Item>
                  <Form.Item label="止盈比例" name="param_take_profit">
                    <Input type="number" placeholder="0.10" step="0.01" />
                  </Form.Item>
                </>
              )}
              {!['momentum_rank', 'quality_rank', 'momentum', 'ma_cross', 'rsi', 'bollinger', 'dual_ma'].includes(editingStrategy.strategy_type) && (
                <Alert message="该策略类型暂不支持参数编辑" type="info" />
              )}
            </Card>

            {/* 自定义脚本代码编辑 */}
            {editingStrategy.strategy_type === 'custom' && (
              <Card title="策略代码" size="small" style={{ marginBottom: 16 }}>
                <Form.Item
                  label="Python 代码"
                  name="param_code"
                  rules={[{ required: true, message: '请输入策略代码' }]}
                >
                  <Input.TextArea
                    rows={15}
                    placeholder={`def on_init(ctx):
    # 初始化参数
    ctx.set_param("lookback", 20)

def on_bar(ctx, bar):
    # 每根K线触发
    # 买入: ctx.buy(bar.ts_code, weight=0.05)
    # 卖出: ctx.sell(bar.ts_code)
    pass`}
                    style={{ fontFamily: 'Monaco, Consolas, monospace', fontSize: 13 }}
                  />
                </Form.Item>
              </Card>
            )}

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">保存</Button>
                <Button onClick={() => {
                  setEditVisible(false);
                  editForm.resetFields();
                  setEditingStrategy(null);
                }}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>

      {/* 策略详情 Modal */}
      <Modal
        title={`策略详情: ${selectedStrategy?.strategy_name || ''}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
      >
        {selectedStrategy && (
          <Tabs
            items={[
              {
                key: 'info',
                label: '基本信息',
                children: (
                  <Descriptions bordered column={2} size="small">
                    <Descriptions.Item label="策略ID">{selectedStrategy.strategy_id}</Descriptions.Item>
                    <Descriptions.Item label="策略名称">{selectedStrategy.strategy_name}</Descriptions.Item>
                    <Descriptions.Item label="类型">{selectedStrategy.strategy_type}</Descriptions.Item>
                    <Descriptions.Item label="版本">{selectedStrategy.strategy_version}</Descriptions.Item>
                    <Descriptions.Item label="状态">{getStatusTag(selectedStrategy.status)}</Descriptions.Item>
                    <Descriptions.Item label="更新时间">
                      {selectedStrategy.updated_at ? new Date(selectedStrategy.updated_at).toLocaleString() : '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label="描述" span={2}>{selectedStrategy.description || '-'}</Descriptions.Item>
                    {selectedStrategy.params && Object.keys(selectedStrategy.params).length > 0 && (
                      <Descriptions.Item label="参数" span={2}>
                        {Object.entries(selectedStrategy.params).map(([key, value]) => (
                          <Tag key={key} style={{ margin: '2px' }}>
                            {key}: {String(value)}
                          </Tag>
                        ))}
                      </Descriptions.Item>
                    )}
                  </Descriptions>
                ),
              },
              {
                key: 'code',
                label: '策略代码',
                children: (
                  <div>
                    <Alert
                      message="策略 Python 代码"
                      description="这是该策略对应的可执行 Python 代码，可用于回测和实盘。"
                      type="info"
                      style={{ marginBottom: 16 }}
                    />
                    <Card
                      size="small"
                      extra={
                        <Button
                          size="small"
                          onClick={() => {
                            navigator.clipboard.writeText(generateStrategyCode(selectedStrategy));
                            message.success('代码已复制到剪贴板');
                          }}
                        >
                          复制代码
                        </Button>
                      }
                    >
                      <pre style={{
                        background: '#f5f5f5',
                        padding: 16,
                        borderRadius: 4,
                        maxHeight: 400,
                        overflow: 'auto',
                        fontSize: 13,
                        fontFamily: 'Monaco, Consolas, monospace',
                      }}>
                        {generateStrategyCode(selectedStrategy)}
                      </pre>
                    </Card>
                  </div>
                ),
              },
              {
                key: 'review',
                label: '审核结果',
                children: review ? (
                  <div>
                    <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
                      <Descriptions.Item label="审核决定">
                        {getDecisionTag(review.decision)}
                      </Descriptions.Item>
                      <Descriptions.Item label="总分">
                        <Progress
                          percent={review.score}
                          size="small"
                          status={review.score >= 80 ? 'success' : review.score >= 60 ? 'normal' : 'exception'}
                        />
                      </Descriptions.Item>
                    </Descriptions>

                    <Table
                      dataSource={review.criteria_results}
                      rowKey="name"
                      size="small"
                      pagination={false}
                      columns={[
                        {
                          title: '检查项',
                          dataIndex: 'name',
                          key: 'name',
                          render: (name: string) => {
                            const nameMap: Record<string, string> = {
                              sharpe_ratio: '夏普比率',
                              max_drawdown: '最大回撤',
                              annual_return: '年化收益',
                              excess_return: '超额收益',
                              stability: '收益稳定性',
                            };
                            return nameMap[name] || name;
                          },
                        },
                        {
                          title: '结果',
                          dataIndex: 'passed',
                          key: 'passed',
                          width: 80,
                          render: (passed: boolean) => (
                            <Tag color={passed ? 'success' : 'error'}>
                              {passed ? '通过' : '未通过'}
                            </Tag>
                          ),
                        },
                        {
                          title: '详情',
                          dataIndex: 'message',
                          key: 'message',
                        },
                      ]}
                    />
                  </div>
                ) : (
                  <Alert message="暂无审核记录" type="info" />
                ),
              },
              {
                key: 'lifecycle',
                label: '生命周期',
                children: (
                  <div>
                    <Alert
                      message="状态流转规则"
                      description="draft → research → candidate → paper → production → retired"
                      type="info"
                      style={{ marginBottom: 16 }}
                    />
                    <Descriptions bordered column={1} size="small">
                      <Descriptions.Item label="当前状态">
                        {getStatusTag(selectedStrategy.status)}
                      </Descriptions.Item>
                      <Descriptions.Item label="可流转到">
                        <Space>
                          {selectedStrategy.status === 'draft' && (
                            <Button size="small" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'research')}>
                              流转到: 研究中
                            </Button>
                          )}
                          {selectedStrategy.status === 'research' && (
                            <>
                              <Button size="small" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'candidate')}>
                                流转到: 候选
                              </Button>
                              <Button size="small" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'draft')}>
                                回退到: 草稿
                              </Button>
                            </>
                          )}
                          {selectedStrategy.status === 'candidate' && (
                            <>
                              <Button size="small" type="primary" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'paper')}>
                                流转到: 模拟盘
                              </Button>
                              <Button size="small" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'deprecated')}>
                                标记: 淘汰
                              </Button>
                            </>
                          )}
                          {selectedStrategy.status === 'paper' && (
                            <>
                              <Button size="small" type="primary" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'production')}>
                                流转到: 实盘
                              </Button>
                              <Button size="small" onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'deprecated')}>
                                标记: 淘汰
                              </Button>
                            </>
                          )}
                          {selectedStrategy.status === 'production' && (
                            <Button size="small" danger onClick={() => handleStatusChange(selectedStrategy.strategy_id, 'retired')}>
                              退役
                            </Button>
                          )}
                        </Space>
                      </Descriptions.Item>
                    </Descriptions>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Modal>

      {/* 脚本策略 Modal */}
      <Modal
        title="创建脚本策略"
        open={scriptVisible}
        onCancel={() => {
          setScriptVisible(false);
          scriptForm.resetFields();
        }}
        footer={null}
        width={900}
      >
        <Alert
          message="脚本策略说明"
          description="选择策略类型，配置参数，系统会自动生成可执行的 Python 脚本并创建策略。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Form
          form={scriptForm}
          layout="vertical"
          onFinish={(values) => {
            // 收集参数
            const params: Record<string, any> = {};
            const selectedType = scriptTypes.find(t => t.type === values.script_type);
            if (selectedType) {
              selectedType.params.forEach(p => {
                const value = values[`param_${p.name}`];
                if (value !== undefined && value !== '') {
                  params[p.name] = p.type === 'int' ? parseInt(value) :
                                   p.type === 'float' ? parseFloat(value) : value;
                } else {
                  params[p.name] = p.default;
                }
              });
            }

            // 创建脚本策略
            const newStrategy: StrategyConfig = {
              strategy_id: `script_${values.script_type}_${Date.now()}`,
              strategy_name: values.strategy_name || `${values.script_type} 策略`,
              strategy_type: values.script_type,
              strategy_version: 'v1',
              description: values.description || `基于 ${values.script_type} 的脚本策略`,
              status: 'draft',
              params: params,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            };

            const updated = [...strategies, newStrategy];
            setStrategies(updated);
            localStorage.setItem('strategies', JSON.stringify(updated));
            setScriptVisible(false);
            scriptForm.resetFields();
            message.success('脚本策略创建成功！');
          }}
        >
          <Card title="步骤1: 选择策略类型" size="small" style={{ marginBottom: 16 }}>
            <Form.Item
              label="策略类型"
              name="script_type"
              rules={[{ required: true, message: '请选择策略类型' }]}
            >
              <Select placeholder="选择策略类型" size="large">
                {scriptTypes.map(type => (
                  <Select.Option key={type.type} value={type.type}>
                    <div>
                      <strong>{type.name}</strong>
                      <div style={{ fontSize: 12, color: '#666' }}>{type.description}</div>
                    </div>
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          </Card>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.script_type !== currentValues.script_type}
          >
            {({ getFieldValue }) => {
              const selectedType = getFieldValue('script_type');
              const typeInfo = scriptTypes.find(t => t.type === selectedType);
              if (!typeInfo) return null;

              return (
                <>
                  <Card title="步骤2: 配置策略参数" size="small" style={{ marginBottom: 16 }}>
                    <Alert
                      message={`${typeInfo.name} 参数配置`}
                      description={typeInfo.description}
                      type="info"
                      style={{ marginBottom: 16 }}
                    />
                    {typeInfo.params.filter(p => p.type !== 'text').map(param => (
                      <Form.Item
                        key={param.name}
                        label={
                          <Space>
                            {param.description}
                            <Tag>{param.type}</Tag>
                          </Space>
                        }
                        name={`param_${param.name}`}
                        initialValue={String(param.default)}
                        rules={[{ required: true, message: `请输入${param.description}` }]}
                      >
                        <Input
                          type={param.type === 'int' || param.type === 'float' ? 'number' : 'text'}
                          placeholder={`默认值: ${param.default}`}
                          step={param.type === 'float' ? '0.01' : '1'}
                        />
                      </Form.Item>
                    ))}

                    {/* 自定义脚本代码编辑 */}
                    {selectedType === 'custom' && (
                      <Form.Item
                        label="Python 代码"
                        name="param_code"
                        rules={[{ required: true, message: '请输入策略代码' }]}
                      >
                        <Input.TextArea
                          rows={15}
                          placeholder={`def on_init(ctx):
    # 初始化参数
    ctx.set_param("lookback", 20)

def on_bar(ctx, bar):
    # 每根K线触发
    # 买入: ctx.buy(bar.ts_code, weight=0.05)
    # 卖出: ctx.sell(bar.ts_code)
    pass`}
                          style={{ fontFamily: 'Monaco, Consolas, monospace', fontSize: 13 }}
                        />
                      </Form.Item>
                    )}
                  </Card>

                  <Card title="步骤3: 配置策略信息" size="small" style={{ marginBottom: 16 }}>
                    <Form.Item
                      label="策略名称"
                      name="strategy_name"
                      rules={[{ required: true, message: '请输入策略名称' }]}
                    >
                      <Input placeholder={`例如: 我的${typeInfo.name}`} />
                    </Form.Item>

                    <Form.Item
                      label="策略描述"
                      name="description"
                    >
                      <TextArea rows={2} placeholder="描述这个策略的用途..." />
                    </Form.Item>
                  </Card>
                </>
              );
            }}
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" size="large">
                创建脚本策略
              </Button>
              <Button onClick={() => {
                setScriptVisible(false);
                scriptForm.resetFields();
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
