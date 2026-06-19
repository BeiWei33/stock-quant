CREATE TABLE IF NOT EXISTS workflow_lock (
    workflow_name VARCHAR(100) PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    acquired_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
