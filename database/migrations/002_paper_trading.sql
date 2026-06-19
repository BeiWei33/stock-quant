CREATE TABLE IF NOT EXISTS order_intent (
    order_id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price NUMERIC NOT NULL,
    quantity INT NOT NULL,
    target_weight NUMERIC NOT NULL,
    trade_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reconciliation_report (
    report_id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL,
    local_count INT NOT NULL,
    broker_count INT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
