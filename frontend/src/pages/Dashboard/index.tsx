import { useEffect, useState } from 'react';
import { Row, Col, Card, Table, Tag, Statistic, Spin, message } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons';
import api from '../../api/client';

interface StatusCard {
  label: string;
  value: string;
  status: string;
}

interface AccountMetrics {
  trade_date: string;
  total_asset: number;
  cash: number;
  market_value: number;
  position_ratio: number;
  daily_return: number;
  cum_return: number;
  drawdown: number;
}

interface Signal {
  ts_code: string;
  name: string;
  signal_type: string;
  score: number;
  price: number;
  reason: string;
}

interface Position {
  ts_code: string;
  name: string;
  quantity: number;
  weight: number;
  market_value: number;
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [statusCards, setStatusCards] = useState<StatusCard[]>([]);
  const [accountMetrics, setAccountMetrics] = useState<AccountMetrics | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [overviewRes, signalsRes, positionsRes] = await Promise.all([
        api.get('/api/dashboard/overview'),
        api.get('/api/dashboard/signals/today'),
        api.get('/api/dashboard/positions'),
      ]);

      setStatusCards(overviewRes.data.data.status_cards || []);
      setAccountMetrics(overviewRes.data.data.account_metrics);
      setSignals(signalsRes.data.data.signals || []);
      setPositions(positionsRes.data.data.positions || []);
    } catch (error) {
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'warning':
        return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  const signalColumns = [
    {
      title: '方向',
      dataIndex: 'signal_type',
      key: 'signal_type',
      render: (type: string) => (
        <Tag color={type === 'BUY' ? 'success' : 'error'}>
          {type === 'BUY' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    { title: '代码', dataIndex: 'ts_code', key: 'ts_code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (val: number) => val?.toFixed(2) || '-',
    },
    {
      title: '评分',
      dataIndex: 'score',
      key: 'score',
      render: (val: number) => val?.toFixed(4) || '-',
    },
    { title: '理由', dataIndex: 'reason', key: 'reason' },
  ];

  const positionColumns = [
    { title: '代码', dataIndex: 'ts_code', key: 'ts_code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '数量', dataIndex: 'quantity', key: 'quantity' },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      render: (val: number) => `${(val * 100).toFixed(1)}%`,
    },
    {
      title: '市值',
      dataIndex: 'market_value',
      key: 'market_value',
      render: (val: number) => `¥${val?.toLocaleString() || '-'}`,
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      {/* Status Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {statusCards.map((card, index) => (
          <Col xs={24} sm={12} lg={6} key={index}>
            <Card>
              <Statistic
                title={card.label}
                value={card.value}
                prefix={getStatusIcon(card.status)}
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* Account Metrics */}
      {accountMetrics && (
        <Card title="账户概览" style={{ marginBottom: 24 }}>
          <Row gutter={[16, 16]}>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="总资产"
                value={accountMetrics.total_asset}
                precision={2}
                prefix="¥"
              />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="可用现金"
                value={accountMetrics.cash}
                precision={2}
                prefix="¥"
              />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="持仓市值"
                value={accountMetrics.market_value}
                precision={2}
                prefix="¥"
              />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="仓位"
                value={accountMetrics.position_ratio * 100}
                precision={1}
                suffix="%"
              />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="日收益"
                value={accountMetrics.daily_return * 100}
                precision={2}
                suffix="%"
                prefix={accountMetrics.daily_return >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                valueStyle={{ color: accountMetrics.daily_return >= 0 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Statistic
                title="累计收益"
                value={accountMetrics.cum_return * 100}
                precision={2}
                suffix="%"
                prefix={accountMetrics.cum_return >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                valueStyle={{ color: accountMetrics.cum_return >= 0 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
          </Row>
        </Card>
      )}

      {/* Today's Signals */}
      <Card title="今日信号" style={{ marginBottom: 24 }}>
        <Table
          dataSource={signals}
          columns={signalColumns}
          rowKey={(record) => `${record.ts_code}-${record.signal_type}`}
          pagination={false}
          size="small"
        />
      </Card>

      {/* Latest Positions */}
      <Card title="最新持仓">
        <Table
          dataSource={positions}
          columns={positionColumns}
          rowKey="ts_code"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
