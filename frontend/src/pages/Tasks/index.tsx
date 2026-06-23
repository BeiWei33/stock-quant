import { useEffect, useState } from 'react';
import {
  Card,
  Button,
  Space,
  Table,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Descriptions,
  Badge,
  Spin,
  Alert,
  Progress,
  Popconfirm,
} from 'antd';
import {
  PlayCircleOutlined,
  ReloadOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import api from '../../api/client';
import { useTaskWebSocket, TaskProgress } from '../../hooks/useWebSocket';

export default function TasksPage() {
  const { tasks, connected, getActiveTasks, getCompletedTasks } = useTaskWebSocket();
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskProgress | null>(null);
  const [logModalVisible, setLogModalVisible] = useState(false);

  // Stock pick modal
  const [stockPickVisible, setStockPickVisible] = useState(false);
  const [stockPickLoading, setStockPickLoading] = useState(false);
  const [stockPickForm] = Form.useForm();

  const runTask = async (action: string, params?: any) => {
    try {
      const response = await api.post(`/api/tasks/${action}`, null, { params });
      const result = response.data;

      message.success(`任务已提交: ${result.task_id}`);

      return result;
    } catch (error: any) {
      const msg = error.response?.data?.detail || '任务执行失败';
      message.error(msg);
      throw error;
    }
  };

  const handleRunDaily = async () => {
    await runTask('daily');
  };

  const handleRunDoctor = async () => {
    await runTask('doctor');
  };

  const handleRunSnapshot = async () => {
    await runTask('snapshot');
  };

  const handleStockPick = async (values: any) => {
    setStockPickLoading(true);
    try {
      await runTask('stock-pick', values);
      setStockPickVisible(false);
      stockPickForm.resetFields();
    } catch (error) {
      // Error already handled in runTask
    } finally {
      setStockPickLoading(false);
    }
  };

  const handleResetPaper = async () => {
    try {
      const response = await api.post('/api/tasks/reset-paper', null, {
        params: { initial_cash: 10000 }
      });
      if (response.data.status === 'OK') {
        message.success(response.data.message || '模拟盘已重置');
      } else {
        message.error(response.data.message || '重置失败');
      }
    } catch (error: any) {
      message.error('重置失败');
    }
  };

  const viewTaskLog = (task: TaskProgress) => {
    setSelectedTask(task);
    setLogModalVisible(true);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'OK':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'FAIL':
      case 'TIMEOUT':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'RUNNING':
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case 'PENDING':
        return <SyncOutlined style={{ color: '#faad14' }} />;
      default:
        return null;
    }
  };

  const getStatusTag = (status: string) => {
    const colorMap: Record<string, string> = {
      OK: 'success',
      RUNNING: 'processing',
      FAIL: 'error',
      TIMEOUT: 'warning',
      PENDING: 'default',
    };
    return (
      <Tag icon={getStatusIcon(status)} color={colorMap[status] || 'default'}>
        {status}
      </Tag>
    );
  };

  const getActionLabel = (action: string) => {
    const labelMap: Record<string, string> = {
      daily: '日常流程',
      'stock-pick': '选股',
      doctor: '系统体检',
      snapshot: '快照归档',
      backtest: '回测',
    };
    return labelMap[action] || action;
  };

  const columns: ColumnsType<TaskProgress> = [
    {
      title: '任务ID',
      dataIndex: 'task_id',
      key: 'task_id',
      width: 200,
      ellipsis: true,
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 120,
      render: (action: string) => getActionLabel(action),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '进度',
      key: 'step',
      width: 200,
      render: (_: any, record: TaskProgress) => (
        <span style={{ fontSize: 12, color: '#666' }}>
          {record.step_name || '-'}
        </span>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (val: string) => val ? new Date(val).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, record: TaskProgress) => (
        <Button
          type="link"
          icon={<FileTextOutlined />}
          onClick={() => viewTaskLog(record)}
        >
          详情
        </Button>
      ),
    },
  ];

  const activeTasks = getActiveTasks();
  const completedTasks = getCompletedTasks();

  return (
    <div>
      {/* Connection Status */}
      <Alert
        message={
          <span>
            WebSocket 状态:{' '}
            <Badge
              status={connected ? 'success' : 'error'}
              text={connected ? '已连接' : '未连接'}
            />
          </span>
        }
        type={connected ? 'success' : 'warning'}
        showIcon
        style={{ marginBottom: 16 }}
      />

      {/* Quick Actions */}
      <Card title="快速操作" style={{ marginBottom: 24 }}>
        <Space wrap>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={handleRunDaily}
            disabled={!connected}
          >
            运行日常流程
          </Button>
          <Button
            icon={<ThunderboltOutlined />}
            onClick={() => setStockPickVisible(true)}
            disabled={!connected}
          >
            执行选股
          </Button>
          <Button onClick={handleRunDoctor} disabled={!connected}>
            系统体检
          </Button>
          <Button onClick={handleRunSnapshot} disabled={!connected}>
            快照归档
          </Button>
          <Popconfirm
            title="确定要重置模拟盘吗？"
            description="将清空所有交易记录，重置为初始资金 10,000 元"
            onConfirm={handleResetPaper}
            okText="确定"
            cancelText="取消"
          >
            <Button danger>
              重置模拟盘
            </Button>
          </Popconfirm>
        </Space>
      </Card>

      {/* Active Tasks */}
      {activeTasks.length > 0 && (
        <Card
          title={
            <span>
              <LoadingOutlined style={{ marginRight: 8 }} />
              进行中的任务 ({activeTasks.length})
            </span>
          }
          style={{ marginBottom: 24 }}
        >
          {activeTasks.map((task) => (
            <Card
              key={task.task_id}
              size="small"
              style={{ marginBottom: 8 }}
            >
              <Descriptions column={2} size="small">
                <Descriptions.Item label="任务">
                  {getActionLabel(task.action)}
                </Descriptions.Item>
                <Descriptions.Item label="状态">
                  {getStatusTag(task.status)}
                </Descriptions.Item>
                <Descriptions.Item label="进度" span={2}>
                  {task.step_name || '处理中...'}
                </Descriptions.Item>
                {task.stdout_tail && (
                  <Descriptions.Item label="输出" span={2}>
                    <pre
                      style={{
                        margin: 0,
                        fontSize: 12,
                        maxHeight: 100,
                        overflow: 'auto',
                        background: '#f5f5f5',
                        padding: 8,
                        borderRadius: 4,
                      }}
                    >
                      {task.stdout_tail}
                    </pre>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          ))}
        </Card>
      )}

      {/* Task History */}
      <Card title="任务历史">
        <Table
          dataSource={completedTasks}
          columns={columns}
          rowKey="task_id"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1000 }}
          size="small"
        />
      </Card>

      {/* Stock Pick Modal */}
      <Modal
        title="执行选股"
        open={stockPickVisible}
        onCancel={() => setStockPickVisible(false)}
        footer={null}
      >
        <Form
          form={stockPickForm}
          onFinish={handleStockPick}
          initialValues={{ scope: '30' }}
        >
          <Form.Item label="选股范围" name="scope">
            <Select
              options={[
                { label: '30只白马股', value: '30' },
                { label: '全市场', value: 'all' },
              ]}
            />
          </Form.Item>
          <Form.Item label="最低价" name="price_min">
            <Input type="number" placeholder="不限" />
          </Form.Item>
          <Form.Item label="最高价" name="price_max">
            <Input type="number" placeholder="不限" />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={stockPickLoading}
              block
            >
              执行选股
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Task Detail Modal */}
      <Modal
        title={`任务详情: ${selectedTask?.task_id || ''}`}
        open={logModalVisible}
        onCancel={() => setLogModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedTask && (
          <div>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="任务ID">{selectedTask.task_id}</Descriptions.Item>
              <Descriptions.Item label="操作">{getActionLabel(selectedTask.action)}</Descriptions.Item>
              <Descriptions.Item label="状态">{getStatusTag(selectedTask.status)}</Descriptions.Item>
              <Descriptions.Item label="返回码">{selectedTask.return_code ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="开始时间">
                {selectedTask.started_at ? new Date(selectedTask.started_at).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="结束时间">
                {selectedTask.ended_at ? new Date(selectedTask.ended_at).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="当前步骤" span={2}>
                {selectedTask.step_name || '-'}
              </Descriptions.Item>
            </Descriptions>

            {selectedTask.stdout_tail && (
              <Card title="标准输出" size="small" style={{ marginBottom: 16 }}>
                <pre
                  style={{
                    maxHeight: 400,
                    overflow: 'auto',
                    background: '#f5f5f5',
                    padding: 12,
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {selectedTask.stdout_tail}
                </pre>
              </Card>
            )}

            {selectedTask.stderr_tail && (
              <Card title="错误输出" size="small">
                <pre
                  style={{
                    maxHeight: 400,
                    overflow: 'auto',
                    background: '#fff2f0',
                    padding: 12,
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {selectedTask.stderr_tail}
                </pre>
              </Card>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
