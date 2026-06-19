# Execution Audit Report

| Metric | Value |
| --- | --- |
| Status | OK |
| Trade Date | 2024-09-09 |
| Strategy | momentum_rank |
| Started At | 2026-06-18T14:07:20.384452+00:00 |
| Ended At | 2026-06-18T14:07:20.490622+00:00 |
| Steps | 7 |

## Latest Refresh Cycle
| Step | Status | Passed | Trade Date | Strategy | Detail | Artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| execution_authorization | GO | True | 2024-09-09 | momentum_rank | authorization passed | json=research_store\reports\execution_authorization.json; markdown=research_store\reports\execution_authorization.md; policy=config\execution_policy.generated.json |
| broker_adapter_contract | OK | True | 2024-09-09 | momentum_rank | contract passed | json=research_store\reports\broker_adapter_contract.json; markdown=research_store\reports\broker_adapter_contract.md |
| manual_package | READY | True | 2024-09-09 | momentum_rank | rebuild=False | fill_template=research_store\reports\manual_fill_template.csv; json=research_store\reports\manual_execution.json; markdown=research_store\reports\manual_execution.md; order_ticket=research_store\reports\manual_order_ticket.csv |
| manual_fill_validation | OK | True | - | - | issues=0, allow_incomplete=True | fills=research_store\reports\manual_fill_template.csv; json=research_store\reports\manual_fill_validation.json; markdown=research_store\reports\manual_fill_validation.md; order_ticket=research_store\reports\manual_order_ticket.csv |
| manual_reconciliation | DIFF | True | 2024-09-09 | - | paper:2024-09-09:trades | broker_fills=research_store\reports\manual_broker_fills.csv; broker_orders=research_store\reports\manual_broker_orders.csv; json=research_store\reports\manual_reconciliation.json; local_orders=research_store\reports\manual_local_orders.csv; markdown=research_store\reports\manual_reconciliation.md; sqlite=research_store\paper_trading.sqlite3 |
| execution_day_end | READY | True | 2024-09-09 | momentum_rank | blocked=[], pending=[] | json=research_store\reports\execution_day_end.json; markdown=research_store\reports\execution_day_end.md |
| config_health | OK | True | - | - | errors=0, warnings=0 | json=research_store\monitoring\config_health.json; markdown=research_store\monitoring\config_health.md |
