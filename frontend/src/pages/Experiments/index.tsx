import { useEffect, useState } from 'react';
import {
  Card,
  Button,
  Table,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  message,
  Descriptions,
  Space,
  Tooltip,
  Progress,
  Spin,
  Alert,
  Steps,
  Popconfirm,
} from 'antd';
import {
  ExperimentOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  TrophyOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import api from '../../api/client';

interface Experiment {
  experiment_id: string;
  name: string;
  strategy_id: string;
  param_grid: Record<string, any[]>;
  metric: string;
  status: string;
  created_at: string;
  runs?: ExperimentRun[];
}

interface ExperimentRun {
  run_id: string;
  params: Record<string, any>;
  metrics: Record<string, number>;
  score: {
    total_score: number;
    grade: string;
    scores: Record<string, number>;
  };
  rank: number;
}

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [createVisible, setCreateVisible] = useState(false);
  const [createForm] = Form.useForm();
  const [strategies, setStrategies] = useState<any[]>([]);
  const [pollingExperimentId, setPollingExperimentId] = useState<string | null>(null);

  useEffect(() => {
    fetchExperiments();
    loadStrategies();
  }, []);

  // 轮询实验状态
  useEffect(() => {
    if (!pollingExperimentId) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/experiments/${pollingExperimentId}`);
        const experiment = response.data.data;

        if (experiment) {
          const taskStatus = experiment.task_status;
          if (taskStatus === 'completed') {
            message.success('实验完成！');
            setPollingExperimentId(null);
            fetchExperiments();
          } else if (taskStatus === 'failed') {
            message.error('实验失败: ' + (experiment.task_error || '未知错误'));
            setPollingExperimentId(null);
            fetchExperiments();
          }
        }
      } catch (error) {
        console.error('轮询实验状态失败', error);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [pollingExperimentId]);

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

  const fetchExperiments = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/experiments');
      setExperiments(response.data.data || []);
    } catch (error) {
      console.error('获取实验列表失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    try {
      const paramGrid = JSON.parse(values.param_grid);
      const response = await api.post('/api/experiments', {
        name: values.name,
        strategy_id: values.strategy_id,
        param_grid: paramGrid,
        metric: values.metric,
        universe: values.universe || 'all',
        rebalance: values.rebalance || 'weekly',
        start_date: values.start_date || '2025-01-01',
        end_date: values.end_date || '',
      });

      if (response.data.code === 200) {
        message.success('实验创建成功');
        setCreateVisible(false);
        createForm.resetFields();
        fetchExperiments();
      } else {
        message.error(response.data.message || '创建失败');
      }
    } catch (error: any) {
      message.error('创建失败: ' + (error.message || '未知错误'));
    }
  };

  const handleRun = async (experimentId: string) => {
    try {
      const response = await api.post(`/api/experiments/${experimentId}/run`);
      if (response.data.code === 200) {
        message.info('实验已提交运行，请等待完成');
        setPollingExperimentId(experimentId);
        fetchExperiments();
      } else {
        message.error(response.data.message || '运行失败');
      }
    } catch (error: any) {
      message.error('运行失败: ' + (error.message || '未知错误'));
    }
  };

  const handleDelete = async (experimentId: string) => {
    try {
      await api.delete(`/api/experiments/${experimentId}`);
      message.success('已删除');
      fetchExperiments();
    } catch (error: any) {
      message.error('删除失败');
    }
  };

  const handleViewDetail = async (experiment: Experiment) => {
    try {
      const response = await api.get(`/api/experiments/${experiment.experiment_id}`);
      setSelectedExperiment(response.data.data);
      setDetailVisible(true);
    } catch (error) {
      message.error('获取详情失败');
    }
  };

  const getGradeColor = (grade: string) => {
    const colorMap: Record<string, string> = {
      A: '#52c41a',
      B: '#1890ff',
      C: '#faad14',
      D: '#ff4d4f',
      F: '#d9d9d9',
    };
    return colorMap[grade] || '#d9d9d9';
  };

  const columns = [
    {
      title: '实验 ID',
      dataIndex: 'experiment_id',
      key: 'experiment_id',
      width: 200,
      ellipsis: true,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '策略',
      dataIndex: 'strategy_id',
      key: 'strategy_id',
      width: 120,
    },
    {
      title: '优化目标',
      dataIndex: 'metric',
      key: 'metric',
      width: 100,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={status === 'completed' ? 'success' : status === 'running' ? 'processing' : 'default'}>
          {status === 'completed' ? '已完成' : status === 'running' ? '运行中' : status}
        </Tag>
      ),
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
      width: 180,
      render: (_: any, record: Experiment) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record)}
            />
          </Tooltip>
          <Tooltip title="运行实验">
            <Button
              type="link"
              icon={<PlayCircleOutlined />}
              onClick={() => handleRun(record.experiment_id)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此实验？"
            onConfirm={() => handleDelete(record.experiment_id)}
          >
            <Tooltip title="删除">
              <Button type="link" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const runColumns = [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 80,
      render: (rank: number) => (
        <span style={{ fontWeight: rank <= 3 ? 'bold' : 'normal', color: rank <= 3 ? '#faad14' : undefined }}>
          #{rank}
        </span>
      ),
    },
    {
      title: '参数',
      key: 'params',
      width: 250,
      render: (_: any, record: ExperimentRun) => (
        <span style={{ fontSize: 12 }}>
          {JSON.stringify(record.params)}
        </span>
      ),
    },
    {
      title: '总收益',
      key: 'total_return',
      width: 120,
      render: (_: any, record: ExperimentRun) => {
        const val = record.metrics?.total_return;
        if (val == null) return '-';
        const percent = val * 100;
        return (
          <span style={{ color: percent >= 0 ? '#3f8600' : '#cf1322', fontWeight: 'bold' }}>
            {percent.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: '夏普',
      key: 'sharpe',
      width: 100,
      render: (_: any, record: ExperimentRun) => (
        <span style={{ fontWeight: 'bold' }}>
          {record.metrics?.sharpe?.toFixed(4) || '-'}
        </span>
      ),
    },
    {
      title: '年化收益',
      key: 'annual_return',
      width: 120,
      render: (_: any, record: ExperimentRun) => {
        const val = record.metrics?.annual_return;
        if (val == null) return '-';
        const percent = val * 100;
        return (
          <span style={{ color: percent >= 0 ? '#3f8600' : '#cf1322' }}>
            {percent.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: '最大回撤',
      key: 'max_drawdown',
      width: 120,
      render: (_: any, record: ExperimentRun) => {
        const val = record.metrics?.max_drawdown;
        if (val == null) return '-';
        return (
          <span style={{ color: '#cf1322' }}>
            {(val * 100).toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: '评分',
      key: 'score',
      width: 120,
      render: (_: any, record: ExperimentRun) => {
        if (!record.score) return '-';
        return (
          <Space>
            <Tag color={getGradeColor(record.score.grade)}>
              {record.score.grade}
            </Tag>
            <span>{record.score.total_score?.toFixed(1)}</span>
          </Space>
        );
      },
    },
  ];

  const getRadarOption = () => {
    if (!selectedExperiment?.runs?.length) return {};

    const bestRun = selectedExperiment.runs[0];
    if (!bestRun?.score?.scores) return {};

    const scores = bestRun.score.scores;
    const indicators = [
      { name: '收益', max: 100 },
      { name: '年化', max: 100 },
      { name: '夏普', max: 100 },
      { name: '回撤', max: 100 },
      { name: '胜率', max: 100 },
      { name: '稳定性', max: 100 },
    ];

    return {
      tooltip: {},
      radar: {
        indicator: indicators,
      },
      series: [{
        type: 'radar',
        data: [{
          value: [
            scores.return_score || 0,
            scores.annual_return || 0,
            scores.sharpe || 0,
            scores.max_drawdown || 0,
            scores.win_rate || 0,
            scores.stability || 0,
          ],
          name: '最优参数',
        }],
      }],
    };
  };

  return (
    <div>
      {/* 操作指引 */}
      <Alert
        message="实验优化使用指南"
        description={
          <div>
            <p><strong>实验优化</strong>可以帮你自动搜索最优策略参数，步骤如下：</p>
            <ol style={{ margin: '8px 0', paddingLeft: 20 }}>
              <li>点击「创建实验」按钮，填写实验名称、选择策略、输入参数搜索空间</li>
              <li>在实验列表中，点击「眼睛」图标查看详情</li>
              <li>在详情页面，点击「运行实验」按钮开始参数搜索</li>
              <li>等待运行完成，查看评分雷达图和最优参数排名</li>
            </ol>
            <p style={{ color: '#666', fontSize: 12 }}>
              💡 提示：参数组合越多，运行时间越长。建议先用少量参数测试。
            </p>
          </div>
        }
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        style={{ marginBottom: 16 }}
        closable
      />

      <Card
        title={
          <Space>
            <ExperimentOutlined />
            实验管理
          </Space>
        }
        extra={
          <Button type="primary" onClick={() => setCreateVisible(true)}>
            创建实验
          </Button>
        }
      >
        <Table
          dataSource={experiments}
          columns={columns}
          rowKey="experiment_id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1000 }}
          size="small"
        />
      </Card>

      {/* 创建实验 Modal */}
      <Modal
        title="创建实验"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={createForm}
          onFinish={handleCreate}
          layout="vertical"
          initialValues={{ metric: 'sharpe', name: '动量参数优化', strategy_id: 'momentum_rank' }}
        >
          <Form.Item
            label="实验名称"
            name="name"
            rules={[{ required: true, message: '请输入实验名称' }]}
          >
            <Input placeholder="例如：动量参数优化" />
          </Form.Item>

          <Form.Item
            label="选择策略"
            name="strategy_id"
            rules={[{ required: true, message: '请选择策略' }]}
          >
            <Select
              options={strategies.map(s => ({
                label: `${s.strategy_name} (${s.strategy_type})`,
                value: s.strategy_type,
              }))}
            />
          </Form.Item>

          <Form.Item
            label={
              <Space>
                参数搜索空间
                <Tooltip title='JSON 格式，每个参数对应一个数组。系统会遍历所有组合进行回测。'>
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            }
            name="param_grid"
            rules={[{ required: true, message: '请输入参数搜索空间' }]}
          >
            <Input.TextArea
              rows={4}
              placeholder={`参数示例（只支持 max_holdings）：
{
  "max_holdings": [10, 15, 20, 25, 30]
}

这会测试持有 10、15、20、25、30 只股票的效果`}
            />
          </Form.Item>

          <Form.Item
            label="优化目标"
            name="metric"
            tooltip="选择要优化的指标，系统会按此指标对结果排名"
          >
            <Select
              options={[
                { label: '夏普比率 (推荐)', value: 'sharpe' },
                { label: '年化收益', value: 'annual_return' },
                { label: '最大回撤 (越小越好)', value: 'max_drawdown' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="股票池"
            name="universe"
            tooltip="选择回测使用的股票池"
          >
            <Select
              options={[
                { label: '全市场 (5,895只)', value: 'all' },
                { label: '沪深300 (194只)', value: 'csi300' },
                { label: '中证500 (358只)', value: 'csi500' },
                { label: '中证1000 (769只)', value: 'csi1000' },
                { label: '上证50 (50只)', value: 'sse50' },
                { label: '创业板指 (100只)', value: 'chinext' },
                { label: '科创50 (44只)', value: 'star50' },
                { label: '沪深300+中证500', value: 'csi800' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="再平衡频率"
            name="rebalance"
            tooltip="策略多久调整一次持仓"
          >
            <Select
              options={[
                { label: '每周（适合动量策略）', value: 'weekly' },
                { label: '每月（适合价值/质量策略）', value: 'monthly' },
              ]}
            />
          </Form.Item>

          <Form.Item label="回测开始日期" name="start_date">
            <Input placeholder="2025-01-01" />
          </Form.Item>

          <Form.Item label="回测结束日期" name="end_date">
            <Input placeholder="默认今天" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              创建实验
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 实验详情 Modal */}
      <Modal
        title={`实验详情: ${selectedExperiment?.name || ''}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={1000}
      >
        {selectedExperiment && (
          <div>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="实验 ID">{selectedExperiment.experiment_id}</Descriptions.Item>
              <Descriptions.Item label="策略">{selectedExperiment.strategy_id}</Descriptions.Item>
              <Descriptions.Item label="优化目标">{selectedExperiment.metric}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={selectedExperiment.status === 'completed' ? 'success' : 'default'}>
                  {selectedExperiment.status === 'completed' ? '已完成' : selectedExperiment.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="参数空间" span={2}>
                <code>{JSON.stringify(selectedExperiment.param_grid)}</code>
              </Descriptions.Item>
            </Descriptions>

            {selectedExperiment.status !== 'completed' && (
              <Card size="small" style={{ marginBottom: 16, textAlign: 'center' }}>
                <Space direction="vertical">
                  <span>实验尚未运行</span>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => {
                      handleRun(selectedExperiment.experiment_id);
                      setDetailVisible(false);
                    }}
                  >
                    运行实验
                  </Button>
                </Space>
              </Card>
            )}

            {selectedExperiment.runs && selectedExperiment.runs.length > 0 && (
              <>
                <Card title="评分雷达图（最优参数）" size="small" style={{ marginBottom: 16 }}>
                  <ReactECharts option={getRadarOption()} style={{ height: 300 }} />
                </Card>

                <Card title="运行结果排名" size="small">
                  <Table
                    dataSource={selectedExperiment.runs}
                    columns={runColumns}
                    rowKey="run_id"
                    pagination={false}
                    scroll={{ x: 800 }}
                    size="small"
                  />
                </Card>
              </>
            )}

            {selectedExperiment.status === 'completed' && (!selectedExperiment.runs || selectedExperiment.runs.length === 0) && (
              <Card size="small" style={{ textAlign: 'center' }}>
                <span>实验已完成但无运行结果</span>
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
