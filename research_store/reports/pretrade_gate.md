# Pre-Trade Gate Report

| Field | Value |
| --- | --- |
| Status | GO |
| Passed | True |
| Monitor | research_store\monitoring\status_summary.json |
| Risk Guard | research_store\reports\risk_guard.json |
| Broker Submission | research_store\reports\broker_submission.json |
| Execution Policy | config\execution_policy.generated.json |

## Checks
| Check | Result | Severity | Detail |
| --- | --- | --- | --- |
| monitor_status | PASS | INFO | monitor level is INFO |
| risk_guard_allowed | PASS | CRITICAL | allowed=True, rejected_orders=0 |
| broker_risk_guard_link | PASS | CRITICAL | broker risk_guard_allowed=True |
| order_count_match | PASS | CRITICAL | risk_guard accepted_orders=3, broker order_count=3 |
| broker_mode | PASS | INFO | broker mode is DRY_RUN |
| execution_execution_mode_allowed | PASS | CRITICAL | mode=DRY_RUN, allowed=DRY_RUN |
| execution_execution_adapter_allowed | PASS | CRITICAL | adapter=dry_run, allowed=dry_run |
| execution_auto_trade_enabled | PASS | CRITICAL | dry-run does not require auto_trade |
| execution_manual_approval_present | PASS | CRITICAL | dry-run does not require manual approval |
| execution_manual_approval_scope | PASS | CRITICAL | dry-run does not require approval scope |
| execution_manual_approval_not_expired | PASS | CRITICAL | dry-run does not require approval expiry |
| execution_order_count_limit | PASS | CRITICAL | order_count=3, max=unlimited |
| execution_notional_limit | PASS | CRITICAL | notional=298191.41, max=unlimited |
