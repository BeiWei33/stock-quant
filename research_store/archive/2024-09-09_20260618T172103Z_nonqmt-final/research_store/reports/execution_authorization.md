# Execution Authorization Report

| Field | Value |
| --- | --- |
| Status | GO |
| Passed | True |
| Mode | DRY_RUN |
| Adapter | dry_run |
| Trade Date | 2024-09-09 |
| Strategy | momentum_rank |
| Orders | 3 |
| Notional | 298,191.41 |
| Policy | config\execution_policy.generated.json |

## Checks
| Check | Result | Severity | Detail |
| --- | --- | --- | --- |
| execution_mode_allowed | PASS | CRITICAL | mode=DRY_RUN, allowed=DRY_RUN |
| execution_adapter_allowed | PASS | CRITICAL | adapter=dry_run, allowed=dry_run |
| auto_trade_enabled | PASS | CRITICAL | dry-run does not require auto_trade |
| manual_approval_present | PASS | CRITICAL | dry-run does not require manual approval |
| manual_approval_scope | PASS | CRITICAL | dry-run does not require approval scope |
| manual_approval_not_expired | PASS | CRITICAL | dry-run does not require approval expiry |
| order_count_limit | PASS | CRITICAL | order_count=3, max=unlimited |
| notional_limit | PASS | CRITICAL | notional=298191.41, max=unlimited |
