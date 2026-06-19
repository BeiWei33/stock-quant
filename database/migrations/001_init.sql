CREATE TABLE IF NOT EXISTS stocks (
    ts_code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    exchange VARCHAR(20),
    industry VARCHAR(100),
    list_date DATE,
    delist_date DATE,
    is_st BOOLEAN DEFAULT FALSE,
    status VARCHAR(20),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_bar (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    adj_type VARCHAR(20) NOT NULL DEFAULT 'none',
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    pre_close NUMERIC,
    volume BIGINT,
    amount NUMERIC,
    source VARCHAR(50),
    quality_flag VARCHAR(50) DEFAULT 'NORMAL',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(ts_code, trade_date, adj_type)
);

CREATE TABLE IF NOT EXISTS factor_value (
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    factor_name VARCHAR(50) NOT NULL,
    factor_value NUMERIC,
    version VARCHAR(50) DEFAULT 'v1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ts_code, trade_date, factor_name, version)
);

CREATE TABLE IF NOT EXISTS signal (
    id BIGSERIAL PRIMARY KEY,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL DEFAULT 'v1',
    factor_set_id VARCHAR(100),
    signal_type VARCHAR(20) NOT NULL,
    score NUMERIC,
    target_weight NUMERIC,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50) PRIMARY KEY,
    broker_order_id VARCHAR(100),
    signal_id BIGINT,
    account_id VARCHAR(50),
    strategy_id VARCHAR(50),
    strategy_version VARCHAR(50),
    ts_code VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price NUMERIC,
    quantity INT NOT NULL,
    filled_quantity INT DEFAULT 0,
    avg_price NUMERIC,
    status VARCHAR(30) NOT NULL,
    error_msg TEXT,
    request_id VARCHAR(100),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS positions (
    account_id VARCHAR(50),
    ts_code VARCHAR(20),
    trade_date DATE,
    quantity INT,
    available_quantity INT,
    avg_cost NUMERIC,
    market_value NUMERIC,
    weight NUMERIC,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(account_id, ts_code, trade_date)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    account_id VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    total_asset NUMERIC,
    cash NUMERIC,
    market_value NUMERIC,
    total_position_ratio NUMERIC,
    daily_return NUMERIC,
    cum_return NUMERIC,
    drawdown NUMERIC,
    benchmark_code VARCHAR(50),
    excess_return NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(account_id, trade_date)
);

CREATE TABLE IF NOT EXISTS benchmark_bar (
    benchmark_code VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(benchmark_code, trade_date)
);

CREATE TABLE IF NOT EXISTS strategy_registry (
    strategy_id VARCHAR(50) NOT NULL,
    strategy_version VARCHAR(50) NOT NULL,
    description TEXT,
    factor_set_id VARCHAR(100),
    code_hash VARCHAR(100),
    config_hash VARCHAR(100),
    config_json TEXT,
    research_report_path TEXT,
    status VARCHAR(20) DEFAULT 'research',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(strategy_id, strategy_version)
);

CREATE TABLE IF NOT EXISTS universe_snapshot (
    universe_id VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    include_reason TEXT,
    exclude_reason TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(universe_id, trade_date, ts_code)
);
