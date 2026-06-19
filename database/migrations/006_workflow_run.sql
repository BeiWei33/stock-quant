CREATE TABLE IF NOT EXISTS workflow_run (
    run_id VARCHAR(100) PRIMARY KEY,
    workflow_name VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    trade_date DATE,
    summary_path TEXT,
    error_msg TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
