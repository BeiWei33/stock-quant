import { useEffect, useState } from 'react';
import { Card, Select, Spin, message, Row, Col, Descriptions, Tag } from 'antd';
import ReactECharts from 'echarts-for-react';
import api from '../../api/client';

interface StockInfo {
  ts_code: string;
  name: string;
  exchange: string;
  industry: string;
}

interface KlineData {
  ts_code: string;
  name: string;
  dates: string[];
  kline: number[][]; // [open, close, low, high]
  volume: number[];
  ma5: (number | null)[];
  ma10: (number | null)[];
  ma20: (number | null)[];
  ma60: (number | null)[];
}

interface Signal {
  trade_date: string;
  signal_type: string;
  score: number;
  price: number;
}

export default function KLinePage() {
  const [loading, setLoading] = useState(false);
  const [stocks, setStocks] = useState<StockInfo[]>([]);
  const [selectedStock, setSelectedStock] = useState<string>('');
  const [klineData, setKlineData] = useState<KlineData | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [searchKeyword, setSearchKeyword] = useState('');

  useEffect(() => {
    fetchStocks();
  }, []);

  useEffect(() => {
    if (selectedStock) {
      fetchKlineData(selectedStock);
      fetchSignals(selectedStock);
    }
  }, [selectedStock]);

  const fetchStocks = async (keyword?: string) => {
    try {
      const response = await api.get('/api/market/stocks', {
        params: { keyword: keyword || '', limit: 100 },
      });
      setStocks(response.data.data || []);
    } catch (error) {
      console.error('获取股票列表失败', error);
    }
  };

  const fetchKlineData = async (tsCode: string) => {
    setLoading(true);
    try {
      const response = await api.get('/api/market/kline', {
        params: { ts_code: tsCode, period: 'daily', limit: 250 },
      });
      setKlineData(response.data.data);
    } catch (error) {
      message.error('获取K线数据失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchSignals = async (tsCode: string) => {
    try {
      const response = await api.get(`/api/market/signals/${tsCode}`);
      setSignals(response.data.data || []);
    } catch (error) {
      console.error('获取信号数据失败', error);
    }
  };

  const handleSearch = (value: string) => {
    setSearchKeyword(value);
    if (value.length >= 2) {
      fetchStocks(value);
    }
  };

  const getKlineOption = () => {
    if (!klineData?.dates?.length) return {};

    // Prepare signal markers
    const buySignals: any[] = [];
    const sellSignals: any[] = [];

    signals.forEach((signal) => {
      const index = klineData.dates.indexOf(signal.trade_date);
      if (index >= 0) {
        const point = {
          coord: [signal.trade_date, signal.price || klineData.kline[index]?.[1]],
          value: signal.signal_type === 'BUY' ? '买' : '卖',
          itemStyle: {
            color: signal.signal_type === 'BUY' ? '#52c41a' : '#ff4d4f',
          },
        };

        if (signal.signal_type === 'BUY') {
          buySignals.push(point);
        } else {
          sellSignals.push(point);
        }
      }
    });

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
        },
      },
      legend: {
        data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60'],
        top: 10,
      },
      grid: [
        {
          left: '3%',
          right: '4%',
          height: '55%',
        },
        {
          left: '3%',
          right: '4%',
          top: '72%',
          height: '20%',
        },
      ],
      xAxis: [
        {
          type: 'category',
          data: klineData.dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: '#999' } },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: klineData.dates,
          boundaryGap: true,
          axisLabel: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true,
          splitArea: { show: true },
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 70,
          end: 100,
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          bottom: 10,
          start: 70,
          end: 100,
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: klineData.kline,
          itemStyle: {
            color: '#ef232a',
            color0: '#14b143',
            borderColor: '#ef232a',
            borderColor0: '#14b143',
          },
          markPoint: {
            data: [
              ...buySignals.map((p) => ({
                ...p,
                symbol: 'triangle',
                symbolSize: 12,
                symbolRotate: 0,
              })),
              ...sellSignals.map((p) => ({
                ...p,
                symbol: 'triangle',
                symbolSize: 12,
                symbolRotate: 180,
              })),
            ],
          },
        },
        {
          name: 'MA5',
          type: 'line',
          data: klineData.ma5,
          smooth: true,
          lineStyle: { width: 1 },
          showSymbol: false,
        },
        {
          name: 'MA10',
          type: 'line',
          data: klineData.ma10,
          smooth: true,
          lineStyle: { width: 1 },
          showSymbol: false,
        },
        {
          name: 'MA20',
          type: 'line',
          data: klineData.ma20,
          smooth: true,
          lineStyle: { width: 1 },
          showSymbol: false,
        },
        {
          name: 'MA60',
          type: 'line',
          data: klineData.ma60,
          smooth: true,
          lineStyle: { width: 1 },
          showSymbol: false,
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: klineData.volume,
          itemStyle: {
            color: (params: any) => {
              const kline = klineData.kline[params.dataIndex];
              return kline && kline[1] >= kline[0] ? '#ef232a' : '#14b143';
            },
          },
        },
      ],
    };
  };

  return (
    <div>
      {/* Stock Selector */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Select
              showSearch
              placeholder="搜索股票代码或名称"
              style={{ width: '100%' }}
              value={selectedStock || undefined}
              onChange={setSelectedStock}
              onSearch={handleSearch}
              filterOption={false}
              notFoundContent={loading ? <Spin size="small" /> : null}
            >
              {stocks.map((stock) => (
                <Select.Option key={stock.ts_code} value={stock.ts_code}>
                  {stock.ts_code} - {stock.name}
                </Select.Option>
              ))}
            </Select>
          </Col>
        </Row>
      </Card>

      {/* Stock Info */}
      {klineData && (
        <Card style={{ marginBottom: 24 }}>
          <Descriptions>
            <Descriptions.Item label="股票代码">{klineData.ts_code}</Descriptions.Item>
            <Descriptions.Item label="股票名称">{klineData.name}</Descriptions.Item>
            <Descriptions.Item label="信号数">
              <Tag color="blue">{signals.length}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* K-Line Chart */}
      <Card title={klineData ? `${klineData.name} (${klineData.ts_code}) K线图` : 'K线图'}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '200px 0' }}>
            <Spin size="large" />
          </div>
        ) : klineData?.dates?.length ? (
          <ReactECharts option={getKlineOption()} style={{ height: 600 }} />
        ) : (
          <div style={{ textAlign: 'center', padding: '200px 0', color: '#999' }}>
            请选择股票查看K线图
          </div>
        )}
      </Card>
    </div>
  );
}
