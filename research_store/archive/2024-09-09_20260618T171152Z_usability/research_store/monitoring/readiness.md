# Quant Readiness Report

| Metric | Value |
| --- | --- |
| Status | PAPER_READY |
| Paper Ready | True |
| Live Ready | False |
| QMT Available | False |

| Check | Passed | Severity | Detail |
| --- | --- | --- | --- |
| alerts | True | INFO | alerts status=OK |
| pretrade_gate | True | CRITICAL | pretrade status=GO |
| latest_stability | True | WARNING | latest_trade_date=2024-09-09 |
| stability_window | True | WARNING | observed=20/20, unstable_days=0 |
| qmt_interface | False | CRITICAL | qmt interface not configured |

Alerts: `research_store\monitoring\alerts.json`
Pre-Trade Gate: `research_store\reports\pretrade_gate.json`
Stability: `research_store\monitoring\stability.json`
