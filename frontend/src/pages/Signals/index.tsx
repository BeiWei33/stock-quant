import { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Space, DatePicker, Select, message, Row, Col, Statistic } from 'antd';
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import api from '../../api/client';

const { RangePicker } = DatePicker;

interface Signal {
  trade_date: string;
  ts_code: string;
  name: string;
  strategy_id: string;
  signal_type: string;
  score: number;
  price: number;
  reason: string;
  target_weight: number;
}

interface SignalStats {
  total_signals: number;
  buy_signals: number;
  sell_signals: number;
  win_rate_1d: number | null;
  win_rate_5d: number | null;
  win_rate_10d: number | null;
  avg_return_1d: number | null;
  avg_return_5d: number | null;
  avg_return_10d: number | null;
  best_signal_return: number | null;
  worst_signal_return: number | null;
  sharpe_ratio: number | null;
}

export default function SignalsPage() {
  const [loading, setLoading] = useState(false);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [stats, setStats] = useState<SignalStats | null>(null);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const [filters, setFilters] = useState({
    signalType: undefined as string | undefined,
    dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
  });

  useEffect(() => {
    fetchSignals();
    fetchStats();
  }, [pagination.current, pagination.pageSize, filters]);

  const fetchSignals = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: pagination.current,
        page_size: pagination.pageSize,
      };

      if (filters.signalType) {
        params.signal_type = filters.signalType;
      }
      if (filters.dateRange) {
        params.start_date = filters.dateRange[0].format('YYYY-MM-DD');
        params.end_date = filters.dateRange[1].format('YYYY-MM-DD');
      }

      const response = await api.get('/api/signals', { params });
      const { data, total } = response.data;

      setSignals(data || []);
      setPagination(prev => ({ ...prev, total }));
    } catch (error) {
      message.error('获取信号数据失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await api.get('/api/signals/stats');
      setStats(response.data.data);
    } catch (error) {
      console.error('获取统计数据失败', error);
    }
  };

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const params: any = { format };
      if (filters.signalType) {
        params.signal_type = filters.signalType;
      }
      if (filters.dateRange) {
        params.start_date = filters.dateRange[0].format('YYYY-MM-DD');
        params.end_date = filters.dateRange[1].format('YYYY-MM-DD');
      }

      const response = await api.get('/api/signals/export', {
        params,
        responseType: 'blob',
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `signals.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  const columns: ColumnsType<Signal> = [
    {
      title: '日期',
      dataIndex: 'trade_date',
      key: 'trade_date',
      width: 120,
      sorter: (a, b) => a.trade_date.localeCompare(b.trade_date),
    },
    {
      title: '方向',
      dataIndex: 'signal_type',
      key: 'signal_type',
      width: 80,
      render: (type: string) => (
        <Tag color={type === 'BUY' ? 'success' : 'error'}>
          {type === 'BUY' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
    },
    {
      title: '策略',
      dataIndex: 'strategy_id',
      key: 'strategy_id',
      width: 120,
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      align: 'right',
      render: (val: number) => val ? `¥${val.toFixed(2)}` : '-',
    },
    {
      title: '评分',
      dataIndex: 'score',
      key: 'score',
      width: 100,
      align: 'right',
      sorter: (a, b) => (a.score || 0) - (b.score || 0),
      render: (val: number) => val?.toFixed(4) || '-',
    },
    {
      title: '目标权重',
      dataIndex: 'target_weight',
      key: 'target_weight',
      width: 100,
      align: 'right',
      render: (val: number) => val ? `${(val * 100).toFixed(1)}%` : '-',
    },
    {
      title: '理由',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
    },
  ];

  return (
    <div>
      {/* Statistics Cards */}
      {stats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="买入信号" value={stats.buy_signals} valueStyle={{ color: '#52c41a' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="卖出信号" value={stats.sell_signals} valueStyle={{ color: '#ff4d4f' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic title="总信号数" value={stats.total_signals} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic
                title="5日胜率"
                value={stats.win_rate_5d ? stats.win_rate_5d * 100 : 0}
                precision={1}
                suffix="%"
                valueStyle={{ color: stats.win_rate_5d && stats.win_rate_5d > 0.5 ? '#52c41a' : '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic
                title="5日平均收益"
                value={stats.avg_return_5d ? stats.avg_return_5d * 100 : 0}
                precision={2}
                suffix="%"
                valueStyle={{ color: stats.avg_return_5d && stats.avg_return_5d > 0 ? '#52c41a' : '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic
                title="夏普比率"
                value={stats.sharpe_ratio || 0}
                precision={2}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic
                title="最佳信号收益"
                value={stats.best_signal_return ? stats.best_signal_return * 100 : 0}
                precision={2}
                suffix="%"
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card>
              <Statistic
                title="最差信号收益"
                value={stats.worst_signal_return ? stats.worst_signal_return * 100 : 0}
                precision={2}
                suffix="%"
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Filters and Actions */}
      <Card
        title="信号历史"
        extra={
          <Space>
            <Select
              placeholder="信号类型"
              allowClear
              style={{ width: 120 }}
              onChange={(value) => setFilters(prev => ({ ...prev, signalType: value }))}
              options={[
                { label: '买入', value: 'BUY' },
                { label: '卖出', value: 'SELL' },
              ]}
            />
            <RangePicker
              onChange={(dates) => setFilters(prev => ({
                ...prev,
                dateRange: dates as [dayjs.Dayjs, dayjs.Dayjs] | null,
              }))}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchSignals}>
              刷新
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => handleExport('csv')}>
              导出CSV
            </Button>
            <Button onClick={() => handleExport('json')}>导出JSON</Button>
          </Space>
        }
      >
        <Table
          dataSource={signals}
          columns={columns}
          rowKey={(record) => `${record.trade_date}-${record.ts_code}-${record.signal_type}`}
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => setPagination(prev => ({ ...prev, current: page, pageSize })),
          }}
          scroll={{ x: 1200 }}
          size="small"
        />
      </Card>
    </div>
  );
}
