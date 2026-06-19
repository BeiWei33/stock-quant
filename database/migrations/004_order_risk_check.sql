CREATE TABLE IF NOT EXISTS order_risk_check (
    order_id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    allowed BOOLEAN NOT NULL,
    reasons TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
