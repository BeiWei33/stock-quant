# Config Health Report

| Metric | Value |
| --- | --- |
| Status | OK |
| Errors | 0 |
| Warnings | 0 |
| Checks | 17 |

## Checks
| Check | Status | Severity | Detail | Path |
| --- | --- | --- | --- | --- |
| stocks | OK | INFO | columns=8 | research_store\sample\stocks.csv |
| daily_bars | OK | INFO | columns=12 | research_store\sample\daily_bar.cleaned.csv |
| daily_config | OK | INFO | bytes=700 | config\daily.yaml |
| cleaning_config | OK | INFO | bytes=316 | config\cleaning.yaml |
| risk_guard_control | OK | INFO | trade_mode=NORMAL | research_store\state\risk_guard_control.env |
| execution_policy | OK | INFO | modes=DRY_RUN, adapters=dry_run | config\execution_policy.generated.json |
| broker_submission | OK | INFO | fields present | research_store\reports\broker_submission.json |
| execution_authorization | GO | INFO | status=GO | research_store\reports\execution_authorization.json |
| broker_adapter_contract | OK | INFO | adapter=dry_run, mode=DRY_RUN, submitted=False | research_store\reports\broker_adapter_contract.json |
| pretrade_gate | GO | INFO | status=GO | research_store\reports\pretrade_gate.json |
| manual_order_ticket | OK | INFO | columns=14 | research_store\reports\manual_order_ticket.csv |
| manual_fill_template | OK | INFO | columns=10 | research_store\reports\manual_fill_template.csv |
| manual_fill_validation | OK | INFO | manual fills validated | research_store\reports\manual_fill_validation.json |
| execution_day_end | READY | INFO | status=READY | research_store\reports\execution_day_end.json |
| monitor_status | INFO | INFO | level=INFO | research_store\monitoring\status_summary.json |
| readiness | PAPER_READY | INFO | status=PAPER_READY | research_store\monitoring\readiness.json |
| monitor_history | OK | INFO | columns=44 | research_store\monitoring\daily_history.csv |
