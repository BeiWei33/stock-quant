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
  const [detailVisible, setDetailVisible] = useState(false);
  const [scriptVisible, setScriptVisible] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyConfig | null>(null);
  const [review, setReview] = useState<StrategyReview | null>(null);
  const [scriptTypes, setScriptTypes] = useState<ScriptStrategy[]>([]);
  const [createForm] = Form.useForm();
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
      width: 200,
      render: (_: any, record: StrategyConfig) => (
        <Space>
          <Tooltip title="查看详情">
            <Button type="link" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)} />
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

      {/* 策略详情 Modal */}
      <Modal
        title={`策略详情: ${selectedStrategy?.strategy_name || ''}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
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
                  </Descriptions>
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
