CREATE TABLE IF NOT EXISTS order_fill (
    fill_id VARCHAR(120) PRIMARY KEY,
    order_id VARCHAR(100) NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    strategy_id VARCHAR(50) NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price NUMERIC NOT NULL,
    quantity INT NOT NULL,
    amount NUMERIC NOT NULL,
    fee NUMERIC NOT NULL,
    tax NUMERIC NOT NULL,
    trade_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
