# Execution Audit Report

| Metric | Value |
| --- | --- |
| Status | BLOCKED |
| Trade Date | 2024-09-09 |
| Strategy | momentum_rank |
| Started At | 2026-06-19T08:49:55.082534+00:00 |
| Ended At | 2026-06-19T08:49:55.107847+00:00 |
| Steps | 7 |

## Latest Refresh Cycle
| Step | Status | Passed | Trade Date | Strategy | Detail | Artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| execution_authorization | GO | True | 2024-09-09 | momentum_rank | authorization passed | json=research_store\reports\execution_authorization.json; markdown=research_store\reports\execution_authorization.md; policy=config\execution_policy.generated.json |
| broker_adapter_contract | OK | True | 2024-09-09 | momentum_rank | contract passed | json=research_store\reports\broker_adapter_contract.json; markdown=research_store\reports\broker_adapter_contract.md |
| manual_package | READY | True | 2024-09-09 | momentum_rank | rebuild=False | fill_template=research_store\reports\manual_fill_template.csv; json=research_store\reports\manual_execution.json; markdown=research_store\reports\manual_execution.md; order_ticket=research_store\reports\manual_order_ticket.csv |
| manual_fill_validation | ERROR | False | - | - | issues=3, allow_incomplete=False | fills=research_store\reports\manual_fill_template.csv; json=research_store\reports\manual_fill_validation.json; markdown=research_store\reports\manual_fill_validation.md; order_ticket=research_store\reports\manual_order_ticket.csv |
| manual_reconciliation | SKIPPED | - | 2024-09-09 | momentum_rank | manual validation did not pass | json=research_store\reports\manual_reconciliation.json; markdown=research_store\reports\manual_reconciliation.md |
| execution_day_end | BLOCKED | False | 2024-09-09 | momentum_rank | blocked=['manual_fill_validation'], pending=['manual_reconciliation'] | json=research_store\reports\execution_day_end.json; markdown=research_store\reports\execution_day_end.md |
| config_health | WARNING | True | - | - | errors=0, warnings=2 | json=research_store\monitoring\config_health.json; markdown=research_store\monitoring\config_health.md |
