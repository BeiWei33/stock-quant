# Live Execution Rehearsal

| Metric | Value |
| --- | --- |
| Status | POLICY_BLOCKED |
| Live Adapter | qmt |
| Trade Date | 2024-09-09 |
| Strategy | momentum_rank |
| Orders | 3 |
| Notional | 298,191.41 |
| Source Submission | research_store\reports\broker_submission.json |
| Policy | config\execution_policy.generated.json |

## Default Authorization
| Metric | Value |
| --- | --- |
| Status | BLOCK |
| Passed | False |
| Mode | LIVE |
| Adapter | qmt |
| Policy | default dry-run only |
| Failed Checks | execution_mode_allowed;execution_adapter_allowed;auto_trade_enabled;manual_approval_present;manual_approval_not_expired |

## Policy Authorization
| Metric | Value |
| --- | --- |
| Status | BLOCK |
| Passed | False |
| Mode | LIVE |
| Adapter | qmt |
| Policy | config\execution_policy.generated.json |
| Failed Checks | execution_mode_allowed;execution_adapter_allowed;auto_trade_enabled;manual_approval_present;manual_approval_not_expired |
