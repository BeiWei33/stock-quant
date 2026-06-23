import { useEffect, useState } from 'react';
import { Card, Table, Row, Col, message, Spin } from 'antd';
import ReactECharts from 'echarts-for-react';
import api from '../../api/client';

interface Position {
  ts_code: string;
  name: string;
  quantity: number;
  weight: number;
  market_value: number;
  avg_cost: number;
}

interface Distribution {
  by_stock: Array<{
    ts_code: string;
    name: string;
    weight: number;
    market_value: number;
  }>;
  by_industry: Array<{
    industry: string;
    weight: number;
    market_value: number;
  }>;
}

export default function PositionsPage() {
  const [loading, setLoading] = useState(true);
  const [positions, setPositions] = useState<Position[]>([]);
  const [distribution, setDistribution] = useState<Distribution | null>(null);
  const [tradeDate, setTradeDate] = useState<string>('');

  useEffect(() => {
    fetchPositions();
  }, []);

  const fetchPositions = async () => {
    setLoading(true);
    try {
      const [posRes, distRes] = await Promise.all([
        api.get('/api/positions'),
        api.get('/api/positions/distribution'),
      ]);

      setPositions(posRes.data.data.positions || []);
      setTradeDate(posRes.data.data.trade_date || '');
      setDistribution(distRes.data.data);
    } catch (error) {
      message.error('获取持仓数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getPieOption = () => {
    if (!distribution?.by_stock?.length) {
      return {};
    }

    return {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        type: 'scroll',
      },
      series: [
        {
          name: '持仓分布',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: {
            show: false,
            position: 'center',
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
            },
          },
          labelLine: {
            show: false,
          },
          data: distribution.by_stock.map((item) => ({
            value: item.market_value,
            name: `${item.name} (${item.ts_code})`,
          })),
        },
      ],
    };
  };

  const columns = [
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
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 100,
      align: 'right' as const,
      render: (val: number) => val?.toLocaleString(),
    },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      width: 100,
      align: 'right' as const,
      sorter: (a: Position, b: Position) => (a.weight || 0) - (b.weight || 0),
      render: (val: number) => `${(val * 100).toFixed(2)}%`,
    },
    {
      title: '市值',
      dataIndex: 'market_value',
      key: 'market_value',
      width: 120,
      align: 'right' as const,
      sorter: (a: Position, b: Position) => (a.market_value || 0) - (b.market_value || 0),
      render: (val: number) => `¥${val?.toLocaleString()}`,
    },
    {
      title: '成本价',
      dataIndex: 'avg_cost',
      key: 'avg_cost',
      width: 100,
      align: 'right' as const,
      render: (val: number) => val ? `¥${val.toFixed(2)}` : '-',
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
      <Row gutter={[16, 16]}>
        {/* Pie Chart */}
        <Col xs={24} lg={10}>
          <Card title={`持仓分布 (${tradeDate})`}>
            {distribution?.by_stock?.length ? (
              <ReactECharts option={getPieOption()} style={{ height: 400 }} />
            ) : (
              <div style={{ textAlign: 'center', padding: '100px 0', color: '#999' }}>
                暂无持仓数据
              </div>
            )}
          </Card>
        </Col>

        {/* Positions Table */}
        <Col xs={24} lg={14}>
          <Card title={`持仓列表 (${tradeDate})`}>
            <Table
              dataSource={positions}
              columns={columns}
              rowKey="ts_code"
              pagination={false}
              scroll={{ x: 600 }}
              size="small"
              summary={() => {
                const totalValue = positions.reduce((sum, p) => sum + (p.market_value || 0), 0);
                const totalWeight = positions.reduce((sum, p) => sum + (p.weight || 0), 0);

                return (
                  <Table.Summary fixed>
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0} colSpan={3}>
                        <strong>合计</strong>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={3} align="right">
                        <strong>{(totalWeight * 100).toFixed(2)}%</strong>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={4} align="right">
                        <strong>¥{totalValue.toLocaleString()}</strong>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={5} />
                    </Table.Summary.Row>
                  </Table.Summary>
                );
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
