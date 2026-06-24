import { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Form,
  Input,
  Select,
  Button,
  DatePicker,
  Table,
  Tag,
  Statistic,
  Spin,
  message,
  Tabs,
  Checkbox,
  Space,
  Popconfirm,
  Badge,
} from 'antd';
import {
  ReloadOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import api from '../../api/client';

const { RangePicker } = DatePicker;

interface BacktestTask {
  task_id: string;
  status: string;
  params: any;
  result?: any;
  error?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface BacktestMetrics {
  total_return: number;
  annual_return: number;
  volatility: number;
  sharpe: number;
  max_drawdown: number;
  excess_return: number;
  information_ratio: number;
  rebalance_count: number;
  average_turnover: number;
}

interface Experiment {
  experiment_id: string;
  experiment_name: string;
  created_at: string;
  status: string;
  params: any;
  metrics: BacktestMetrics;
}

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [tasks, setTasks] = useState<BacktestTask[]>([]);
  const [polling, setPolling] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchResults();
    fetchTasks();
    loadStrategies();
  }, []);

  // 从 localStorage 加载策略列表
  const loadStrategies = () => {
    const defaultStrategies = [
      { strategy_id: 'momentum_rank', strategy_name: '动量排名策略', strategy_type: 'momentum_rank' },
      { strategy_id: 'quality_rank', strategy_name: '质量排名策略', strategy_type: 'quality_rank' },
      { strategy_id: 'momentum_rank_trend', strategy_name: '动量+趋势策略', strategy_type: 'momentum_rank_trend' },
      { strategy_id: 'quality_rank_trend', strategy_name: '质量+趋势策略', strategy_type: 'quality_rank_trend' },
    ];

    try {
      const saved = localStorage.getItem('strategies');
      if (saved) {
        const parsed = JSON.parse(saved);
        // 合并默认策略和用户创建的策略
        const allStrategies = [...defaultStrategies];
        parsed.forEach((s: any) => {
          if (!allStrategies.find(d => d.strategy_id === s.strategy_id)) {
            allStrategies.push({
              strategy_id: s.strategy_id,
              strategy_name: s.strategy_name,
              strategy_type: s.strategy_type,
            });
          }
        });
        setStrategies(allStrategies);
      } else {
        setStrategies(defaultStrategies);
      }
    } catch {
      setStrategies(defaultStrategies);
    }
  };

  // Polling for running tasks
  useEffect(() => {
    if (!polling) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/backtest/status/${polling}`);
        const task = response.data.data;

        if (task.status === 'completed') {
          message.success('回测完成');
          setResults(task.result);
          setPolling(null);
          fetchTasks();
          setLoading(false);
        } else if (task.status === 'failed') {
          message.error(`回测失败: ${task.error || '未知错误'}`);
          setPolling(null);
          fetchTasks();
          setLoading(false);
        }
      } catch (error) {
        console.error('轮询失败', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [polling]);

  const fetchResults = async () => {
    try {
      const response = await api.get('/api/backtest/results');
      setResults(response.data.data);
    } catch (error) {
      console.error('获取回测结果失败', error);
    }
  };

  const fetchTasks = async () => {
    try {
      const response = await api.get('/api/backtest/tasks');
      setTasks(response.data.data || []);
    } catch (error) {
      console.error('获取任务列表失败', error);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await api.delete(`/api/backtest/tasks/${taskId}`);
      message.success('已删除');
      fetchTasks();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleRunBacktest = async (values: any) => {
    setLoading(true);
    try {
      const params: any = {
        start_date: values.dateRange?.[0]?.format('YYYY-MM-DD') || '2025-01-01',
        end_date: values.dateRange?.[1]?.format('YYYY-MM-DD') || new Date().toISOString().split('T')[0],
        strategy: values.strategy || 'momentum_rank',
        rebalance: values.rebalance || 'weekly',
        use_local: values.useLocal || false,
        universe: values.universe || 'all',
      };
      if (values.limit) params.limit = values.limit;

      const response = await api.post('/api/backtest/run', null, { params });
      const result = response.data;

      if (result.code === 200 && result.data?.task_id) {
        message.info('回测任务已提交，请等待完成');
        setPolling(result.data.task_id);
        fetchTasks();
      } else {
        message.error(result.message || '提交失败');
        setLoading(false);
      }
    } catch (error: any) {
      message.error('提交失败: ' + (error.message || '未知错误'));
      setLoading(false);
    }
  };

  const getEquityOption = () => {
    if (!results?.equity_curve?.length) return {};

    const dates = results.equity_curve.map((item: any) => item.trade_date);
    const strategyEquity = results.equity_curve.map((item: any) => item.strategy_equity || item.portfolio_equity);
    const benchmarkEquity = results.benchmark_equity_curve?.map((item: any) => item.benchmark_equity) || [];

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: {
        data: ['策略净值', '基准净值'],
        top: 10,
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
      },
      yAxis: {
        type: 'value',
        name: '净值',
        axisLabel: {
          formatter: '{value}',
        },
      },
      series: [
        {
          name: '策略净值',
          type: 'line',
          data: strategyEquity,
          smooth: true,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.1 },
        },
        {
          name: '基准净值',
          type: 'line',
          data: benchmarkEquity,
          smooth: true,
          lineStyle: { width: 2, type: 'dashed' },
        },
      ],
    };
  };

  const experimentColumns = [
    {
      title: '实验名称',
      dataIndex: 'experiment_name',
      key: 'experiment_name',
      ellipsis: true,
    },
    {
      title: '策略',
      dataIndex: 'strategies',
      key: 'strategies',
      render: (val: string[]) => val?.join(', ') || '-',
    },
    {
      title: '总收益',
      key: 'total_return',
      align: 'right' as const,
      render: (_: any, record: Experiment) => {
        const val = record.metrics?.total_return;
        return val != null ? `${(val * 100).toFixed(2)}%` : '-';
      },
    },
    {
      title: '夏普',
      key: 'sharpe',
      align: 'right' as const,
      render: (_: any, record: Experiment) => {
        const val = record.metrics?.sharpe;
        return val?.toFixed(4) || '-';
      },
    },
    {
      title: '最大回撤',
      key: 'max_drawdown',
      align: 'right' as const,
      render: (_: any, record: Experiment) => {
        const val = record.metrics?.max_drawdown;
        return val != null ? `${(val * 100).toFixed(2)}%` : '-';
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'OK' ? 'success' : 'error'}>{status}</Tag>
      ),
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
    },
  ];

  return (
    <div>
      <Tabs
        defaultActiveKey="run"
        items={[
          {
            key: 'run',
            label: '运行回测',
            children: (
              <>
                {/* Backtest Form */}
                <Card title="回测参数" style={{ marginBottom: 24 }}>
                  <Form
                    form={form}
                    onFinish={handleRunBacktest}
                    layout="inline"
                    initialValues={{ rebalance: 'weekly', universe: 'all', strategy: 'momentum_rank' }}
                  >
                    <Form.Item label="日期范围" name="dateRange">
                      <RangePicker
                        defaultValue={[dayjs('2025-01-01'), dayjs()]}
                      />
                    </Form.Item>
                    <Form.Item label="策略" name="strategy">
                      <Select style={{ width: 180 }}>
                        {strategies.map(s => (
                          <Select.Option key={s.strategy_id} value={s.strategy_type}>
                            {s.strategy_name}
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                    <Form.Item label="股票池" name="universe">
                      <Select style={{ width: 150 }}>
                        <Select.Option value="all">全市场 (717只)</Select.Option>
                        <Select.Option value="csi300">沪深300 (300只)</Select.Option>
                        <Select.Option value="csi500">中证500 (500只)</Select.Option>
                        <Select.Option value="csi800">沪深300+中证500</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="再平衡" name="rebalance">
                      <Select style={{ width: 120 }}>
                        <Select.Option value="weekly">周</Select.Option>
                        <Select.Option value="monthly">月</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="股票数" name="limit">
                      <Input placeholder="默认全池" style={{ width: 120 }} />
                    </Form.Item>
                    <Form.Item name="useLocal" valuePropName="checked">
                      <Checkbox>使用本地数据</Checkbox>
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={loading}>
                        开始回测
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>

                {/* Running Task */}
                {polling && (
                  <Card style={{ marginBottom: 16 }}>
                    <Space>
                      <Spin />
                      <span>回测运行中，请等待...</span>
                      <Tag color="processing">任务ID: {polling}</Tag>
                    </Space>
                  </Card>
                )}

                {/* Results */}
                {results?.metrics && (
                  <>
                    {/* 核心指标卡片 */}
                    <Card title="核心指标" style={{ marginBottom: 16 }}>
                      <Row gutter={[16, 16]}>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="年化收益"
                            value={results.metrics.annual_return * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{
                              color: results.metrics.annual_return >= 0 ? '#3f8600' : '#cf1322',
                            }}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="夏普比率"
                            value={results.metrics.sharpe}
                            precision={4}
                            valueStyle={{
                              color: results.metrics.sharpe >= 1 ? '#3f8600' : results.metrics.sharpe >= 0 ? '#1890ff' : '#cf1322',
                            }}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="最大回撤"
                            value={results.metrics.max_drawdown * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{ color: '#cf1322' }}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="信息比率"
                            value={results.metrics.information_ratio}
                            precision={4}
                            valueStyle={{
                              color: results.metrics.information_ratio >= 0 ? '#3f8600' : '#cf1322',
                            }}
                          />
                        </Col>
                      </Row>
                    </Card>

                    {/* 收益分析 */}
                    <Card title="收益分析" style={{ marginBottom: 16 }}>
                      <Row gutter={[16, 16]}>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="总收益"
                            value={results.metrics.total_return * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{
                              color: results.metrics.total_return >= 0 ? '#3f8600' : '#cf1322',
                            }}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="年化波动率"
                            value={results.metrics.volatility * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="超额收益"
                            value={(results.metrics.excess_return || 0) * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{
                              color: (results.metrics.excess_return || 0) >= 0 ? '#3f8600' : '#cf1322',
                            }}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="跟踪误差"
                            value={(results.metrics.tracking_error || 0) * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                      </Row>
                    </Card>

                    {/* 基准对比 */}
                    <Card title="基准对比" style={{ marginBottom: 16 }}>
                      <Row gutter={[16, 16]}>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="基准总收益"
                            value={(results.metrics.benchmark_total_return || 0) * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="基准年化收益"
                            value={(results.metrics.benchmark_annual_return || 0) * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="基准波动率"
                            value={(results.metrics.benchmark_volatility || 0) * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="相关系数"
                            value={results.metrics.benchmark_correlation || 0}
                            precision={4}
                          />
                        </Col>
                      </Row>
                    </Card>

                    {/* 持仓统计 */}
                    <Card title="持仓统计" style={{ marginBottom: 16 }}>
                      <Row gutter={[16, 16]}>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="再平衡次数"
                            value={results.metrics.rebalance_count || 0}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="平均持仓数"
                            value={results.metrics.average_holdings || 0}
                            precision={1}
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="平均换手率"
                            value={(results.metrics.average_turnover || 0) * 100}
                            precision={2}
                            suffix="%"
                          />
                        </Col>
                        <Col xs={12} sm={6}>
                          <Statistic
                            title="Beta"
                            value={results.metrics.beta || 0}
                            precision={4}
                          />
                        </Col>
                      </Row>
                    </Card>
                      </Col>
                    </Row>

                    {/* Equity Curve */}
                    <Card title="净值曲线" style={{ marginBottom: 24 }}>
                      <ReactECharts option={getEquityOption()} style={{ height: 400 }} />
                    </Card>
                  </>
                )}
              </>
            ),
          },
          {
            key: 'tasks',
            label: `任务记录 (${tasks.length})`,
            children: (
              <Card>
                <Table
                  dataSource={tasks}
                  columns={[
                    {
                      title: '任务ID',
                      dataIndex: 'task_id',
                      key: 'task_id',
                      width: 200,
                      ellipsis: true,
                    },
                    {
                      title: '策略',
                      key: 'strategy',
                      width: 120,
                      render: (_: any, record: BacktestTask) => record.params?.strategy || '-',
                    },
                    {
                      title: '股票池',
                      key: 'universe',
                      width: 100,
                      render: (_: any, record: BacktestTask) => {
                        const map: Record<string, string> = { all: '全市场', csi300: '沪深300', csi500: '中证500', csi800: '沪深800' };
                        return map[record.params?.universe] || record.params?.universe;
                      },
                    },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      key: 'status',
                      width: 100,
                      render: (status: string) => {
                        const config: Record<string, { color: string; icon: any; text: string }> = {
                          pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
                          running: { color: 'processing', icon: <LoadingOutlined />, text: '运行中' },
                          completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
                          failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
                        };
                        const c = config[status] || config.pending;
                        return <Tag icon={c.icon} color={c.color}>{c.text}</Tag>;
                      },
                    },
                    {
                      title: '创建时间',
                      dataIndex: 'created_at',
                      key: 'created_at',
                      width: 180,
                      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
                    },
                    {
                      title: '操作',
                      key: 'actions',
                      width: 120,
                      render: (_: any, record: BacktestTask) => (
                        <Space>
                          {record.status === 'completed' && (
                            <Button
                              type="link"
                              size="small"
                              onClick={() => {
                                setResults(record.result);
                                message.success('已加载结果');
                              }}
                            >
                              查看
                            </Button>
                          )}
                          <Popconfirm
                            title="确定删除此任务？"
                            onConfirm={() => handleDeleteTask(record.task_id)}
                          >
                            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                  rowKey="task_id"
                  pagination={{ pageSize: 20 }}
                  scroll={{ x: 1000 }}
                  size="small"
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
