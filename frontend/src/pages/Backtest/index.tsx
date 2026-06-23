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
} from 'antd';
import ReactECharts from 'echarts-for-react';
import dayjs from 'dayjs';
import api from '../../api/client';

const { RangePicker } = DatePicker;

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
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchResults();
    fetchExperiments();
  }, []);

  const fetchResults = async () => {
    try {
      const response = await api.get('/api/backtest/results');
      setResults(response.data.data);
    } catch (error) {
      console.error('获取回测结果失败', error);
    }
  };

  const fetchExperiments = async () => {
    try {
      const response = await api.get('/api/backtest/experiments');
      setExperiments(response.data.data || []);
    } catch (error) {
      console.error('获取实验列表失败', error);
    }
  };

  const handleRunBacktest = async (values: any) => {
    setLoading(true);
    try {
      const params: any = {
        start_date: values.dateRange?.[0]?.format('YYYY-MM-DD') || '2025-01-01',
        end_date: values.dateRange?.[1]?.format('YYYY-MM-DD') || new Date().toISOString().split('T')[0],
        rebalance: values.rebalance || 'weekly',
      };
      if (values.limit) params.limit = values.limit;

      const response = await api.post('/api/backtest/run', null, { params });
      const data = response.data.data;

      if (data.status === 'OK') {
        message.success('回测完成');
        setResults(data.result);
        fetchExperiments();
      } else {
        message.error(`回测失败: ${data.stderr || 'Unknown error'}`);
      }
    } catch (error: any) {
      message.error('回测执行失败');
    } finally {
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
                    initialValues={{ rebalance: 'weekly' }}
                  >
                    <Form.Item label="日期范围" name="dateRange">
                      <RangePicker
                        defaultValue={[dayjs('2025-01-01'), dayjs()]}
                      />
                    </Form.Item>
                    <Form.Item label="再平衡" name="rebalance">
                      <Select style={{ width: 120 }}>
                        <Select.Option value="weekly">周</Select.Option>
                        <Select.Option value="monthly">月</Select.Option>
                      </Select>
                    </Form.Item>
                    <Form.Item label="股票数" name="limit">
                      <Input placeholder="默认全市场" style={{ width: 120 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" htmlType="submit" loading={loading}>
                        开始回测
                      </Button>
                    </Form.Item>
                  </Form>
                </Card>

                {/* Results */}
                {results?.metrics && (
                  <>
                    {/* Metrics Cards */}
                    <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                      <Col xs={12} sm={6}>
                        <Card>
                          <Statistic
                            title="年化收益"
                            value={results.metrics.annual_return * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{
                              color: results.metrics.annual_return >= 0 ? '#3f8600' : '#cf1322',
                            }}
                          />
                        </Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card>
                          <Statistic
                            title="夏普比率"
                            value={results.metrics.sharpe}
                            precision={4}
                          />
                        </Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card>
                          <Statistic
                            title="最大回撤"
                            value={results.metrics.max_drawdown * 100}
                            precision={2}
                            suffix="%"
                            valueStyle={{ color: '#cf1322' }}
                          />
                        </Card>
                      </Col>
                      <Col xs={12} sm={6}>
                        <Card>
                          <Statistic
                            title="信息比率"
                            value={results.metrics.information_ratio}
                            precision={4}
                          />
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
            key: 'experiments',
            label: `实验记录 (${experiments.length})`,
            children: (
              <Card>
                <Table
                  dataSource={experiments}
                  columns={experimentColumns}
                  rowKey="experiment_id"
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
