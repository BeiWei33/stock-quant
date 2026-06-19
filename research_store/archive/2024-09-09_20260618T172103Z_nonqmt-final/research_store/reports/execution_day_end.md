# Execution Day-End Report - 2024-09-09

| Metric | Value |
| --- | --- |
| Status | READY |
| Trade Date | 2024-09-09 |
| Strategy | momentum_rank |
| Orders | 3 |
| Estimated Notional | 298,191.41 |

## Artifacts
| Artifact | Status | Passed | Detail | Path |
| --- | --- | --- | --- | --- |
| paper_plan | OK | True | orders=3 | research_store\reports\paper_plan.json |
| risk_guard | OK | True | accepted=3, rejected=0 | research_store\reports\risk_guard.json |
| broker_submission | OK | True | mode=DRY_RUN, orders=3 | research_store\reports\broker_submission.json |
| execution_authorization | OK | True | mode=DRY_RUN, adapter=dry_run | research_store\reports\execution_authorization.json |
| broker_adapter_contract | OK | True | adapter=dry_run, mode=DRY_RUN, submitted=False | research_store\reports\broker_adapter_contract.json |
| manual_execution | READY | True | orders=3, notional=298,191.41 | research_store\reports\manual_execution.json |
| pretrade_gate | GO | True | checks=13 | research_store\reports\pretrade_gate.json |
| manual_fill_validation | OK | True | issues=0 | research_store\reports\manual_fill_validation.json |
| manual_reconciliation | DIFF | False | report_id=paper:2024-09-09:trades | research_store\reports\manual_reconciliation.json |
| monitor_status | INFO | True | latest=2024-09-09 | research_store\monitoring\status_summary.json |
| readiness | PAPER_READY | True | paper_ready=True, live_ready=False | research_store\monitoring\readiness.json |
