import { useEffect, useState } from 'react';
import { Card, Row, Col, Tag, Table, Descriptions, Spin, message, Badge } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import api from '../../api/client';

interface HealthCheck {
  name: string;
  passed: boolean;
  severity: string;
  detail?: string;
}

interface Alert {
  name: string;
  severity: string;
  passed: boolean;
  detail?: string;
}

interface Readiness {
  status: string;
  paper_ready: boolean;
  live_ready: boolean;
  checks: HealthCheck[];
  qmt_available: boolean;
}

interface AlertSummary {
  status: string;
  passed: boolean;
  highest_severity: string;
  alerts: Alert[];
}

interface ConfigHealth {
  status: string;
  checks: Array<{
    name: string;
    status: string;
    detail?: string;
  }>;
}

export default function MonitoringPage() {
  const [loading, setLoading] = useState(true);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [alerts, setAlerts] = useState<AlertSummary | null>(null);
  const [configHealth, setConfigHealth] = useState<ConfigHealth | null>(null);

  useEffect(() => {
    fetchMonitoringData();
  }, []);

  const fetchMonitoringData = async () => {
    setLoading(true);
    try {
      const [healthRes, alertsRes, configRes] = await Promise.all([
        api.get('/api/monitoring/health'),
        api.get('/api/monitoring/alerts'),
        api.get('/api/monitoring/config'),
      ]);

      setReadiness(healthRes.data.data);
      setAlerts(alertsRes.data.data);
      setConfigHealth(configRes.data.data);
    } catch (error) {
      message.error('获取监控数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityIcon = (severity: string, passed: boolean) => {
    if (!passed) {
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    }
    switch (severity) {
      case 'CRITICAL':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'WARNING':
        return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'INFO':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      default:
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
    }
  };

  const getSeverityTag = (severity: string) => {
    const colorMap: Record<string, string> = {
      CRITICAL: 'error',
      WARNING: 'warning',
      INFO: 'success',
    };
    return <Tag color={colorMap[severity] || 'default'}>{severity}</Tag>;
  };

  const checkColumns = [
    {
      title: '检查项',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_: any, record: HealthCheck) => (
        <span>
          {getSeverityIcon(record.severity, record.passed)}
          <span style={{ marginLeft: 8 }}>
            {record.passed ? '通过' : '失败'}
          </span>
        </span>
      ),
    },
    {
      title: '级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (severity: string) => getSeverityTag(severity),
    },
    {
      title: '详情',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true,
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
      {/* System Status Overview */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>系统就绪状态</div>
              <Badge
                status={readiness?.paper_ready ? 'success' : 'error'}
                text={
                  <span style={{ fontSize: 18, fontWeight: 600 }}>
                    {readiness?.status || 'UNKNOWN'}
                  </span>
                }
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>模拟盘</div>
              <Badge
                status={readiness?.paper_ready ? 'success' : 'error'}
                text={
                  <span style={{ fontSize: 18, fontWeight: 600 }}>
                    {readiness?.paper_ready ? '就绪' : '未就绪'}
                  </span>
                }
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>实盘</div>
              <Badge
                status={readiness?.live_ready ? 'success' : 'error'}
                text={
                  <span style={{ fontSize: 18, fontWeight: 600 }}>
                    {readiness?.live_ready ? '就绪' : '未就绪'}
                  </span>
                }
              />
            </div>
          </Card>
        </Col>
      </Row>

      {/* Alerts */}
      <Card
        title="告警"
        style={{ marginBottom: 24 }}
        extra={
          <Tag color={alerts?.passed ? 'success' : 'error'}>
            {alerts?.status || 'UNKNOWN'}
          </Tag>
        }
      >
        <Table
          dataSource={alerts?.alerts || []}
          columns={checkColumns}
          rowKey="name"
          pagination={false}
          size="small"
        />
      </Card>

      {/* Readiness Checks */}
      <Card title="就绪检查" style={{ marginBottom: 24 }}>
        <Table
          dataSource={readiness?.checks || []}
          columns={checkColumns}
          rowKey="name"
          pagination={false}
          size="small"
        />
      </Card>

      {/* Config Health */}
      <Card
        title="配置健康"
        extra={
          <Tag color={configHealth?.status === 'OK' ? 'success' : 'warning'}>
            {configHealth?.status || 'UNKNOWN'}
          </Tag>
        }
      >
        {configHealth?.checks?.length ? (
          <Descriptions bordered column={1} size="small">
            {configHealth.checks.map((check) => (
              <Descriptions.Item
                key={check.name}
                label={
                  <span>
                    {check.status === 'OK' ? (
                      <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                    ) : (
                      <WarningOutlined style={{ color: '#faad14', marginRight: 8 }} />
                    )}
                    {check.name}
                  </span>
                }
              >
                {check.detail || check.status}
              </Descriptions.Item>
            ))}
          </Descriptions>
        ) : (
          <div style={{ textAlign: 'center', color: '#999' }}>暂无配置检查数据</div>
        )}
      </Card>
    </div>
  );
}
